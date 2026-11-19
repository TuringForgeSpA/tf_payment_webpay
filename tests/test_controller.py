from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.tf_payment_webpay.tests.common import WebpayCommon

TRANSACTION_PATH = 'transbank.webpay.webpay_plus.transaction.Transaction'


@tagged('post_install', '-at_install')
class TestWebpayController(WebpayCommon, PaymentHttpCommon):

    @mute_logger('odoo.addons.tf_payment_webpay.controllers.main')
    def test_return_by_get_confirms_and_redirects_to_status(self):
        tx = self._create_webpay_transaction()
        url = self._build_url('/payment/webpay/return')
        with patch(f'{TRANSACTION_PATH}.commit', return_value=self._commit_response(tx)):
            response = self._make_http_get_request(url, params={'token_ws': self.token})
        self.assertEqual(response.status_code, 200)  # Tras seguir la redirección a /payment/status.
        self.assertTrue(response.url.endswith('/payment/status'))
        self.assertEqual(tx.state, 'done')

    @mute_logger('odoo.addons.tf_payment_webpay.controllers.main')
    def test_return_by_post_with_abort_cancels(self):
        tx = self._create_webpay_transaction()
        url = self._build_url('/payment/webpay/return')
        self._make_http_post_request(url, data={
            'TBK_TOKEN': self.token,
            'TBK_ORDEN_COMPRA': tx.webpay_buy_order,
            'TBK_ID_SESION': str(tx.id),
        })
        self.assertEqual(tx.state, 'cancel')

    @mute_logger('odoo.addons.tf_payment_webpay.controllers.main')
    def test_unknown_token_does_not_crash(self):
        url = self._build_url('/payment/webpay/return')
        response = self._make_http_get_request(url, params={'token_ws': 'desconocido'})
        self.assertEqual(response.status_code, 200)
