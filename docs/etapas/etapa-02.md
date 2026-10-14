# ETAPA 02 — Flujo principal del negocio

**Proyecto:** Chifa ASIA — Restaurant App V2  
**Estado:** BORRADOR EN REVISIÓN / NO APROBADA  
**Alcance:** flujo general para el curso de Aplicaciones Móviles (Ingeniería de Sistemas).  
**Antecedente:** [ETAPA 01](etapa-01.md), en revisión; el usuario autorizó elaborar esta etapa sin aprobar formalmente la anterior.

## Objetivo

Representar **un único flujo de extremo a extremo**, desde que el cliente desea realizar un pedido hasta su entrega, cobro y cierre, diferenciando modalidades, canales y autorizaciones. No diseñar todavía interfaces, requisitos formales, base de datos ni arquitectura.

**Diagrama fuente:** [FL-01 — Flujo principal en PlantUML](etapa-02-flujo-principal.puml).

## 1. Entradas y modalidades

| Modalidad | Canales | Responsable del registro | Condición para continuar |
|---|---|---|---|
| Consumo en local | Mozo | Mozo | Registro directo del pedido y mesa; sin segunda aprobación. |
| Consumo en local | App | Cliente | Verificación presencial de la mesa y aprobación por Mozo o Administrador. |
| Recojo en local | App | Cliente | Aprobación del Administrador y anticipo confirmado del 50 %. |
| Recojo en local | Llamada o WhatsApp | Administrador | Registro y validación del Administrador; anticipo confirmado del 50 %. |
| Delivery | App | Cliente | Aprobación del Administrador y anticipo confirmado del 50 %. |
| Delivery | Llamada o WhatsApp | Administrador | Registro y validación del Administrador; anticipo confirmado del 50 %. |

En la aplicación, el cliente puede **iniciar sesión, registrarse o continuar como invitado** y selecciona su modalidad. Para consumo en local escoge la mesa que ocupa; para delivery facilita una dirección de entrega.

## 2. Recorrido general

1. **Recepción y registro:** identificar modalidad, canal, productos y datos básicos para atender el pedido.
2. **Revisión:** aprobar solicitudes de la app según el rol; los pedidos registrados por personal autorizado no precisan una segunda aprobación.
3. **Disponibilidad:** comprobar el estado del catálogo y la cantidad disponible de los productos. No confirmar pedidos que no puedan atenderse con el stock disponible.
4. **Anticipo cuando corresponda:** para recojo o delivery, el Administrador verifica el **50 % antes de cocina**. Sin anticipo confirmado, el pedido permanece pendiente y no genera comanda para preparar.
5. **Confirmación:** confirmar el pedido y **descontar automáticamente el stock**. No descontarlo por solo enviar una solicitud.
6. **Cocina:** enviar comanda, registrar `en preparación` y `listo`.
7. **Atención final:** servir en mesa o registrar el recojo o entrega a domicilio; no se controlan repartidores ni rutas.
8. **Cobro y cierre:** registrar la cuenta en caja; en recojo y delivery registrar el 50 % restante al entregar. Cerrar el pedido una vez completadas las operaciones que correspondan.

## 3. Participación de los siete módulos

| Módulo | Aporte al flujo |
|---|---|
| M01 — Usuarios y accesos | Acceso de cliente/invitado, roles y autorizaciones acumulativas. |
| M02 — Catálogo de productos | Productos, precios, disponibilidad y descuento de stock al confirmar. |
| M03 — Gestión de mesas | Mostrar y asociar mesa al consumo en local. |
| M04 — Gestión de pedidos | Registro, revisión, aprobación/rechazo, confirmación y estados. |
| M05 — Cocina y comandas | Comandas aprobadas, preparación y pedido listo. |
| M06 — Caja y pagos | Registro de cobros, anticipo y saldo restante. El Cajero no aprueba pedidos. |
| M07 — Gestión de entregas | Registro de recojo o entrega y finalización, sin logística de repartidores. |

**Super Administrador:** tiene acceso completo a todo el sistema. Un usuario puede acumular roles, por ejemplo Administrador + Cajero. Esto no exige repetir al Super Administrador en todas las decisiones.

## 4. Excepciones esenciales

- **Solicitud de app rechazada:** informar al cliente; no confirmar el pedido ni enviar comanda.
- **Producto no disponible o sin stock:** no confirmar el pedido; informar que no puede atenderse en esas condiciones.
- **Anticipo de recojo o delivery no confirmado:** mantener pedido pendiente y **bloquear envío a cocina**.
- **Cancelación con anticipo:** el Administrador decide si corresponde devolverlo. No se modela automatización de devoluciones ni políticas adicionales.

Los detalles de reintentos, correcciones, concurrencia de stock y estados exhaustivos se definirán cuando sean pertinentes, principalmente en la ETAPA 03.

## 5. Límites académicos y operaciones externas

Se centra en la experiencia móvil del cliente y las funciones operativas necesarias para demostrar un pedido completo. Las llamadas y WhatsApp son **canales externos con registro manual** por el Administrador; no existe integración automática con dichos servicios. La comprobación del anticipo es administrativa, sin presuponer pasarela de pagos. Delivery registra la operación comercial, no el traslado físico.

No incorporar sedes, repartidores, GPS, inventario de ingredientes, recetas, almacenes ni funcionalidades secundarias. No crear más diagramas sin una necesidad real del flujo.

## 6. Criterios de revisión

- [x] Un solo flujo principal con **tres modalidades** y sus canales.
- [x] Diferenciar pedidos de Mozo, app, llamada y WhatsApp.
- [x] Respetar aprobaciones y permisos acordados.
- [x] Bloquear cocina sin anticipo del 50 % para recojo/delivery.
- [x] Descontar stock solo tras confirmar el pedido.
- [x] Pasar por preparación, atención/entrega, cobro y cierre.
- [x] Excluir logística de delivery y funcionalidades ajenas al alcance.
- [ ] Comprobar compilación/renderización real del archivo `.puml` con PlantUML.
- [ ] Aprobación expresa del usuario de este flujo.

**Estado final: BORRADOR EN REVISIÓN / NO APROBADA.** No iniciar ETAPA 03 sin validar este flujo.
