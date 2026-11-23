from transbank.common.integration_type import IntegrationType

from odoo.tests import tagged

from odoo.addons.tf_payment_webpay.tests.common import WebpayCommon


@tagged('post_install', '-at_install')
class TestPaymentProvider(WebpayCommon):

    def test_supports_partial_refund(self):
        self.assertEqual(self.provider.support_refund, 'partial')

    def test_only_clp_is_supported(self):
        currencies = self.provider._get_supported_currencies()
        self.assertEqual(currencies.mapped('name'), ['CLP'])

    def test_environment_follows_provider_state(self):
        self.provider.state = 'test'
        options = self.provider._webpay_get_transaction().options
        self.assertEqual(options.integration_type, IntegrationType.TEST)
        self.assertEqual(options.commerce_code, '597055555532')

        self.provider.state = 'enabled'
        options = self.provider._webpay_get_transaction().options
        self.assertEqual(options.integration_type, IntegrationType.LIVE)

    def test_webpay_payment_method_supports_refund(self):
        """ El método `webpay` del módulo `payment` viene con `support_refund = 'none'`; este
        módulo debe habilitarlo para que aparezca el botón "Reembolsar". """
        method = self.env.ref('payment.payment_method_webpay')
        self.assertEqual(method.support_refund, 'partial')
