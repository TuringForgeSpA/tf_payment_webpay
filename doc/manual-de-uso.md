# Manual de uso: pagos con WebPay Plus en Odoo 18

Módulo `tf_payment_webpay`, versión 18.0.1.1.2.

Este manual es para quienes trabajan con ventas, cobranza o contabilidad en Odoo. Explica cómo cobrar una orden de venta con WebPay, qué ve el cliente, cómo queda registrado el pago y cómo hacer un reembolso. La instalación y la configuración técnica están en el *Manual de integración*.

---

## 1. Resumen del flujo

1. Creas un **presupuesto** y se lo envías al cliente.
2. Cuando el cliente lo aprueba, lo **confirmas** y se convierte en **orden de venta**.
3. Desde la orden generas un **enlace de pago** y se lo envías al cliente.
4. El cliente abre el enlace, elige **WebPay** y paga en el formulario de Transbank, con débito, crédito o prepago. Con crédito puede pagar **hasta en 12 cuotas**.
5. Transbank devuelve al cliente a Odoo, Odoo confirma el pago y, si la **Facturación automática** está activa, genera la **factura** y la deja **pagada**.

---

## 2. Antes de empezar

Verifica con quien administra Odoo que se cumpla lo siguiente (solo una vez):

- El proveedor **WebPay** está en **Habilitado** (producción) o en **Modo de prueba** (integración) y está **publicado**.
- La orden de venta está en **pesos chilenos (CLP)**. WebPay no acepta otras monedas, así que en otras monedas WebPay no aparece como opción.
- La opción **Ventas > Configuración > Ajustes > Facturación automática** está activa, si quieres que la factura se genere y quede pagada sola.
- Para hacer reembolsos desde Odoo, el módulo **account_payment** está instalado (viene con Contabilidad/Facturación) y tu usuario tiene permisos de facturación.

---

## 3. Cobrar una orden de venta

### 3.1 Crear y confirmar la orden

1. Entra a **Ventas > Pedidos > Presupuestos** y crea el presupuesto con su cliente, productos y precios en CLP.
2. Envíalo al cliente con **Enviar por correo electrónico**, si corresponde.
3. Cuando el cliente lo apruebe, haz clic en **Confirmar**. El presupuesto pasa a ser una **orden de venta** (por ejemplo, `S00012`).

### 3.2 Generar el enlace de pago

1. En la orden de venta, abre el menú **Acción** (ícono de engranaje) y elige **Generar enlace de pago**.
2. En la ventana revisa el **monto**. Por defecto es el saldo pendiente de la orden; puedes bajarlo si quieres cobrar un abono.
3. Copia el enlace con el botón de copiar y envíaselo al cliente por correo, WhatsApp u otro medio.

> **El enlace no vence por sí solo.** La transacción en Transbank se crea recién cuando el cliente hace clic en *Pagar*, así que el cliente puede abrir el enlace días después. Lo que sí tiene un plazo es el formulario de Transbank una vez abierto (ver 3.4).

### 3.3 Lo que ve el cliente

1. Abre el enlace y ve el resumen de la orden con el monto a pagar.
2. Elige **WebPay** y hace clic en **Pagar**.
3. Es redirigido al formulario de WebPay de Transbank, donde elige el medio de pago (débito, crédito o prepago) e ingresa sus datos.
4. Si paga con **tarjeta de crédito**, en ese mismo formulario puede elegir pagar **en cuotas, hasta 12**.
5. Al terminar, Transbank lo devuelve a Odoo y ve la página de estado del pago.

### 3.4 Sobre las cuotas

- Las cuotas **no se configuran en Odoo**. El cliente las elige en el formulario de Transbank; Odoo envía solo el monto total.
- Que las cuotas sean **sin interés** ("precio contado") es una **condición comercial que se contrata con Transbank** para tu código de comercio. Si tu contrato no la incluye, el banco del cliente puede aplicar intereses.
- Después del pago, Odoo guarda en la transacción el **tipo de pago** y el **número de cuotas** que eligió el cliente (ver sección 5).

### 3.5 Resultado del pago

| Lo que pasa en WebPay | Estado de la transacción en Odoo | Qué pasa con la orden |
|---|---|---|
| El pago es aprobado | **Confirmada** | Queda pagada. Con Facturación automática se crea la factura, se publica y queda pagada. |
| El pago es rechazado por el banco | **Error**, con el mensaje "El pago fue rechazado (código …)" | Sigue pendiente de pago. El mensaje queda en el historial de la orden. Puedes reenviar el mismo enlace. |
| El cliente hace clic en "Anular compra y volver al comercio" | **Cancelada** ("El pago fue anulado en el formulario de WebPay.") | Sigue pendiente de pago. |
| El cliente deja el formulario abierto hasta que expira | **Cancelada** ("Se agotó el tiempo para completar el pago en WebPay.") | Sigue pendiente de pago. |
| Odoo no pudo confirmar con Transbank (falla de comunicación) | **Error** ("No fue posible confirmar el pago con Transbank…") | Revisa el caso con el administrador antes de volver a cobrar, para evitar un doble cobro. |

Si el cliente recarga la página de retorno, Odoo no vuelve a confirmar el pago: una transacción ya procesada no se procesa dos veces.

---

## 4. La factura pagada

Con **Facturación automática** activa, al confirmarse el pago Odoo:

1. Crea la factura de la orden y la publica.
2. Crea el **pago contable** ligado a la transacción de WebPay.
3. Concilia el pago con la factura, que queda en estado **Pagado**.

Para verlo, abre la orden de venta y usa el botón inteligente **Factura**. Desde la factura puedes llegar al pago en la sección de pagos, al pie de la factura.

Sin Facturación automática, el pago queda registrado igual, pero tienes que crear la factura manualmente desde la orden (**Crear factura**) y conciliarla con el pago.

---

## 5. Dónde ver los datos de WebPay de un pago

Los datos que entrega Transbank se guardan en la **transacción de pago**:

1. Activa el **modo desarrollador** (Ajustes > Activar el modo desarrollador).
2. Entra a **Contabilidad > Configuración > Transacciones de pago** (en Odoo 18 puede aparecer bajo el grupo *Pagos en línea*) y abre la transacción. También puedes llegar desde el pago contable, en el campo **Transacción de pago**.

En el formulario de la transacción, junto a la referencia del proveedor, verás:

| Campo | Qué contiene |
|---|---|
| **Referencia del proveedor** | El código de autorización que entrega Transbank. |
| **Token WebPay** | El identificador único de la transacción en Transbank. Es el dato que pide Transbank para revisar o anular un pago. |
| **Orden de compra WebPay** | La orden de compra enviada a Transbank. Normalmente es la referencia de la transacción (por ejemplo, `S00012` o `S00012-1`). |
| **Tipo de pago WebPay** | El código del tipo de pago (ver tabla siguiente). |
| **Número de cuotas WebPay** | Solo aparece si el pago fue en cuotas. |
| **Últimos dígitos de la tarjeta** | Los últimos 4 dígitos de la tarjeta. |

Códigos de tipo de pago:

| Código | Significado |
|---|---|
| `VD` | Venta débito |
| `VN` | Venta normal (crédito, sin cuotas) |
| `VC` | Venta en cuotas |
| `SI` | 3 cuotas sin interés |
| `S2` | 2 cuotas sin interés |
| `NC` | N cuotas sin interés |
| `VP` | Venta prepago |

---

## 6. Reembolsos (anulaciones)

Puedes devolver un pago **completo** o **parcialmente** desde Odoo. Odoo le pide a Transbank que anule el cobro en la tarjeta del cliente.

### 6.1 Cómo hacer un reembolso

1. Abre el **pago contable**: **Contabilidad > Clientes > Pagos**, o desde la factura pagada.
2. Haz clic en **Reembolsar**, arriba del formulario.
3. Indica el **monto del reembolso**: el total o una parte.
4. Confirma con **Reembolsar**.

Odoo crea una transacción de reembolso con referencia `R-<referencia original>` (por ejemplo, `R-S00012`):

- Si Transbank lo acepta, el reembolso queda **Confirmado** con el mensaje "Anulación REVERSED/NULLIFIED en Transbank. Token: … Autorización: …", y Odoo registra un pago de salida por ese monto.
- Si Transbank lo rechaza, queda en **Error** con el motivo: "Transbank rechazó el reembolso: …".

Transbank responde con uno de estos tipos:

- **REVERSED** (reversa): ocurre cuando se anula el monto total el mismo día contable del pago. Para el cliente es como si el cargo nunca hubiera existido.
- **NULLIFIED** (anulación): el resto de los casos, incluidos los reembolsos parciales. La devolución se refleja en el estado de cuenta del cliente según los plazos de su banco.

### 6.2 Cosas a tener en cuenta

- El botón **Reembolsar** aparece solo si el pago está ligado a una transacción de WebPay **y** quedan montos por reembolsar. Un pago registrado a mano no lo muestra.
- El reembolso **no crea una nota de crédito**. Si corresponde anular la factura en el SII, emite la nota de crédito desde la factura (**Nota de crédito**) y concíliala con el pago de salida.
- Transbank pone restricciones según el tipo de tarjeta y el plazo transcurrido (por ejemplo, las anulaciones parciales no siempre están disponibles para débito). Si Transbank rechaza el reembolso, el mensaje de error lo indica.
- Puedes hacer varios reembolsos parciales mientras la suma no supere el monto pagado.

---

## 7. Preguntas frecuentes

**El cliente dice que no ve WebPay al abrir el enlace ("No hay métodos de pago disponibles").**
Revisa que la orden esté en CLP. Si lo está, pide al administrador que revise la configuración del proveedor (estado, publicado, métodos de pago, compañía y monto máximo).

**El cliente pagó, pero la orden sigue sin pagar.**
Abre la transacción (sección 5). Si está en **Error** por "No fue posible confirmar el pago con Transbank", el cobro puede haberse hecho o no en Transbank; pide al administrador que lo revise con el token antes de volver a cobrar.

**¿Puedo cobrar en dólares?**
No. WebPay Plus solo opera en pesos chilenos.

**¿Puedo cobrar un abono y luego el saldo?**
Sí. Al generar el enlace, cambia el monto. Cada pago queda como una transacción distinta.
