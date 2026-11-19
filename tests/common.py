from odoo.addons.payment.tests.common import PaymentCommon


class WebpayCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.currency = cls._prepare_currency('CLP')
        cls.amount = 15990
        cls.provider = cls._prepare_provider('webpay', update_values={
            'webpay_commerce_code': '597055555532',
            'webpay_api_key': 'DUMMY-API-KEY',
            'available_currency_ids': [(6, 0, cls.currency.ids)],
        })
        cls.token = '01ab' * 16
        cls.create_response = {
            'token': cls.token,
            'url': 'https://webpay3gint.transbank.cl/webpayserver/initTransaction',
        }

    def _create_webpay_transaction(self, **values):
        tx = self._create_transaction(flow='redirect', **values)
        tx.write({'webpay_token': self.token, 'webpay_buy_order': tx.reference})
        return tx

    def _commit_response(self, tx, **overrides):
        return {
            'vci': 'TSY',
            'amount': int(tx.amount),
            'status': 'AUTHORIZED',
            'buy_order': tx.webpay_buy_order,
            'session_id': str(tx.id),
            'card_detail': {'card_number': '6623'},
            'accounting_date': '1119',
            'transaction_date': '2026-11-19T16:00:00.000Z',
            'authorization_code': '1213',
            'payment_type_code': 'VN',
            'response_code': 0,
            'installments_number': 0,
            **overrides,
        }
