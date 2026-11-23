from unittest.mock import patch

from transbank.error.transaction_commit_error import TransactionCommitError

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.tf_payment_webpay.tests.common import WebpayCommon

TRANSACTION_PATH = 'transbank.webpay.webpay_plus.transaction.Transaction'


@tagged('post_install', '-at_install')
class TestPaymentTransaction(WebpayCommon, PaymentHttpCommon):

    def test_redirect_form_posts_token_to_webpay(self):
        tx = self._create_transaction(flow='redirect')
        with patch(f'{TRANSACTION_PATH}.create', return_value=self.create_response) as create:
            processing_values = tx._get_processing_values()

        buy_order, session_id, amount, return_url = create.call_args.args
        self.assertEqual(buy_order, tx.reference)
        self.assertEqual(session_id, str(tx.id))
        self.assertEqual(amount, 15990)
        self.assertEqual(return_url, self._build_url('/payment/webpay/return'))

        form_info = self._extract_values_from_html_form(processing_values['redirect_form_html'])
        self.assertEqual(form_info['action'], self.create_response['url'])
        self.assertEqual(form_info['method'], 'post')
        self.assertDictEqual(form_info['inputs'], {'token_ws': self.token})
        self.assertEqual(tx.state, 'draft', "La transacción no debe cambiar de estado antes del pago.")
        self.assertEqual(tx.webpay_token, self.token)

    def test_long_reference_is_shortened_for_buy_order(self):
        tx = self._create_transaction(flow='redirect', reference='S' * 40)
        buy_order = tx._webpay_compute_buy_order()
        self.assertLessEqual(len(buy_order), 26)
        self.assertTrue(buy_order.startswith('S' * 17))

    def test_authorized_commit_confirms_transaction(self):
        tx = self._create_webpay_transaction()
        with patch(f'{TRANSACTION_PATH}.commit', return_value=self._commit_response(tx)):
            tx._handle_notification_data('webpay', {'token_ws': self.token})
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, '1213')
        self.assertEqual(tx.webpay_card_number, '6623')

    @mute_logger('odoo.addons.tf_payment_webpay.models.payment_transaction')
    def test_rejected_commit_sets_error(self):
        tx = self._create_webpay_transaction()
        response = self._commit_response(tx, response_code=-1, status='FAILED')
        with patch(f'{TRANSACTION_PATH}.commit', return_value=response):
            tx._handle_notification_data('webpay', {'token_ws': self.token})
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.tf_payment_webpay.models.payment_transaction')
    def test_amount_mismatch_sets_error(self):
        tx = self._create_webpay_transaction()
        response = self._commit_response(tx, amount=10)
        with patch(f'{TRANSACTION_PATH}.commit', return_value=response):
            tx._handle_notification_data('webpay', {'token_ws': self.token})
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.tf_payment_webpay.models.payment_transaction')
    def test_buy_order_mismatch_sets_error(self):
        tx = self._create_webpay_transaction()
        response = self._commit_response(tx, buy_order='OTRA-ORDEN')
        with patch(f'{TRANSACTION_PATH}.commit', return_value=response):
            tx._handle_notification_data('webpay', {'token_ws': self.token})
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.tf_payment_webpay.models.payment_transaction')
    def test_commit_api_error_sets_error(self):
        tx = self._create_webpay_transaction()
        with patch(f'{TRANSACTION_PATH}.commit', side_effect=TransactionCommitError('boom', 422)):
            tx._handle_notification_data('webpay', {'token_ws': self.token})
        self.assertEqual(tx.state, 'error')

    def test_commit_is_not_repeated_for_processed_transaction(self):
        tx = self._create_webpay_transaction()
        tx._set_done()
        with patch(f'{TRANSACTION_PATH}.commit') as commit:
            tx._handle_notification_data('webpay', {'token_ws': self.token})
        commit.assert_not_called()
        self.assertEqual(tx.state, 'done')

    def test_customer_abort_cancels_transaction(self):
        tx = self._create_webpay_transaction()
        with patch(f'{TRANSACTION_PATH}.commit') as commit:
            tx._handle_notification_data('webpay', {
                'TBK_TOKEN': self.token,
                'TBK_ORDEN_COMPRA': tx.webpay_buy_order,
                'TBK_ID_SESION': str(tx.id),
            })
        commit.assert_not_called()
        self.assertEqual(tx.state, 'cancel')

    def test_timeout_cancels_transaction(self):
        tx = self._create_webpay_transaction()
        tx._handle_notification_data('webpay', {
            'TBK_ORDEN_COMPRA': tx.webpay_buy_order,
            'TBK_ID_SESION': str(tx.id),
        })
        self.assertEqual(tx.state, 'cancel')

    def test_refund_request(self):
        self._skip_if_account_payment_is_not_installed()
        tx = self._create_webpay_transaction(state='done')
        with patch(
            f'{TRANSACTION_PATH}.refund',
            return_value={'type': 'NULLIFIED', 'authorization_code': '123456', 'response_code': 0},
        ) as refund:
            refund_tx = tx._send_refund_request(amount_to_refund=5000)
        refund.assert_called_once_with(self.token, 5000)
        self.assertEqual(refund_tx.state, 'done')
        self.assertEqual(refund_tx.amount, -5000)
        self.assertEqual(refund_tx.webpay_token, self.token, "El reembolso guarda el token original.")
        self.assertIn(self.token, refund_tx.state_message)

    def test_return_lookup_ignores_refunds(self):
        """ Un retorno con el token original debe encontrar el pago, no su reembolso. """
        tx = self._create_webpay_transaction()
        self._create_transaction(
            'redirect', reference=f'R-{tx.reference}', amount=-tx.amount, operation='refund',
            source_transaction_id=tx.id, webpay_token=self.token,
        )
        found = self.env['payment.transaction']._get_tx_from_notification_data(
            'webpay', {'token_ws': self.token},
        )
        self.assertEqual(found, tx)

    def test_timeout_logs_original_token(self):
        tx = self._create_webpay_transaction()
        with self.assertLogs('odoo.addons.tf_payment_webpay.models.payment_transaction', 'INFO') as logs:
            tx._handle_notification_data('webpay', {
                'TBK_ORDEN_COMPRA': tx.webpay_buy_order, 'TBK_ID_SESION': str(tx.id),
            })
        self.assertTrue(any(self.token in line for line in logs.output))
