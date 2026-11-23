from . import controllers
from . import models

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(env):
    setup_provider(env, 'webpay')


def uninstall_hook(env):
    env['payment.method']._webpay_set_refund_support('none')
    reset_payment_provider(env, 'webpay')
