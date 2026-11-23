from odoo import api, models

from odoo.addons.tf_payment_webpay import const


class PaymentMethod(models.Model):
    _inherit = 'payment.method'

    @api.model
    def _webpay_set_refund_support(self, support_refund='partial'):
        """ Ajusta el soporte de reembolsos del método de pago WebPay.

        El módulo `payment` crea el método `webpay` con `support_refund = 'none'`, lo que oculta
        el botón "Reembolsar" en los pagos aunque el proveedor sí permita reembolsos. Se llama al
        instalar o actualizar este módulo, y con `'none'` al desinstalarlo.

        :param str support_refund: El valor a asignar ('none', 'full_only' o 'partial').
        :return: None
        """
        methods = self.with_context(active_test=False).search([
            ('code', 'in', list(const.DEFAULT_PAYMENT_METHOD_CODES)),
        ])
        methods.write({'support_refund': support_refund})
