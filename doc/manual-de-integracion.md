# Manual de integración: WebPay Plus en Odoo 18

Módulo `tf_payment_webpay`, versión 18.0.1.1.2.

Este manual es para quien instala y configura el módulo: el administrador de Odoo o el implementador. Cubre la instalación, la configuración del proveedor, la validación que exige Transbank y el paso a producción. El uso diario está en el *Manual de uso* y el detalle del código, en el *Manual de desarrollador*.

---

## 1. Requisitos

| Requisito | Detalle |
|---|---|
| Odoo | 18.0 (Community o Enterprise). |
| Módulos de Odoo | `payment` (dependencia directa). Para el flujo completo: **Ventas** (`sale`), **Facturación/Contabilidad** y `account_payment`, que agrega el botón *Reembolsar* en los pagos. |
| Python | Paquete `transbank-sdk` (probado con 6.1.0). |
| Red | Salida HTTPS desde el servidor de Odoo hacia Transbank: `webpay3gint.transbank.cl` (integración) y `webpay3g.transbank.cl` (producción). |
| URL pública | Odoo debe ser accesible desde internet por **HTTPS**, porque Transbank devuelve al cliente a `https://<tu-dominio>/payment/webpay/return`. |
| Moneda | **CLP** activa en Odoo. |

---

## 2. Instalación

1. Instala la dependencia en el mismo entorno de Python que usa Odoo:

   ```bash
   pip install transbank-sdk
   ```

2. Descomprime `tf_payment_webpay-18.0.1.1.2.zip` en una ruta incluida en `addons_path`. La carpeta debe llamarse exactamente **`tf_payment_webpay`**.
3. Reinicia el servicio de Odoo.
4. En **Aplicaciones**, haz clic en **Actualizar lista de aplicaciones**, busca *WebPay* (quita el filtro *Aplicaciones*) y haz clic en **Activar**.

Al instalarse, el módulo:

- Crea el proveedor **WebPay** en estado *Deshabilitado*, con las credenciales públicas de integración ya cargadas.
- Le asocia los métodos de pago **WebPay** y **Tarjeta**, y activa **WebPay**.
- Habilita los reembolsos parciales en el método de pago **WebPay**. El módulo `payment` lo crea con reembolsos "No soportado", lo que ocultaría el botón *Reembolsar*.

### Actualizar a una versión nueva

1. Reemplaza la carpeta `tf_payment_webpay` por la de la nueva versión.
2. Reinicia Odoo.
3. En **Aplicaciones**, busca el módulo y elige **Actualizar**, o ejecuta `odoo-bin -d <bd> -u tf_payment_webpay --stop-after-init`.

Los datos del proveedor (credenciales, estado y métodos) están en `noupdate`, así que actualizar **no sobrescribe** tu configuración. El soporte de reembolsos del método WebPay sí se vuelve a aplicar en cada actualización.

### Desinstalar

Al desinstalar, el proveedor vuelve a su estado por defecto y el método de pago WebPay vuelve a "reembolsos no soportados".

---

## 3. Configuración del proveedor

Entra a **Contabilidad (o Facturación) > Configuración > Proveedores de pago** y abre **WebPay**.

### 3.1 Credenciales

En la pestaña **Credenciales**:

| Campo | Integración (pruebas) | Producción |
|---|---|---|
| **Código de comercio** | `597055555532` | El código de 12 dígitos que te entrega Transbank. |
| **API Key secreta** | `579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C` | La llave secreta que te entrega Transbank tras la validación. |

Las credenciales de integración son las **genéricas y públicas** que publica Transbank para WebPay Plus, y ya vienen cargadas al instalar. Solo los usuarios con permiso de **Administración / Ajustes** pueden ver y editar estos campos.

### 3.2 Estado

El estado del proveedor define el **ambiente de Transbank** que se usa:

| Estado | Ambiente de Transbank |
|---|---|
| **Deshabilitado** | No se ofrece a los clientes. |
| **Modo de prueba** | **Integración** (`webpay3gint.transbank.cl`). No se hacen cobros reales. |
| **Habilitado** | **Producción** (`webpay3g.transbank.cl`). Cobros reales. |

> **Cuidado:** no uses las credenciales de integración con el estado *Habilitado*, ni las de producción con *Modo de prueba*. Transbank rechazará las llamadas.

### 3.3 Publicado

El botón de la parte superior del formulario debe decir **Publicado**. Si no está publicado, el proveedor solo es visible para usuarios internos, y un cliente que abre el enlace de pago verá "No hay métodos de pago disponibles".

### 3.4 Métodos de pago

En la pestaña **Configuración**, en *Métodos de pago*, deja activo **WebPay**.

> El módulo también asocia el método **Tarjeta**, pero solo el método **WebPay** queda con reembolsos habilitados. Si un cliente paga con *Tarjeta*, el pago no mostrará el botón *Reembolsar*. Se recomienda dejar activo **solo WebPay**. Las cuotas, el débito y el prepago se eligen dentro del formulario de Transbank, no en Odoo.

### 3.5 Moneda, país y montos

- **Monedas:** el módulo limita el proveedor a **CLP**. Si configuras monedas en el proveedor, CLP debe estar incluida, y la orden o factura debe estar en CLP.
- **Países:** si restringes países, incluye **Chile**.
- **Monto máximo:** si lo configuras, las órdenes por un monto mayor no verán WebPay.
- Los montos se envían a Transbank **redondeados a pesos enteros**, sin decimales.

### 3.6 Compañía

El proveedor pertenece a **una compañía** (campo *Compañía*). Debe ser la misma compañía de las órdenes que se cobrarán. En un entorno multicompañía, duplica el proveedor para cada compañía, con su propio código de comercio.

### 3.7 URL de retorno y `web.base.url`

Al crear la transacción, el módulo le envía a Transbank la URL de retorno:

```
<URL base>/payment/webpay/return
```

La URL base es el parámetro del sistema **`web.base.url`** (`get_base_url()` del proveedor). Por eso:

1. Revisa en **Ajustes > Técnico > Parámetros del sistema** (modo desarrollador) que `web.base.url` sea tu dominio público con **https**, por ejemplo `https://erp.tuempresa.cl`.
2. Para que Odoo no lo cambie cuando un administrador entra por otra dirección, crea el parámetro **`web.base.url.freeze`** con valor `True`.
3. Si Odoo está detrás de un proxy inverso (Nginx, Apache, un balanceador), activa `proxy_mode = True` en el archivo de configuración de Odoo y reenvía los encabezados `X-Forwarded-Host` y `X-Forwarded-Proto`. Sin esto, y sin `web.base.url.freeze`, Odoo puede reescribir `web.base.url` con `http://` o con el host interno cuando un administrador inicia sesión, y la URL de retorno quedaría mal.
4. El servidor debe aceptar **GET y POST** en `/payment/webpay/return` sin bloqueos (WAF, autenticación básica, etc.). Transbank usa POST en las anulaciones y en los tiempos agotados.

### 3.8 Ventas y facturación

- **Facturación automática:** activa **Ventas > Configuración > Ajustes > Facturación automática** para que, al confirmarse el pago, Odoo cree la factura, la publique y la concilie con el pago.
- **Reembolsos:** verifica que `account_payment` esté instalado. Sin él no existe el botón *Reembolsar* en el pago contable.
- **Diario de pagos:** en la pestaña **Configuración** del proveedor, revisa el **Diario de pago** donde se registrarán los cobros de WebPay.

### 3.9 Prueba rápida

1. Deja el proveedor en **Modo de prueba** y **Publicado**.
2. Crea y confirma una orden de venta en CLP por un monto chico.
3. Usa **Acción > Generar enlace de pago** y abre el enlace en una ventana de incógnito.
4. Elige WebPay y paga con una tarjeta de prueba (sección 4.1).
5. Revisa que la transacción quede **Confirmada** y, con Facturación automática, que la factura quede pagada.

---

## 4. Validación con Transbank

Antes de entregarte las credenciales de producción, Transbank pide que pruebes en **integración** una serie de casos y que le informes los datos de cada uno, normalmente el **token** (`token_ws`) y, en algunos casos, la orden de compra. Todos los casos se prueban con el proveedor en **Modo de prueba**.

### 4.1 Datos de prueba de Transbank

| Medio | Número | Resultado |
|---|---|---|
| VISA crédito | `4051 8856 0044 6623`, CVV `123`, cualquier fecha futura | Aprobado |
| Mastercard crédito | `5186 0595 5959 0568`, CVV `123`, cualquier fecha futura | Rechazado |
| Redcompra débito | `4051 8842 3993 7763` | Aprobado |

En la pantalla de autenticación del banco simulado usa el RUT **`11.111.111-1`** y la clave **`123`**.

Transbank actualiza estos datos de vez en cuando; si alguno no funciona, revisa la documentación vigente en transbankdevelopers.cl.

### 4.2 Dónde obtener los tokens

Hay dos fuentes, y conviene usar ambas:

**En el formulario de la transacción.** Con el modo desarrollador activo, entra a **Contabilidad > Configuración > Transacciones de pago** y abre la transacción. El campo **Token WebPay** muestra el token que entregó Transbank al crear la transacción; **Orden de compra WebPay** muestra la orden de compra. En los reembolsos (`R-…`), el token es el de la transacción original, y además aparece en el mensaje de estado.

**En el log del servidor.** Todas las líneas del módulo empiezan con `WebPay:` o con `Retorno desde WebPay`. Por ejemplo:

```bash
grep -E "WebPay|webpay" /var/log/odoo/odoo-server.log
```

El nivel de log debe ser `info` o más detallado (es el valor por defecto de Odoo).

### 4.3 Casos de validación

Para cada caso: crea una orden nueva, genera el enlace de pago, ábrelo y sigue los pasos.

#### Caso 1: transacción aprobada

1. Paga con la **VISA** de prueba (o con débito Redcompra).
2. Resultado en Odoo: transacción **Confirmada**, con *Referencia del proveedor* (código de autorización), tipo de pago y últimos dígitos.
3. Token: campo **Token WebPay**, o en el log:

   ```
   WebPay: respuesta del commit para la transacción S00012 (token 01ab…):
   {'amount': 15990, 'authorization_code': '1213', 'buy_order': 'S00012', ..., 'response_code': 0, 'status': 'AUTHORIZED', ...}
   ```

#### Caso 2: transacción rechazada

1. Paga con la **Mastercard** de prueba.
2. Resultado en Odoo: transacción en **Error**, "El pago fue rechazado (código …)". El mensaje también queda en el historial de la orden.
3. Token: campo **Token WebPay**, o en el log, la línea `respuesta del commit` (con `response_code` distinto de 0) y la línea:

   ```
   WebPay: transacción S00013 rechazada (response_code=-1, status=FAILED).
   ```

#### Caso 3: anulación del cliente en el formulario

1. En el formulario de Transbank haz clic en **Anular compra y volver al comercio**.
2. Transbank vuelve a Odoo con `TBK_TOKEN`, `TBK_ORDEN_COMPRA` y `TBK_ID_SESION`. Odoo **no** confirma la transacción.
3. Resultado en Odoo: transacción **Cancelada**, "El pago fue anulado en el formulario de WebPay."
4. Token: campo **Token WebPay**, o en el log:

   ```
   Retorno desde WebPay con los datos:
   {'TBK_ID_SESION': '57', 'TBK_ORDEN_COMPRA': 'S00014', 'TBK_TOKEN': '01ab…'}
   WebPay: pago anulado por el cliente. Transacción S00014, token 01ab…, orden de compra S00014.
   ```

#### Caso 4: tiempo agotado en el formulario (timeout)

1. Abre el formulario de Transbank y **no hagas nada** hasta que expire (unos minutos; el plazo lo define Transbank). Transbank devuelve al cliente al comercio.
2. Transbank vuelve a Odoo **solo** con `TBK_ORDEN_COMPRA` y `TBK_ID_SESION`, **sin token**. Odoo ubica la transacción por la orden de compra.
3. Resultado en Odoo: transacción **Cancelada**, "Se agotó el tiempo para completar el pago en WebPay."
4. Token: como Transbank no lo devuelve, el módulo registra el token que obtuvo al **crear** la transacción, que es el que debes informar. Está en el campo **Token WebPay** y en el log:

   ```
   Retorno desde WebPay con los datos:
   {'TBK_ID_SESION': '58', 'TBK_ORDEN_COMPRA': 'S00015'}
   WebPay: tiempo agotado en el formulario. Transacción S00015, token 01ab…, orden de compra S00015.
   ```

#### Caso 5: anulación total

1. Paga una orden con la VISA (caso 1).
2. Abre el **pago contable** (desde la factura o en **Contabilidad > Clientes > Pagos**), haz clic en **Reembolsar** y deja el **monto total**.
3. Resultado en Odoo: transacción `R-S00016` **Confirmada**, con el mensaje "Anulación REVERSED (o NULLIFIED) en Transbank. Token: … Autorización: …".
4. Token: el de la transacción **original**. Aparece en el campo **Token WebPay** del reembolso, en su mensaje de estado y en el log:

   ```
   WebPay: solicitud de anulación R-S00016 de la transacción S00016 por 15990 (token 01ab…, orden de compra S00016).
   WebPay: respuesta de la anulación R-S00016 (token 01ab…):
   {'authorization_code': '123456', 'response_code': 0, 'type': 'NULLIFIED', ...}
   ```

#### Caso 6: anulación parcial

1. Igual que el caso 5, pero indica un **monto menor** al pagado.
2. Usa una transacción con **tarjeta de crédito**: Transbank no admite anulaciones parciales en todos los medios de pago.
3. Resultado en Odoo: reembolso **Confirmado** con tipo **NULLIFIED**. El pago original sigue mostrando *Reembolsar* por el saldo restante.
4. Token: igual que en el caso 5.

### 4.4 Si un caso falla

| Síntoma | Causa probable |
|---|---|
| "No hay métodos de pago disponibles" | El proveedor no está publicado, no tiene el método WebPay activo, la orden no está en CLP, o la compañía o el monto máximo no coinciden. |
| "No fue posible iniciar el pago con Transbank" | Credenciales incorrectas para el ambiente elegido, o el servidor no llega a Transbank. Revisa el log: `WebPay: error al crear la transacción …`. |
| Transbank no vuelve a Odoo o devuelve un error 404 | `web.base.url` o el proxy inverso arman una URL de retorno incorrecta (sección 3.7). |
| La transacción queda en *Borrador* tras pagar | El retorno no llegó a Odoo o no se pudo asociar. Busca `Retorno desde WebPay` y `no fue posible procesar los datos de retorno` en el log. |
| No aparece el botón *Reembolsar* | Falta `account_payment`, el pago se registró a mano, se pagó con el método *Tarjeta*, o el módulo no se actualizó tras instalar una versión nueva. |
| "Transbank rechazó el reembolso: Transaction not found" | Transbank no encuentra el token con el código de comercio y el ambiente actuales. Revisa que el reembolso use el mismo ambiente y las mismas credenciales del pago original. |

---

## 5. Paso a producción

1. **Completa la validación** (sección 4) y envía a Transbank los datos que pide. Transbank te entregará el **código de comercio** y la **API Key secreta** de producción.
2. **Confirma las condiciones comerciales** con Transbank, en particular las **cuotas sin interés** (hasta 12 cuotas precio contado), que dependen de tu contrato y no de Odoo.
3. **Verifica la URL pública**: `web.base.url` con `https://` y tu dominio definitivo, `web.base.url.freeze = True`, y `proxy_mode` si corresponde (sección 3.7).
4. **Actualiza el proveedor**:
   1. Pon el proveedor en **Deshabilitado** mientras cambias los datos.
   2. Reemplaza el **Código de comercio** y la **API Key secreta** por los de producción.
   3. Cambia el estado a **Habilitado** y verifica que siga **Publicado**.
5. **Haz un pago real de bajo monto** y revisa que la transacción quede *Confirmada*, que la factura quede pagada y que el cargo aparezca en el portal de Transbank. Si quieres, anúlalo después desde *Reembolsar*.
6. **Avisa al equipo** que los enlaces generados desde ahora cobran de verdad.

> Las transacciones creadas en integración **no existen** en producción. No intentes reembolsar en producción un pago hecho en modo de prueba.

### Volver a integración

Si necesitas volver a probar, cambia el estado a **Modo de prueba** y vuelve a poner las credenciales de integración (sección 3.1). Recuerda dejar luego las de producción.
