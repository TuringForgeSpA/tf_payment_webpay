import hashlib
import logging

from transbank.error.transbank_error import TransbankError
from werkzeug import urls

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_round

from odoo.addons.tf_payment_webpay import const
from odoo.addons.tf_payment_webpay.controllers.main import WebpayController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    webpay_token = fields.Char(string="Token WebPay", readonly=True, copy=False, index=True)
    webpay_buy_order = fields.Char(
        string="Orden de compra WebPay", readonly=True, copy=False, index=True,
    )
    webpay_payment_type_code = fields.Char(string="Tipo de pago WebPay", readonly=True, copy=False)
    webpay_installments_number = fields.Integer(
        string="Número de cuotas WebPay", readonly=True, copy=False,
    )
    webpay_card_number = fields.Char(
        string="Últimos dígitos de la tarjeta", readonly=True, copy=False,
    )

    # === BUSINESS METHODS - PAYMENT FLOW === #

    def _get_specific_rendering_values(self, processing_values):
        """ Override de `payment` para crear la transacción en WebPay y retornar los valores del
        formulario de redirección.

        Note: self.ensure_one() desde `_get_processing_values`.

        :param dict processing_values: Los valores genéricos y específicos de la transacción.
        :return: Los valores específicos para el formulario de redirección.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'webpay':
            return res

        base_url = self.provider_id.get_base_url()
        return_url = urls.url_join(base_url, WebpayController._return_url)
        buy_order = self._webpay_compute_buy_order()
        try:
            response = self.provider_id._webpay_get_transaction().create(
                buy_order, str(self.id), self._webpay_get_amount(), return_url,
            )
        except TransbankError as error:
            _logger.warning(
                "WebPay: error al crear la transacción %s: %s", self.reference, error.message,
            )
            raise ValidationError("WebPay: " + _(
                "No fue posible iniciar el pago con Transbank. Inténtalo nuevamente."
            ))

        self.write({
            'webpay_token': response['token'],
            'webpay_buy_order': buy_order,
        })
        return {
            'api_url': response['url'],
            'token_ws': response['token'],
        }

    def _webpay_compute_buy_order(self):
        """ Retorna la orden de compra a enviar a Transbank.

        La API admite como máximo 26 caracteres. Si la referencia de Odoo es más larga se usa un
        prefijo de la referencia más un hash corto, que se guarda para ubicar la transacción.

        :return: La orden de compra.
        :rtype: str
        """
        self.ensure_one()
        reference = self.reference
        if len(reference) <= const.BUY_ORDER_MAX_LENGTH:
            return reference
        digest = hashlib.sha1(f'{reference}-{self.id}'.encode()).hexdigest()[:8]
        return f'{reference[:const.BUY_ORDER_MAX_LENGTH - 9]}-{digest}'

    def _webpay_get_amount(self):
        """ Retorna el monto en pesos chilenos (sin decimales), como lo exige WebPay.

        :return: El monto redondeado.
        :rtype: int
        """
        self.ensure_one()
        return int(float_round(abs(self.amount), precision_digits=0))

    # === BUSINESS METHODS - NOTIFICATION PROCESSING === #

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override de `payment` para encontrar la transacción a partir de los datos de retorno.

        :param str provider_code: El código del proveedor.
        :param dict notification_data: Los datos enviados por Transbank.
        :return: La transacción encontrada.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: Si los datos no coinciden con ninguna transacción.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'webpay' or len(tx) == 1:
            return tx

        # En una anulación llega `TBK_TOKEN`; en el flujo normal, `token_ws`; en un tiempo
        # agotado, solo la orden de compra.
        token = notification_data.get('token_ws') or notification_data.get('TBK_TOKEN')
        buy_order = notification_data.get('TBK_ORDEN_COMPRA')
        if token:
            domain = [('webpay_token', '=', token)]
        elif buy_order:
            domain = [('webpay_buy_order', '=', buy_order)]
        else:
            raise ValidationError("WebPay: " + _("Se recibieron datos sin token ni orden de compra."))

        tx = self.search(domain + [('provider_code', '=', 'webpay')], limit=1)
        if not tx:
            raise ValidationError(
                "WebPay: " + _("No se encontró ninguna transacción para los datos recibidos.")
            )
        return tx

    def _process_notification_data(self, notification_data):
        """ Override de `payment` para procesar el retorno de WebPay.

        En el flujo normal confirma (commit) la transacción en Transbank y valida la respuesta
        contra la transacción de Odoo antes de marcarla como pagada.

        Note: self.ensure_one() desde `_process_notification_data`.

        :param dict notification_data: Los datos enviados por Transbank.
        :return: None
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'webpay':
            return

        # Evita confirmar dos veces (por ejemplo, si el cliente recarga la página de retorno).
        if self.state not in ('draft', 'pending'):
            _logger.info(
                "WebPay: la transacción %s ya fue procesada (estado %s).", self.reference, self.state,
            )
            return

        if notification_data.get('TBK_TOKEN'):
            self._set_canceled(state_message=_("El pago fue anulado en el formulario de WebPay."))
            return
        if not notification_data.get('token_ws'):
            self._set_canceled(state_message=_("Se agotó el tiempo para completar el pago en WebPay."))
            return

        try:
            response = self.provider_id._webpay_get_transaction().commit(self.webpay_token)
        except TransbankError as error:
            _logger.warning(
                "WebPay: error al confirmar la transacción %s: %s", self.reference, error.message,
            )
            self._set_error("WebPay: " + _(
                "No fue posible confirmar el pago con Transbank. Revisa el estado de la "
                "transacción antes de reintentar."
            ))
            return

        self._webpay_apply_commit_response(response)

    def _webpay_apply_commit_response(self, response):
        """ Valida la respuesta del commit y actualiza el estado de la transacción.

        :param dict response: La respuesta de `Transaction.commit`.
        :return: None
        """
        self.ensure_one()
        response_code = response.get('response_code')
        status = response.get('status')
        self.provider_reference = response.get('authorization_code') or self.provider_reference
        self.webpay_payment_type_code = response.get('payment_type_code')
        self.webpay_installments_number = response.get('installments_number') or 0
        self.webpay_card_number = (response.get('card_detail') or {}).get('card_number')

        if response_code != 0 or status != const.STATUS_AUTHORIZED:
            _logger.info(
                "WebPay: transacción %s rechazada (response_code=%s, status=%s).",
                self.reference, response_code, status,
            )
            self._set_error("WebPay: " + _(
                "El pago fue rechazado (código %(code)s).", code=response_code,
            ))
            return

        # Valida que la respuesta corresponda a esta transacción y al monto esperado.
        expected_amount = self._webpay_get_amount()
        if response.get('buy_order') != self.webpay_buy_order or float_compare(
            response.get('amount') or 0, expected_amount, precision_digits=0,
        ) != 0:
            _logger.error(
                "WebPay: datos inconsistentes para %s: orden %s (esperada %s), monto %s "
                "(esperado %s).", self.reference, response.get('buy_order'),
                self.webpay_buy_order, response.get('amount'), expected_amount,
            )
            self._set_error("WebPay: " + _(
                "La respuesta de Transbank no coincide con la orden o el monto de la transacción."
            ))
            return

        self._set_done()

    # === BUSINESS METHODS - REFUND === #

    def _send_refund_request(self, amount_to_refund=None):
        """ Override de `payment` para solicitar el reembolso a Transbank.

        Note: self.ensure_one()

        :param float amount_to_refund: El monto a reembolsar.
        :return: La transacción de reembolso creada.
        :rtype: recordset of `payment.transaction`
        """
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != 'webpay':
            return refund_tx

        amount = refund_tx._webpay_get_amount()
        try:
            response = self.provider_id._webpay_get_transaction().refund(self.webpay_token, amount)
        except TransbankError as error:
            _logger.warning(
                "WebPay: error al reembolsar %s: %s", self.reference, error.message,
            )
            refund_tx._set_error("WebPay: " + _(
                "Transbank rechazó el reembolso: %(message)s", message=error.message,
            ))
            return refund_tx

        refund_type = response.get('type')
        if refund_type in const.REFUND_TYPES_OK and response.get('response_code', 0) == 0:
            refund_tx.provider_reference = response.get('authorization_code') or refund_type
            refund_tx._set_done()
        else:
            refund_tx._set_error("WebPay: " + _(
                "Respuesta inesperada de Transbank al reembolsar (tipo %(type)s).",
                type=refund_type,
            ))
        return refund_tx
