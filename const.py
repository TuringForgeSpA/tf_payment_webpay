# Monedas soportadas por WebPay Plus (ISO 4217). WebPay Plus solo opera en pesos chilenos.
SUPPORTED_CURRENCIES = ['CLP']

# Códigos de los métodos de pago activados por defecto al instalar el proveedor.
DEFAULT_PAYMENT_METHOD_CODES = {'webpay'}

# Largo máximo de los campos según la API de WebPay Plus.
BUY_ORDER_MAX_LENGTH = 26
SESSION_ID_MAX_LENGTH = 61

# Tiempo máximo (en segundos) de espera de las llamadas a la API de Transbank.
API_TIMEOUT = 30

# Estado que entrega Transbank al confirmar (commit) una transacción aprobada.
STATUS_AUTHORIZED = 'AUTHORIZED'

# Tipos de respuesta de un reembolso exitoso: reversa (mismo día, monto total) o anulación.
REFUND_TYPES_OK = ('REVERSED', 'NULLIFIED')

# Códigos de tipo de pago entregados por Transbank.
PAYMENT_TYPE_CODES = {
    'VD': 'Venta débito',
    'VN': 'Venta normal (crédito)',
    'VC': 'Venta en cuotas',
    'SI': '3 cuotas sin interés',
    'S2': '2 cuotas sin interés',
    'NC': 'N cuotas sin interés',
    'VP': 'Venta prepago',
}
