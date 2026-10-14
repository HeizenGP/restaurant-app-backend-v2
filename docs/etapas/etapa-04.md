# ETAPA 04 — Modelado del sistema

**Proyecto:** Restaurant App V2 — Chifa ASIA.  
**Estado:** BORRADOR TÉCNICO / PENDIENTE DE REVISIÓN Y APROBACIÓN.  
**Antecedentes:** ETAPAS 01–03 aprobadas expresamente por el usuario el 2026-10-13. La ETAPA 04 fue autorizada para elaboración, pero **no está aprobada**.  
**Fuentes:** [ETAPA 01](etapa-01.md), [ETAPA 02](etapa-02.md), [ETAPA 03 — RN/RNF](etapa-03.md) y [ETAPA 03 — 40 RF](etapa-03-requisitos.md).

## 1. Objetivo y límites

Modelar **casos de uso, actividades y secuencias** desde los módulos M01–M07 y sus **40 RF** para mostrar interacción actor–sistema, condiciones de autorización, excepciones y trazabilidad. Los diagramas no definen arquitectura técnica, entidades SQL, APIs, pantallas ni despliegues; esas decisiones corresponden a etapas posteriores.

### Actores y reglas de autorización

| Actor | Responsabilidad modelada |
|---|---|
| Cliente | Consulta catálogo/mesas, accede como invitado o autenticado, solicita pedidos y revisa estados. |
| Mozo | Registra pedidos presenciales sin segunda aprobación; verifica la mesa y aprueba app-local; sirve pedidos en mesa. |
| Cajero | Registra cobros; no aprueba pedidos ni verifica anticipos por tener solo rol Caja. |
| Administrador | Catálogo, stock, mesas, pedidos por canal externo, aprobación de solicitudes autorizadas y verificación manual/simulada de anticipo. |
| Personal de cocina | Consulta comandas confirmadas y marca En preparación/Listo. |
| Super Administrador | Acceso absoluto. Los roles de una cuenta son acumulativos; el privilegio Super no se representa como una nueva operación. |

Los nombres «Personal autorizado» (CU-01) y «Mozo o Administrador» (SD-02) son **agrupaciones de presentación**, no roles nuevos.

### Simulaciones y exclusiones

- **Anticipo/pago:** registrar y verificar de forma manual o simulada; no cobrar mediante pasarela bancaria, Yape, Plin ni tarjeta real.
- **Llamada/WhatsApp:** comunicaciones externas al sistema; el Administrador registra manualmente el pedido, sin API de WhatsApp.
- **Delivery:** registrar la entrega comercial, sin repartidores, rutas ni GPS.
- **Facturación/SUNAT:** cualquier comprobante de demostración carecerá de validez tributaria. **No se modela todavía como caso de uso**, porque no figura en los 40 RF y en ETAPA 01/03 la exclusión sigue por decidir; si se incluye, primero actualizar RF/CA y alcance.
- **No incluir:** sedes, ingredientes, recetas, almacenes, reservas o promociones no aprobadas.

## 2. Catálogo de diagramas (fuente PlantUML)

**Carpeta dedicada:** [diagramas/etapa-04/](diagramas/etapa-04/).

| ID | Diagrama | Archivo |
|---|---|---|
| **CU-00** | Casos de uso general por actor y módulo | [etapa-04-cu-general.puml](diagramas/etapa-04/etapa-04-cu-general.puml) |
| **CU-01** | M01: acceso, roles y permisos | [etapa-04-cu-m01.puml](diagramas/etapa-04/etapa-04-cu-m01.puml) |
| **CU-02** | M02: catálogo y stock | [etapa-04-cu-m02.puml](diagramas/etapa-04/etapa-04-cu-m02.puml) |
| **CU-03** | M03: mesas | [etapa-04-cu-m03.puml](diagramas/etapa-04/etapa-04-cu-m03.puml) |
| **CU-04** | M04: pedidos y aprobaciones | [etapa-04-cu-m04.puml](diagramas/etapa-04/etapa-04-cu-m04.puml) |
| **CU-05** | M05: cocina y comandas | [etapa-04-cu-m05.puml](diagramas/etapa-04/etapa-04-cu-m05.puml) |
| **CU-06** | M06: caja y anticipo simulado | [etapa-04-cu-m06.puml](diagramas/etapa-04/etapa-04-cu-m06.puml) |
| **CU-07** | M07: atención y cierre | [etapa-04-cu-m07.puml](diagramas/etapa-04/etapa-04-cu-m07.puml) |
| **AD-01** | Actividad: condiciones, errores y cierre | [etapa-04-ad-confirmacion.puml](diagramas/etapa-04/etapa-04-ad-confirmacion.puml) |
| **SD-01** | Secuencia: local por mozo | [etapa-04-sd-local-mozo.puml](diagramas/etapa-04/etapa-04-sd-local-mozo.puml) |
| **SD-02** | Secuencia: local por app | [etapa-04-sd-local-app.puml](diagramas/etapa-04/etapa-04-sd-local-app.puml) |
| **SD-03** | Secuencia: recojo/delivery por app | [etapa-04-sd-app-recojo-delivery.puml](diagramas/etapa-04/etapa-04-sd-app-recojo-delivery.puml) |
| **SD-04** | Secuencia: recojo/delivery por llamada o WhatsApp | [etapa-04-sd-externo-recojo-delivery.puml](diagramas/etapa-04/etapa-04-sd-externo-recojo-delivery.puml) |

**Criterio UML:** los CU modulares identifican trazas de RF, no implican que cada RF sea una función de interfaz. Las relaciones «include» expresan una dependencia obligatoria modelada; «extend» se reserva a los casos de rechazo condicionados. Las secuencias usan un único participante «Sistema» para no fijar una arquitectura antes de ETAPA 05.

## 3. Matriz de trazabilidad RF → caso de uso UML

Cada RF de la ETAPA 03 debe aparecer **exactamente una vez en su diagrama CU modular de origen**. Los diagramas transversales pueden volver a referenciarlo sin crear RF nuevos.

| Módulo | RF incluidos | CU fuente | Apoyo de actividades/secuencias |
|---|---|---|---|
| **M01** | RF-M01-01, RF-M01-02, RF-M01-03, RF-M01-04, RF-M01-05 | CU-01 | — |
| **M02** | RF-M02-01, RF-M02-02, RF-M02-03, RF-M02-04, RF-M02-05, RF-M02-06 | CU-02 | AD-01 |
| **M03** | RF-M03-01, RF-M03-02, RF-M03-03, RF-M03-04 | CU-03 | — |
| **M04** | RF-M04-01, RF-M04-02, RF-M04-03, RF-M04-04, RF-M04-05, RF-M04-06, RF-M04-07, RF-M04-08, RF-M04-09, RF-M04-10, RF-M04-11 | CU-04 | AD-01, SD-01, SD-02, SD-03, SD-04 |
| **M05** | RF-M05-01, RF-M05-02, RF-M05-03, RF-M05-04 | CU-05 | AD-01, SD-01, SD-02, SD-03, SD-04 |
| **M06** | RF-M06-01, RF-M06-02, RF-M06-03, RF-M06-04, RF-M06-05, RF-M06-06 | CU-06 | AD-01, SD-01, SD-02, SD-03, SD-04 |
| **M07** | RF-M07-01, RF-M07-02, RF-M07-03, RF-M07-04 | CU-07 | AD-01, SD-01, SD-02, SD-03, SD-04 |

**Cobertura esperada:** 40/40 RF (5 + 6 + 4 + 11 + 4 + 6 + 4); 7 CU modulares + 1 CU general + 1 actividad + 4 secuencias = **13 fuentes UML**.

## 4. Excepciones y decisiones

| Caso | Comportamiento modelado | Trazas |
|---|---|---|
| Solicitud de app rechazada | Informar rechazo; sin confirmación, sin descuento y sin comanda. | RF-M04-06/07/08; RN-06/07/15 |
| Sin disponibilidad o stock insuficiente | No confirmar, no descontar y no enviar a cocina. | RF-M02-05/06, RF-M04-09; RN-09/10 |
| Sin anticipo confirmado en recojo/delivery | Mantener pendiente, bloquear confirmación/comanda. | RF-M06-02/03/04, RF-M04-09; RN-12/13 |
| Reintento concurrente de confirmación o cobro | Consistencia e idempotencia se requieren en pruebas; no se define mecanismo técnico en UML. | RNF-04/05/10; RN-20 propuesta |
| Saldo pendiente o entrega sin registrar | Bloquear cierre según RN-21 (propuesta, pendiente de validar). | RF-M06-06, RF-M07-04; RN-21 propuesta |
| Cancelación con anticipo | Administrador decide sobre posible devolución; no crear un servicio automatizado de reembolsos. | RN-19 |

## 5. Pendientes que no se deben convertir en supuestos

1. **RN-20 y RN-21:** confirmar formalmente integridad de stock y política de cierre propuesta; la representación UML no implica aprobación.
2. **Responsable de recojo, entrega delivery y cierre:** M07 no asigna expresamente todos los roles; CU-07 y SD-03/04 muestran Administrador como **propuesta**, pendiente de ratificación. No crear un rol de repartidor.
3. **Simulación de comprobantes:** el usuario quiere simular servicios académicos, pero la facturación no tiene RF vigente; formalizar alcance antes de modelarla.
4. **Etapas 01–03:** aprobadas por el usuario el 2026-10-13; las prioridades MoSCoW también quedan aprobadas como línea base documental. La métrica propuesta de RNF-08 sigue pendiente de ratificación específica.

## 6. Validación y criterios de aceptación

- [x] Se identificaron 6 actores y 7 módulos sin arquitectura nueva.
- [x] Se documentó traza uno a uno de los 40 RF a 7 CU modulares.
- [x] Los 4 canales operativos están representados en secuencias; local por mozo y local app diferenciados.
- [x] Se modelaron rechazo, falta de stock, anticipo pendiente y cierre incompleto.
- [x] Se explicitó la simulación académica y se evitó inventar facturación integrada.
- [ ] Ejecutar compilación y renderización REAL de los 13 diagramas PlantUML de la [carpeta de etapa 04](diagramas/etapa-04/) (no basta inspeccionar el texto).
- [ ] Verificar igualdad de archivos compartidos en docs/ de backend/frontend tras integrarlos.
- [ ] Revisar actores propuestos en M07 y ratificar pendientes.
- [ ] Aprobación expresa de ETAPA 04 por el usuario.

**Estado final: ETAPA 04 — EN REVISIÓN / NO APROBADA.** La autorización para elaborarla no sustituye los criterios de aceptación.
