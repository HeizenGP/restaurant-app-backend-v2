# ETAPA 01 — Análisis del negocio y alcance

**Proyecto:** Restaurant App V2 — Chifa ASIA  
**Estado:** APROBADA POR EL USUARIO (2026-10-13)  
**Referencia:** `docs/etapas/README.md`. La ETAPA 00 permanece aprobada.

## 1. Negocio, problemática y objetivo

**Negocio confirmado:** Chifa ASIA funcionará como un único restaurante, sin sedes, y atenderá pedidos para consumo en local, recojo en local y delivery. El sistema cubrirá la operación comercial del pedido, pero no la logística del transporte.

**Problemática (redacción propuesta):** Centralizar los pedidos recibidos por distintos canales, reducir errores en su registro y atención, controlar las existencias de productos, coordinar comandas con cocina y registrar cobros. El anticipo para recojo y delivery busca reducir pérdidas por pedidos no completados.

**Objetivo general (propuesto):** Centralizar la gestión del catálogo, stock de productos, mesas, pedidos, cocina, cobros y cierre de entregas de Chifa ASIA, respetando sus modalidades de atención y responsabilidades.

## 2. Actores y permisos confirmados

| Actor | Funciones y límites esenciales |
|---|---|
| **Cliente** | Inicia sesión, se registra o continúa como invitado; consulta catálogo, selecciona modalidad, envía pedidos y consulta su estado. |
| **Mozo** | Atiende mesas, registra pedidos presenciales y los envía a cocina; comprueba la mesa y aprueba o rechaza solicitudes de consumo en local enviadas desde la app. |
| **Cajero** | Accede únicamente al módulo de caja para registrar cobros y las operaciones habilitadas en dicho módulo. No aprueba pedidos. |
| **Administrador** | Gestiona las operaciones del restaurante, usuarios/personal, catálogo y stock; registra pedidos por llamadas o WhatsApp; aprueba solicitudes de la app y verifica anticipos de recojo y delivery. |
| **Personal de cocina** | Recibe comandas autorizadas y actualiza el estado de preparación (en preparación y listo); no aprueba pedidos ni registra cobros. |
| **Super Administrador** | Acceso absoluto a todas las funciones y módulos, sin volver a enumerarlo en cada permiso. |

**Roles múltiples:** Una misma cuenta puede tener varios roles y acumular sus permisos. Ejemplo: Administrador + Cajero. El rol Administrador por sí solo no concede acceso al módulo de Cajero; la verificación del anticipo de recojo/delivery sí pertenece a sus responsabilidades administrativas.

## 3. Modalidades, canales y validación

| Modalidad | Canal | Registro | Revisión y condición antes de cocina | Cierre |
|---|---|---|---|---|
| Consumo en local | Mozo | Mozo | El mozo registra y envía directamente la comanda, sin segunda aprobación. | Servicio en mesa y cobro. |
| Consumo en local | App | Cliente | Mozo o Administrador verifica presencialmente la mesa seleccionada y aprueba. | Servicio en mesa y cobro. |
| Recojo en local | App | Cliente | Administrador aprueba y verifica anticipo del 50 %. | Recojo y cobro del 50 % restante. |
| Recojo en local | Llamada / WhatsApp | Administrador | Registra y valida; verifica anticipo del 50 %. | Recojo y cobro del 50 % restante. |
| Delivery | App | Cliente | Administrador aprueba y verifica anticipo del 50 %. | Entrega y cobro del 50 % restante. |
| Delivery | Llamada / WhatsApp | Administrador | Registra y valida; verifica anticipo del 50 %. | Entrega y cobro del 50 % restante. |

La app ofrece inicio de sesión, registro y acceso como invitado, seguidos de la elección de la modalidad. En consumo en local mediante app, se muestran las mesas para que el cliente seleccione la que ocupa.

Para cada pedido se necesita, según corresponda, modalidad, productos y cantidades, mesa, datos de contacto o dirección de entrega. El detalle exacto de los campos se especificará en la ETAPA 03.

**Delivery:** La aplicación puede registrar el pedido y su cierre, pero no gestiona repartidores, asignaciones, rutas ni seguimiento GPS.

## 4. Funcionamiento principal y reglas

1. El cliente selecciona modalidad y canal de pedido; en la app puede ingresar con cuenta o como invitado.
2. El pedido se registra con productos, cantidades y los datos esenciales de la modalidad.
3. **Pedidos de la app:** requieren aprobación; para consumo en local la realiza el Mozo o Administrador, y para recojo/delivery solo el Administrador. Los pedidos registrados directamente por personal autorizado no necesitan una segunda aprobación.
4. **Consumo en local por app:** antes de aprobar, el personal comprueba presencialmente que el cliente ocupa la mesa indicada.
5. **Recojo y delivery:** el Administrador debe verificar el anticipo obligatorio del **50 % del total** antes de enviar el pedido a cocina, independientemente de si se recibió por app, llamada o WhatsApp.
6. Cuando se confirma el pedido conforme a las condiciones de su modalidad, el sistema **descuenta automáticamente el stock** de los productos solicitados.
7. Cocina recibe la comanda habilitada, registra la preparación y marca el pedido como listo.
8. El pedido se sirve en la mesa, se recoge en el local o se entrega a domicilio, según modalidad; para recojo y delivery se cobra el 50 % restante en la entrega.
9. Se registran los cobros y el cierre del pedido. No se controla el transporte de delivery.
10. Si se cancela un pedido con anticipo, el Administrador decide si corresponde devolverlo. No se diseña ahora un procedimiento automatizado de reembolso.

### Catálogo y stock — decisión confirmada

- Cada producto tiene precio, cantidad de stock y estado de disponibilidad.
- El stock se descuenta automáticamente al **confirmar** un pedido, no al solo enviarlo.
- El Administrador puede actualizar cantidades y cambiar manualmente la disponibilidad.
- No se gestionan ingredientes, recetas ni almacenes.
- La validación detallada frente a stock insuficiente se especificará en la etapa de requisitos; no se inventan excepciones operativas ahora.

## 5. Siete módulos funcionales

| ID | Módulo | Alcance |
|---|---|---|
| **M01** | Usuarios y accesos | Registro, autenticación, acceso invitado, usuarios, roles múltiples y permisos acumulativos. |
| **M02** | Catálogo de productos | Categorías, productos, precios, disponibilidad manual y control de stock por cantidad con descuento automático. |
| **M03** | Gestión de mesas | Distribución, ocupación, disponibilidad y asociación de pedidos de consumo en local. |
| **M04** | Gestión de pedidos | Registro por modalidad y canal, aprobación/rechazo, confirmación y estados del pedido. |
| **M05** | Cocina y comandas | Recepción de comandas autorizadas, preparación y estado listo. |
| **M06** | Caja y pagos | Cobros, registro de anticipos, verificación administrativa del 50 % y saldos pendientes. |
| **M07** | Gestión de entregas | Registro de recojo/entrega y cierre del pedido, sin gestión de repartidores. |

Estos son módulos **funcionales del negocio**; no fijan módulos de código, apps independientes ni arquitectura. Esas decisiones corresponden a la ETAPA 05.

## 6. Alcance, simulaciones y exclusiones

**Incluido y confirmado:** un restaurante; seis actores; roles múltiples; tres modalidades; app con invitado; registro de pedidos por app, mozo, llamada o WhatsApp; aprobación por rol y modalidad; validación presencial de mesa; catálogo y stock de productos; cocina y estados; pagos y anticipos; registro del recojo o entrega.

**Manual / sin integración externa prevista en este alcance:** los pedidos por llamadas y WhatsApp son registrados manualmente por el Administrador; los anticipos son verificados por el Administrador; el transporte de delivery se realiza fuera del sistema. No se asumen integraciones automáticas con WhatsApp, pasarelas ni servicios de mapas.

**Excluido por decisión expresa:** sedes múltiples; gestión de repartidores, asignaciones y rutas; inventario de ingredientes, recetas y almacenes; automatización de devoluciones no solicitada.

**Exclusiones propuestas, aún no aprobadas:** reservas, promociones, fidelización, reportes avanzados y facturación electrónica SUNAT integrada. No incorporar estas capacidades sin confirmación.

## 7. Revisión y límite de la etapa

**Confirmado:** los seis actores, las tres modalidades y sus canales, los permisos principales, los anticipos, la gestión del stock y los siete módulos funcionales están definidos.

**Registro de aprobación:** el usuario aprobó la ETAPA 01 como línea base documental el 2026-10-13, incluida la redacción de problemática y objetivos. Las exclusiones marcadas expresamente como «propuestas» se mantienen pendientes de ratificación específica; no agregar funcionalidades al alcance sin trazabilidad.

**Siguientes etapas:** en ETAPA 02 se diseñará un único flujo principal con ramificaciones y los subflujos indispensables; ETAPA 03 especificará requisitos y criterios de aceptación; ETAPA 04 modelará UML; ETAPA 05 definirá arquitectura.

**Estado final: APROBADA POR EL USUARIO (2026-10-13).** Aprobación del documento de negocio, sin convertir exclusiones todavía propuestas en decisiones confirmadas. Mantener idéntica esta documentación en `develop` de backend y frontend.
