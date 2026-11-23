from unittest import SkipTest

from odoo.modules.registry import Registry
from odoo.tests import tagged
from odoo.tests.common import get_db_name

from odoo.addons.account_payment.tests.common import AccountPaymentCommon


@tagged('post_install', '-at_install')
class TestWebpayAccountPayment(AccountPaymentCommon):
    """ Requiere `account_payment`, que agrega el botón "Reembolsar" al pago contable. """

    @classmethod
    def setUpClass(cls):
        registry = Registry(get_db_name())
        payment_model = registry.get('account.payment')
        if payment_model is None or 'payment_transaction_id' not in payment_model._fields:
            raise SkipTest("account_payment no está instalado.")
        super().setUpClass()
        cls.webpay_method = cls.env.ref('payment.payment_method_webpay')

    def test_refund_is_available_for_webpay_payment_method(self):
        """ El botón "Reembolsar" se muestra cuando `amount_available_for_refund > 0`, lo que exige
        que tanto el proveedor como el método de pago de la transacción admitan reembolsos. """
        self.provider.support_refund = 'partial'
        tx = self._create_transaction(
            'redirect', state='done', payment_method_id=self.webpay_method.id,
        )
        tx._post_process()  # Crea el pago contable.
        self.assertTrue(tx.payment_id)
        self.assertAlmostEqual(tx.payment_id.amount_available_for_refund, tx.amount, places=2)
