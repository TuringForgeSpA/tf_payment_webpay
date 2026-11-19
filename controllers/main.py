import logging
import pprint

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class WebpayController(http.Controller):
    _return_url = '/payment/webpay/return'

    @http.route(
        _return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False,
        save_session=False,
    )
    def webpay_return_from_checkout(self, **data):
        """ Procesa el retorno del cliente desde el formulario de WebPay.

        Transbank vuelve a la URL de retorno con distintos parámetros según el caso:

        - Flujo normal (pago aprobado o rechazado): `token_ws`.
        - Pago anulado por el cliente: `TBK_TOKEN`, `TBK_ORDEN_COMPRA` y `TBK_ID_SESION`.
        - Tiempo agotado en el formulario: `TBK_ORDEN_COMPRA` y `TBK_ID_SESION`.
        - Error en el formulario de pago: `token_ws` junto con `TBK_TOKEN` y los demás.

        `save_session=False` evita reemplazar la sesión del cliente cuando el retorno llega por
        POST desde el dominio de Transbank (sin cookies). La redirección final por GET sí lleva la
        cookie de sesión, por lo que /payment/status encuentra la transacción.

        :param dict data: Los parámetros enviados por Transbank.
        """
        _logger.info("Retorno desde WebPay con los datos:\n%s", pprint.pformat(data))
        try:
            request.env['payment.transaction'].sudo()._handle_notification_data('webpay', data)
        except ValidationError:
            _logger.exception("WebPay: no fue posible procesar los datos de retorno.")
        return request.redirect('/payment/status')
