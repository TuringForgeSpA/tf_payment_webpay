# Manual de desarrollador: `tf_payment_webpay`

Versión 18.0.1.1.2 · Odoo 18.0 · `transbank-sdk` 6.x · Licencia LGPL-3

Este manual describe la arquitectura del módulo, sus modelos y campos, el flujo de creación, confirmación (commit) y reembolso, el registro en logs y las pruebas automatizadas. Supone conocimiento del framework de proveedores de pago de Odoo (`addons/payment`).

---

## 1. Arquitectura

El módulo es un **proveedor de pago de redirección** al estilo de `payment_paypal` o `payment_mercado_pago`: Odoo crea la transacción en Transbank, envía al cliente al formulario de WebPay con un POST y recibe el retorno en un controlador propio.

```
tf_payment_webpay/
├── __init__.py                     # post_init_hook / uninstall_hook
├── __manifest__.py
├── const.py                        # Constantes de la API (monedas, largos, estados, códigos)
├── controllers/
│   └── main.py                     # WebpayController: /payment/webpay/return
├── data/
│   ├── payment_method_data.xml     # <function> que habilita reembolsos en el método webpay
│   └── payment_provider_data.xml   # Registro del proveedor (noupdate) con credenciales de integración
├── models/
│   ├── payment_method.py           # _webpay_set_refund_support
│   ├── payment_provider.py         # Campos de credenciales, monedas, cliente del SDK
│   └── payment_transaction.py      # create / commit / refund y procesamiento del retorno
├── static/description/             # icon.png, icon.svg
├── tests/
└── views/
    ├── payment_provider_views.xml      # Campos de credenciales en el formulario del proveedor
    ├── payment_transaction_views.xml   # Campos WebPay en el formulario de la transacción
    └── payment_webpay_templates.xml    # redirect_form (POST de token_ws)
```

Dependencias: `payment` en el manifiesto y `transbank-sdk` como dependencia externa de Python. `account_payment` y `sale` no son dependencias, pero son necesarios para el botón *Reembolsar* y para el enlace de pago de la orden de venta.

### 1.1 Diagrama del flujo de pago

```
Cliente            Odoo                                   Transbank
  │  Pagar           │                                        │
  ├─────────────────>│ _get_specific_rendering_values         │
  │                  ├── Transaction.create(buy_order, ──────>│
  │                  │     session_id, amount, return_url)    │
  │                  │<────────────────── {token, url} ───────┤
  │<── redirect_form (POST token_ws a url) ───────────────────│
  ├──────────────────────────────────────────────────────────>│ Formulario WebPay
  │<────────────── retorno a /payment/webpay/return ──────────┤
  ├─────────────────>│ WebpayController                       │
  │                  │ _handle_notification_data('webpay', …) │
  │                  │  ├ TBK_TOKEN      → _set_canceled       │
  │                  │  ├ sin token_ws   → _set_canceled       │
  │                  │  └ token_ws       → Transaction.commit ─>│
  │                  │<──────────────── respuesta del commit ─┤
  │                  │   _webpay_apply_commit_response         │
  │<── redirect /payment/status                               │
```

---

## 2. Constantes (`const.py`)

| Constante | Valor | Uso |
|---|---|---|
| `SUPPORTED_CURRENCIES` | `['CLP']` | Filtra `_get_supported_currencies`. |
| `DEFAULT_PAYMENT_METHOD_CODES` | `{'webpay'}` | Métodos activados por defecto y métodos a los que se habilita el reembolso. |
| `BUY_ORDER_MAX_LENGTH` | `26` | Largo máximo de `buy_order` en la API. |
| `SESSION_ID_MAX_LENGTH` | `61` | Largo máximo de `session_id` (hoy se envía el `id` de la transacción, que no se acerca al límite). |
| `API_TIMEOUT` | `30` | Segundos de espera de las llamadas al SDK. |
| `STATUS_AUTHORIZED` | `'AUTHORIZED'` | Estado esperado en el commit. |
| `REFUND_TYPES_OK` | `('REVERSED', 'NULLIFIED')` | Tipos de respuesta de un reembolso exitoso. |
| `PAYMENT_TYPE_CODES` | `VD`, `VN`, `VC`, `SI`, `S2`, `NC`, `VP` | Descripciones de los tipos de pago (referencia; no se usa en vistas). |

---

## 3. Modelos y campos

### 3.1 `payment.provider` (`models/payment_provider.py`)

| Elemento | Detalle |
|---|---|
| `code` | `selection_add=[('webpay', 'WebPay')]`, `ondelete='set default'`. |
| `webpay_commerce_code` | `Char`, "Código de comercio". `required_if_provider='webpay'`, `groups='base.group_system'`. |
| `webpay_api_key` | `Char`, "API Key secreta". `required_if_provider='webpay'`, `groups='base.group_system'`, se muestra como contraseña. |
| `_compute_feature_support_fields` | Override: `support_refund = 'partial'` para `webpay`. |
| `_get_supported_currencies` | Override: solo CLP. |
| `_get_default_payment_method_codes` | Override: retorna `DEFAULT_PAYMENT_METHOD_CODES`. |
| `_webpay_get_transaction()` | Construye `transbank.webpay.webpay_plus.transaction.Transaction` con `WebpayOptions(commerce_code, api_key, integration_type, timeout=30)`. `state == 'enabled'` → `IntegrationType.LIVE`; cualquier otro estado → `IntegrationType.TEST`. |

El ambiente **se deriva del estado del proveedor**: no hay un campo aparte para elegir integración o producción.

### 3.2 `payment.method` (`models/payment_method.py`)

| Elemento | Detalle |
|---|---|
| `_webpay_set_refund_support(support_refund='partial')` | Escribe `support_refund` en los métodos con código en `DEFAULT_PAYMENT_METHOD_CODES`, incluidos los inactivos (`active_test=False`). |

¿Por qué existe? El método `payment.payment_method_webpay` lo crea el módulo `payment` con `support_refund='none'` y en `noupdate`. `account_payment` calcula `amount_available_for_refund` solo si **el proveedor y el método** admiten reembolsos, así que sin este ajuste el botón *Reembolsar* no aparece.

Se invoca desde:

- `data/payment_method_data.xml`, con un `<function>` **sin `noupdate`**, en cada instalación y actualización.
- `uninstall_hook`, con `'none'`, para dejar el método como estaba.

### 3.3 `payment.transaction` (`models/payment_transaction.py`)

Campos agregados (todos `readonly`, `copy=False`):

| Campo | Tipo | Índice | Origen |
|---|---|---|---|
| `webpay_token` | `Char` "Token WebPay" | Sí | `token` de `create`. En reembolsos se copia el de la transacción origen. |
| `webpay_buy_order` | `Char` "Orden de compra WebPay" | Sí | `_webpay_compute_buy_order()`. En reembolsos se copia la de la origen. |
| `webpay_payment_type_code` | `Char` "Tipo de pago WebPay" | No | `payment_type_code` del commit. |
| `webpay_installments_number` | `Integer` "Número de cuotas WebPay" | No | `installments_number` del commit (0 si no viene). |
| `webpay_card_number` | `Char` "Últimos dígitos de la tarjeta" | No | `card_detail.card_number` del commit. |

Campos estándar que se usan:

- `provider_reference`: `authorization_code` del commit; en reembolsos, el `authorization_code` de la anulación o, si no viene, el `type`.
- `state_message`: mensajes de error, cancelación y confirmación de anulación.

La vista `payment_transaction_views.xml` agrega estos campos después de `provider_reference` en `payment.payment_transaction_form`, visibles solo si `provider_code == 'webpay'`. Cuotas y tarjeta se ocultan si están vacíos.

---

## 4. Flujo de pago en detalle

### 4.1 Creación (`_get_specific_rendering_values`)

Se ejecuta cuando el cliente hace clic en *Pagar* (desde `_get_processing_values`), **no** al generar el enlace.

1. `return_url = url_join(provider.get_base_url(), '/payment/webpay/return')`. `get_base_url()` retorna el parámetro `web.base.url`.
2. `buy_order = _webpay_compute_buy_order()`:
   - Si `len(reference) <= 26`, es la referencia.
   - Si no, `reference[:17] + '-' + sha1(f'{reference}-{id}')[:8]`, que da 26 caracteres.
3. `Transaction.create(buy_order, str(self.id), _webpay_get_amount(), return_url)`. El `session_id` es el `id` de la transacción.
4. `_webpay_get_amount()` = `int(float_round(abs(amount), 0))`. Usa `abs` porque los reembolsos tienen monto negativo.
5. Guarda `webpay_token` y `webpay_buy_order`, y retorna `{'api_url': url, 'token_ws': token}` para el template `redirect_form`, que hace un POST de `token_ws` a la URL de Transbank.
6. Si el SDK lanza `TransbankError`, se registra un *warning* y se lanza `ValidationError("WebPay: No fue posible iniciar el pago con Transbank…")`, que el frontend muestra al cliente.

La transacción queda en `draft`: no se marca como *pending* ni *authorized* antes del pago.

### 4.2 Retorno (`controllers/main.py`)

`WebpayController.webpay_return_from_checkout`:

- Ruta `/payment/webpay/return`, `type='http'`, `auth='public'`, `methods=['GET', 'POST']`, `csrf=False`, `save_session=False`.
- Registra los datos recibidos (`Retorno desde WebPay con los datos: …`).
- Llama a `payment.transaction.sudo()._handle_notification_data('webpay', data)`.
- Si se lanza `ValidationError`, la registra con `_logger.exception` y no la propaga. El cliente siempre termina en `/payment/status`.

`save_session=False` evita que el POST cruzado desde el dominio de Transbank, que llega sin cookies, reemplace la sesión del cliente. La redirección final por GET sí lleva la cookie, así que `/payment/status` encuentra la transacción.

Parámetros que envía Transbank según el caso:

| Caso | Parámetros |
|---|---|
| Aprobado o rechazado | `token_ws` |
| Anulación del cliente | `TBK_TOKEN`, `TBK_ORDEN_COMPRA`, `TBK_ID_SESION` |
| Tiempo agotado | `TBK_ORDEN_COMPRA`, `TBK_ID_SESION` |
| Error en el formulario | `token_ws` junto con `TBK_TOKEN` y los demás |

### 4.3 Búsqueda de la transacción (`_get_tx_from_notification_data`)

1. `token = token_ws or TBK_TOKEN`. Si hay token, busca por `webpay_token`; si no, por `webpay_buy_order = TBK_ORDEN_COMPRA`.
2. Filtra `provider_code = 'webpay'` y **`operation != 'refund'`**. Los reembolsos comparten token y orden de compra con su origen, y sin este filtro el retorno podría resolver al reembolso.
3. Sin token ni orden de compra, o sin resultados: `ValidationError`.

### 4.4 Procesamiento (`_process_notification_data`)

1. **Idempotencia:** si `state` no está en `('draft', 'pending')`, registra un *info* y sale. Evita un segundo commit si el cliente recarga la página.
2. **`TBK_TOKEN` presente** (anulación del cliente o error del formulario): registra token y orden, y `_set_canceled("El pago fue anulado en el formulario de WebPay.")`. No hace commit.
3. **Sin `token_ws`** (tiempo agotado): registra el token **guardado al crear** (Transbank no lo devuelve) y `_set_canceled("Se agotó el tiempo…")`.
4. **Flujo normal:** `Transaction.commit(self.webpay_token)`. Usa el token guardado, no el recibido.
   - `TransbankError` → `_set_error("No fue posible confirmar el pago con Transbank…")`.
   - Si no, registra la respuesta completa y llama a `_webpay_apply_commit_response`.

### 4.5 Validación del commit (`_webpay_apply_commit_response`)

1. Guarda siempre `provider_reference`, tipo de pago, cuotas y últimos dígitos, incluso si el pago fue rechazado.
2. Si `response_code != 0` o `status != 'AUTHORIZED'` → `_set_error("El pago fue rechazado (código X).")`.
3. Si `buy_order` no coincide con `webpay_buy_order`, o `amount` no coincide con `_webpay_get_amount()` → *error* en el log y `_set_error("La respuesta de Transbank no coincide…")`.
4. En otro caso → `_set_done()`. El post-procesamiento estándar de Odoo crea el pago contable y, con *Facturación automática*, la factura conciliada.

---

## 5. Reembolsos (`_send_refund_request`)

Lo invoca `account_payment` desde el asistente *Reembolsar* del pago contable (`payment.refund.wizard` → `payment_transaction_id.action_refund(amount)`).

1. `super()._send_refund_request(amount_to_refund)` crea la transacción `R-<referencia>` con `operation='refund'`, monto negativo y `source_transaction_id`.
2. Copia `webpay_token` y `webpay_buy_order` de la origen al reembolso, para tenerlos a mano en la validación y en soporte.
3. `Transaction.refund(self.webpay_token, abs(monto))`. El token es el de la **transacción origen** (`self`).
4. `TransbankError` → `refund_tx._set_error("Transbank rechazó el reembolso: <mensaje>")` y retorna el reembolso. No propaga la excepción.
5. Si `type in ('REVERSED', 'NULLIFIED')` y `response_code` es 0 (o no viene, como en REVERSED): `provider_reference = authorization_code or type` y `_set_done()` con el mensaje "Anulación TIPO en Transbank. Token: … Autorización: …".
6. Otra respuesta → `_set_error("Respuesta inesperada de Transbank al reembolsar (tipo X).")`.

El SDK usa las credenciales y el ambiente **actuales** del proveedor. Un pago hecho en integración no se puede reembolsar con el proveedor en producción, y al revés.

---

## 6. Hooks y datos

| Elemento | Qué hace |
|---|---|
| `post_init_hook` | `setup_provider(env, 'webpay')`: enlaza los métodos de pago por defecto. |
| `uninstall_hook` | `_webpay_set_refund_support('none')` y `reset_payment_provider(env, 'webpay')`. |
| `payment_provider_data.xml` (`noupdate="1"`) | Proveedor `payment_provider_webpay` con nombre, código, ícono, `redirect_form_view_id`, métodos `payment_method_webpay` y `payment_method_card`, y credenciales de integración. |
| `payment_method_data.xml` (sin `noupdate`) | `<function model="payment.method" name="_webpay_set_refund_support"/>`. |
| `redirect_form` | `<form t-att-action="api_url" method="post">` con `<input name="token_ws">`. |

---

## 7. Logs

Loggers:

- `odoo.addons.tf_payment_webpay.controllers.main`
- `odoo.addons.tf_payment_webpay.models.payment_transaction`

| Nivel | Mensaje | Cuándo |
|---|---|---|
| INFO | `Retorno desde WebPay con los datos: {…}` | Cada retorno, con los parámetros crudos. |
| ERROR | `WebPay: no fue posible procesar los datos de retorno.` (con traza) | `ValidationError` en el retorno (token desconocido, datos vacíos). |
| WARNING | `WebPay: error al crear la transacción REF: MSG` | Falla `create`. |
| INFO | `WebPay: la transacción REF ya fue procesada (estado X).` | Retorno repetido. |
| INFO | `WebPay: pago anulado por el cliente. Transacción REF, token T, orden de compra OC.` | `TBK_TOKEN`. |
| INFO | `WebPay: tiempo agotado en el formulario. Transacción REF, token T, orden de compra OC.` | Timeout. |
| WARNING | `WebPay: error al confirmar la transacción REF: MSG` | Falla `commit`. |
| INFO | `WebPay: respuesta del commit para la transacción REF (token T): {…}` | Respuesta completa del commit. |
| INFO | `WebPay: transacción REF rechazada (response_code=X, status=Y).` | Rechazo. |
| ERROR | `WebPay: datos inconsistentes para REF: orden … monto …` | No coincide la orden o el monto. |
| INFO | `WebPay: solicitud de anulación R-REF de la transacción REF por MONTO (token T, orden de compra OC).` | Antes de `refund`. |
| WARNING | `WebPay: error en la anulación R-REF (token T): MSG` | Falla `refund`. |
| INFO | `WebPay: respuesta de la anulación R-REF (token T): {…}` | Respuesta completa de `refund`. |

Las credenciales nunca se registran. La respuesta del commit incluye solo los últimos 4 dígitos de la tarjeta, como la entrega Transbank.

Para depurar contra Transbank desde `odoo shell`:

```python
tx = env['payment.transaction'].search([('reference', '=', 'S00012')])
tx.provider_id._webpay_get_transaction().status(tx.webpay_token)
```

---

## 8. Pruebas automatizadas

Todas las pruebas usan `post_install` y `-at_install`, y simulan el SDK con `unittest.mock.patch` sobre `transbank.webpay.webpay_plus.transaction.Transaction`. No salen a la red.

```bash
odoo-bin -d <bd> -i tf_payment_webpay --test-tags /tf_payment_webpay --stop-after-init
```

Para incluir las pruebas de reembolso, instala también `account_payment` (por ejemplo, `-i tf_payment_webpay,account_payment`). Sin él, esas pruebas se omiten con `SkipTest`.

| Archivo | Clase | Qué cubre |
|---|---|---|
| `common.py` | `WebpayCommon(PaymentCommon)` | Moneda CLP, monto 15.990, proveedor con credenciales de prueba, token ficticio, respuestas tipo de `create` y `commit`. |
| `test_payment_provider.py` | `TestPaymentProvider` | Reembolso parcial en el proveedor, solo CLP, ambiente según estado (TEST/LIVE), reembolso habilitado en el método `webpay`. |
| `test_payment_transaction.py` | `TestPaymentTransaction` | Formulario de redirección y argumentos de `create`; estado `draft` antes del pago; acortado de `buy_order`; commit autorizado, rechazado, con monto u orden distintos y con error de API; idempotencia; anulación del cliente; timeout; reembolso parcial (llamada, estado, token copiado, mensaje); búsqueda que ignora reembolsos; token en el log del timeout. |
| `test_controller.py` | `TestWebpayController` | Retorno por GET que confirma y redirige a `/payment/status`; retorno por POST con `TBK_TOKEN` que cancela; token desconocido sin error 500. |
| `test_account_payment.py` | `TestWebpayAccountPayment` | Con `account_payment`: el pago contable de una transacción WebPay tiene `amount_available_for_refund` igual al monto (botón *Reembolsar* visible). |

---

## 9. Puntos de extensión y consideraciones

- **Otros productos de Transbank (Oneclick, Mall, Patpass):** agregarlos como códigos nuevos o en módulos aparte. `_webpay_get_transaction` es específico de WebPay Plus.
- **Métodos de pago:** si se agregan códigos a `DEFAULT_PAYMENT_METHOD_CODES`, `_webpay_set_refund_support` también les habilita el reembolso.
- **Moneda:** WebPay Plus solo opera en CLP. No amplíes `SUPPORTED_CURRENCIES` sin un contrato de Transbank que lo permita.
- **Montos:** se redondean a entero. Si el precio tiene decimales, Odoo cobra el monto redondeado, y la validación del commit compara contra ese mismo redondeo.
- **Concurrencia:** el chequeo de estado en `_process_notification_data` cubre los reintentos secuenciales. Dos retornos simultáneos para la misma transacción son poco probables con WebPay Plus, porque Transbank hace un solo retorno por navegador.
- **Versionado:** `18.0.X.Y.Z`. Sube la versión en `__manifest__.py` en cada entrega para que *Actualizar* aplique los datos.
