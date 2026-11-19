import logging

from transbank.common.integration_type import IntegrationType
from transbank.common.options import WebpayOptions
from transbank.webpay.webpay_plus.transaction import Transaction

from odoo import api, fields, models

from odoo.addons.tf_payment_webpay import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('webpay', 'WebPay')], ondelete={'webpay': 'set default'}
    )
    webpay_commerce_code = fields.Char(
        string="Código de comercio",
        help="Código de comercio entregado por Transbank.",
        required_if_provider='webpay',
        groups='base.group_system',
    )
    webpay_api_key = fields.Char(
        string="API Key secreta",
        help="Llave secreta entregada por Transbank.",
        required_if_provider='webpay',
        groups='base.group_system',
    )

    # === COMPUTE METHODS === #

    @api.depends('code')
    def _compute_feature_support_fields(self):
        """ Override de `payment` para habilitar los reembolsos parciales. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'webpay').update({
            'support_refund': 'partial',
        })

    # === BUSINESS METHODS === #

    def _get_supported_currencies(self):
        """ Override de `payment` para limitar las monedas a CLP. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'webpay':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """ Override de `payment` para retornar los métodos de pago por defecto. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'webpay':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _webpay_get_transaction(self):
        """ Construye el cliente de WebPay Plus según el estado del proveedor.

        El estado "Habilitado" usa el ambiente de producción de Transbank; el estado "Modo de
        prueba" usa el ambiente de integración.

        Note: self.ensure_one()

        :return: El cliente de transacciones de WebPay Plus.
        :rtype: transbank.webpay.webpay_plus.transaction.Transaction
        """
        self.ensure_one()
        integration_type = IntegrationType.LIVE if self.state == 'enabled' else IntegrationType.TEST
        options = WebpayOptions(
            self.webpay_commerce_code, self.webpay_api_key, integration_type,
            timeout=const.API_TIMEOUT,
        )
        return Transaction(options)
