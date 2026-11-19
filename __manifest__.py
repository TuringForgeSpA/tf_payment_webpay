{
    'name': 'Payment Provider: WebPay Plus',
    'version': '18.0.1.1.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 340,
    'summary': 'Proveedor de pago chileno: WebPay Plus de Transbank.',
    'description': "Integra WebPay Plus de Transbank en Odoo 18 mediante transbank-sdk.",
    'author': 'César López Aguillón',
    'website': 'https://www.turingforge.cl',
    'depends': ['payment'],
    'data': [
        'views/payment_webpay_templates.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',

        'data/payment_provider_data.xml',
    ],
    'external_dependencies': {
        'python': ['transbank-sdk'],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'license': 'LGPL-3',
}
