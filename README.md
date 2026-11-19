# WebPay Plus para Odoo 18

Proveedor de pago para Odoo 18 que integra WebPay Plus de Transbank (Chile) usando
[transbank-sdk](https://pypi.org/project/transbank-sdk/).

## Instalación

1. Instala la dependencia: `pip install transbank-sdk`.
2. Copia el módulo en tu ruta de addons con el nombre de carpeta `tf_payment_webpay`.
3. Instala el módulo desde Aplicaciones.

## Configuración

En **Facturación/Contabilidad > Configuración > Proveedores de pago > WebPay**:

- **Modo de prueba**: usa el ambiente de integración de Transbank. El módulo viene con las
  credenciales públicas de integración (`597055555532`).
- **Habilitado**: usa el ambiente de producción. Ingresa tu código de comercio y tu API Key.
- La URL de retorno se construye con la URL base de la compañía (`web.base.url`), por lo que debe
  ser pública y con HTTPS: `https://<tu-dominio>/payment/webpay/return`.
- Solo se admite la moneda CLP.

## Flujo

1. Al pagar se crea la transacción en Transbank y el cliente es redirigido al formulario de WebPay.
2. Al volver, el módulo confirma (`commit`) la transacción y valida estado, orden de compra y
   monto antes de marcarla como pagada.
3. Las anulaciones (`TBK_TOKEN`) y los tiempos agotados cancelan la transacción.
4. Los reembolsos totales o parciales se solicitan desde el pago (requiere `account_payment`).

## Tests

```
odoo-bin -d <bd> -i tf_payment_webpay --test-tags /tf_payment_webpay --stop-after-init
```
