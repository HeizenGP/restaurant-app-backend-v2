# ETAPA 02 — Flujo principal del negocio

**Proyecto:** Chifa ASIA — Restaurant App V2  
**Estado:** APROBADA POR EL USUARIO (2026-10-13)  
**Alcance:** flujo general para el curso de Aplicaciones Móviles (Ingeniería de Sistemas).  
**Antecedente:** [ETAPA 01](etapa-01.md), aprobada por el usuario el 2026-10-13.

## Objetivo

Representar **un único flujo de extremo a extremo**, desde que el cliente desea realizar un pedido hasta su entrega, cobro y cierre, diferenciando modalidades, canales y autorizaciones. No diseñar todavía interfaces, requisitos formales, base de datos ni arquitectura.

**Diagrama fuente:** [FL-01 — Flujo principal en PlantUML](etapa-02-flujo-principal.puml).

## 1. Entradas y modalidades

| Modalidad | Canales | Responsable del registro | Condición para continuar |
|---|---|---|---|
| Consumo en local | Mozo | Mozo | Verificar stock, confirmar y enviar directamente a cocina; sin segunda aprobación ni anticipo. |
| Consumo en local | App | Cliente | Mozo o Administrador comprueba la mesa y aprueba; verificar stock, confirmar y enviar a cocina sin anticipo. |
| Recojo en local | App | Cliente | Aprobación del Administrador y anticipo confirmado del 50 %. |
| Recojo en local | Llamada o WhatsApp | Administrador | Registro y validación del Administrador; anticipo confirmado del 50 %. |
| Delivery | App | Cliente | Aprobación del Administrador y anticipo confirmado del 50 %. |
| Delivery | Llamada o WhatsApp | Administrador | Registro y validación del Administrador; anticipo confirmado del 50 %. |

En la aplicación, el cliente puede **iniciar sesión, registrarse o continuar como invitado** y selecciona su modalidad. Para consumo en local escoge la mesa que ocupa; para delivery facilita una dirección de entrega.

## 2. Recorrido general

1. **Recepción y registro:** identificar modalidad, canal, productos y datos básicos para atender el pedido.
2. **Revisión:** aprobar solicitudes de la app según el rol; los pedidos registrados por personal autorizado no precisan una segunda aprobación.
3. **Stock antes de confirmar:** verificar primero la disponibilidad y las cantidades solicitadas para todas las modalidades. Sin stock suficiente, el pedido **no se confirma ni se envía a cocina**.
4. **Consumo en local:** después del registro por el Mozo o de la aprobación de la app, y tras validar el stock, **confirmar el pedido presencial y enviarlo directamente a cocina**, descontando el stock al confirmar; **no requiere anticipo**.
5. **Recojo o delivery:** después del registro o aprobación y la revisión de stock, el Administrador verifica el **anticipo del 50 %**. Solo con el anticipo confirmado se confirma el pedido, se descuenta el stock y se envía a cocina. De lo contrario, permanece pendiente.
6. **Cocina:** recibir la comanda confirmada, registrar `en preparación` y después `listo`.
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
- [x] Verificar stock **antes de confirmar** y descontarlo automáticamente al confirmar.
- [x] Enviar pedidos presenciales confirmados directamente a cocina, sin anticipo.
- [x] Pasar por preparación, atención/entrega, cobro y cierre.
- [x] Excluir logística de delivery y funcionalidades ajenas al alcance.
- [ ] Comprobar compilación/renderización real del archivo `.puml` con PlantUML.
- [x] Aprobación expresa del usuario de este flujo (2026-10-13).

**Estado final: APROBADA POR EL USUARIO (2026-10-13).** La comprobación de compilación/renderización real del archivo PlantUML sigue pendiente; la aprobación no se confunde con esa prueba técnica.
