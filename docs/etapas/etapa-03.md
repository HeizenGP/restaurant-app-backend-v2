# ETAPA 03 — Ingeniería de requisitos

**Proyecto:** Chifa ASIA — Restaurant App V2  
**Estado:** APROBADA POR EL USUARIO (2026-10-13)  
**Organización principal:** siete módulos existentes, no el orden del flujo principal.  
**Referencia para consistencia:** [ETAPA 01](etapa-01.md) y [FL-01](etapa-02-flujo-principal.puml); sus documentos están aprobados por el usuario (2026-10-13).

## Objetivo y entregables

Definir requisitos funcionales (RF), no funcionales (RNF), reglas de negocio (RN), prioridades MoSCoW y criterios de aceptación (CA) **por módulo**. No diseñar base de datos, endpoints, arquitectura ni nuevas funcionalidades.

- [Catálogo detallado de RF y criterios de aceptación](etapa-03-requisitos.md)
- RNF, RN, prioridades y validación: este documento.

## 1. Cobertura por módulos

| Módulo | RF | Must | Should |
|---|---:|---:|---:|
| M01 — Usuarios y accesos | 5 | 5 | 0 |
| M02 — Catálogo de productos | 6 | 6 | 0 |
| M03 — Gestión de mesas | 4 | 3 | 1 |
| M04 — Gestión de pedidos | 11 | 11 | 0 |
| M05 — Cocina y comandas | 4 | 4 | 0 |
| M06 — Caja y pagos | 6 | 6 | 0 |
| M07 — Atención y cierre de entregas | 4 | 4 | 0 |
| **Total** | **40** | **39** | **1** |

**Criterios de aceptación redactados:** 48. Cada RF tiene por lo menos un CA específico.

Las prioridades quedan aprobadas como línea base académica: el núcleo mínimo cubre solicitud, permisos, stock, aprobación, cocina, anticipo, entrega y cobro. Los RF de control de ocupación de mesas se clasifican como Should; no implican quitar la asociación obligatoria entre mesa y pedido.

## 2. Requisitos no funcionales (RNF)

Los criterios deben ser verificables. Valores de rendimiento no aprobados se identifican expresamente como propuestas.

| ID | Atributo | Requisito | Método de verificación | Estado |
|---|---|---|---|---|
| **RNF-01** | Control de acceso | Las operaciones protegidas deben comprobar permisos en el servidor, independientemente de la interfaz. | Prueba de acceso autorizado/no autorizado para cada rol; 100 % de intentos no autorizados rechazados. | Esencial |
| **RNF-02** | Protección de credenciales | Las contraseñas no deben almacenarse en texto claro ni mostrarse durante el inicio de sesión. | Revisión de persistencia y respuesta de autenticación; ningún dato de contraseña en claro. | Esencial |
| **RNF-03** | Comunicación segura | Las comunicaciones que incluyan credenciales o datos personales deben usar HTTPS en un despliegue accesible por Internet. | Verificación de certificado y prueba de acceso protegido. | Esencial |
| **RNF-04** | Integridad del stock | La confirmación y descuento de stock deben mantener consistencia ante solicitudes simultáneas o repetidas. | Prueba de confirmaciones concurrentes: sin stock negativo, sin doble descuento. | Esencial |
| **RNF-05** | Integridad de pagos | Un cobro no debe duplicarse por reintentos y su saldo debe ser correcto. | Reintento controlado de registro: una sola operación contabilizada; saldo consistente. | Esencial |
| **RNF-06** | Gestión de errores | La app debe informar errores de permisos, stock, aprobación y pagos de forma comprensible. | Probar los cuatro casos: mensaje visible y sin cierre indebido. | Esencial |
| **RNF-07** | Experiencia móvil | El flujo principal debe poder completarse desde teléfonos Android con pantallas habituales. | Prueba manual del pedido completo en al menos un teléfono Android físico; tamaños adicionales pendientes de acordar. | Esencial |
| **RNF-08** | Rendimiento | El catálogo y la consulta de pedidos deben responder de manera aceptable en una demostración académica. | Propuesta por validar: percentil 95 de las consultas <= 3 s con 20 usuarios concurrentes en entorno de prueba. | Propuesta |
| **RNF-09** | Trazabilidad de operaciones | Deben poder identificarse actor y momento de aprobación, cambio de stock, anticipo y cobro. | Pruebas de auditoría sobre los cuatro tipos de operación. | Esencial |
| **RNF-10** | Recuperación ante desconexión | Si falla la comunicación al enviar o confirmar, el sistema no debe informar éxito sin confirmación del servidor. | Simulación de corte de conexión: mensaje de error y sin doble pedido al reintentar. | Esencial |
| **RNF-11** | Mantenibilidad | Las funcionalidades de los siete módulos deben ser verificables con pruebas aisladas y de integración. | Pruebas automatizadas para reglas críticas de permisos, stock, aprobación y anticipo. | Esencial |

## 3. Reglas de negocio (RN)

| ID | Regla | Módulos vinculados | Estado |
|---|---|---|---|
| **RN-01** | El negocio cuenta con un único restaurante; no maneja sedes. | M03/M04 | Confirmada |
| **RN-02** | Los clientes pueden usar la app con cuenta o como invitados. | M01 | Confirmada |
| **RN-03** | Los roles pueden acumularse; Super Administrador posee todos los permisos. | M01 | Confirmada |
| **RN-04** | El Cajero solo utiliza Caja salvo que tenga otros roles; no aprueba pedidos. | M01/M06 | Confirmada |
| **RN-05** | El Mozo registra pedidos presenciales sin segunda aprobación. | M04 | Confirmada |
| **RN-06** | Los pedidos de app para consumo local los aprueba Mozo o Administrador después de verificar la mesa. | M03/M04 | Confirmada |
| **RN-07** | Los pedidos de app para recojo/delivery los aprueba el Administrador. | M04 | Confirmada |
| **RN-08** | El Administrador registra los pedidos recibidos por llamada o WhatsApp. | M04 | Confirmada |
| **RN-09** | Antes de confirmar un pedido se debe verificar disponibilidad y stock suficiente. | M02/M04 | Confirmada |
| **RN-10** | El stock se descuenta automáticamente al confirmar, nunca solo por crear una solicitud. | M02/M04 | Confirmada |
| **RN-11** | El Administrador puede cambiar stock y disponibilidad de cada producto. | M02 | Confirmada |
| **RN-12** | Todo pedido de recojo/delivery requiere anticipo confirmado del 50 % antes de cocina. | M04/M06 | Confirmada |
| **RN-13** | El Administrador verifica anticipos; esto no le concede rol Cajero. | M01/M06 | Confirmada |
| **RN-14** | Los pedidos presenciales no requieren anticipo antes de cocina. | M04/M06 | Confirmada |
| **RN-15** | Solo pedidos confirmados generan comandas habilitadas para cocina. | M04/M05 | Confirmada |
| **RN-16** | El personal de cocina gestiona los estados En preparación y Listo. | M05 | Confirmada |
| **RN-17** | En recojo/delivery, el 50 % restante se cobra al entregar el pedido. | M06/M07 | Confirmada |
| **RN-18** | El sistema no asigna repartidores ni sigue rutas de delivery. | M07 | Confirmada |
| **RN-19** | El Administrador decide si corresponde devolver un anticipo cancelado; no se automatiza el reembolso. | M06 | Confirmada |
| **RN-20** | No se debe permitir stock negativo ni repetir un descuento por la misma confirmación. | M02 | Propuesta técnica para validar |
| **RN-21** | El cierre del pedido requiere entrega o servicio registrado y saldo igual a cero. | M06/M07 | Propuesta funcional para validar |

Las reglas confirmadas provienen de decisiones de negocio de esta conversación; RN-20 y RN-21 son propuestas necesarias para mantener integridad o completar el cierre, no aprobaciones implícitas.

## 4. Prioridades y alcance

- **Must Have:** 39 RF indispensables para demostrar el ciclo del pedido y los controles esenciales.
- **Should Have:** 1 RF para mejorar operación, sin impedir la entrega básica.
- **Could Have:** ninguno propuesto por ahora; se evita inflar el proyecto.
- **Won't Have en esta versión:** sedes múltiples, gestión de repartidores y rutas, ingredientes/recetas/almacenes, integración automática con WhatsApp o pasarelas de pago. Reservas, promociones, fidelización, reportes avanzados y facturación electrónica siguen como exclusiones **propuestas**, no confirmadas.

Las prioridades quedan aprobadas para el alcance documental de ETAPA 03. Podrán revisarse si cambia el tiempo del curso o la demostración esperada; no equivalen a funcionalidades ya implementadas.

## 5. Trazabilidad modular

| Módulo | Requisitos funcionales | Reglas relacionadas | Capacidades del sistema |
|---|---|---|---|
| M01 | RF-M01-01 a RF-M01-05 | RN-02, RN-03, RN-04, RN-13 | Usuarios y accesos |
| M02 | RF-M02-01 a RF-M02-06 | RN-09, RN-10, RN-11, RN-20 | Catálogo de productos |
| M03 | RF-M03-01 a RF-M03-04 | RN-01, RN-06 | Gestión de mesas |
| M04 | RF-M04-01 a RF-M04-11 | RN-01, RN-05, RN-06, RN-07, RN-08, RN-09, RN-10, RN-12, RN-14, RN-15 | Gestión de pedidos |
| M05 | RF-M05-01 a RF-M05-04 | RN-15, RN-16 | Cocina y comandas |
| M06 | RF-M06-01 a RF-M06-06 | RN-04, RN-12, RN-13, RN-14, RN-17, RN-19, RN-21 | Caja y pagos |
| M07 | RF-M07-01 a RF-M07-04 | RN-17, RN-18, RN-21 | Atención y cierre de entregas |

**Comprobaciones cruzadas con FL-01 (no fuente primaria):** acceso invitado; canales por modalidad; aprobación del Mozo/Administrador en local y solo Administrador en app recojo/delivery; verificación de stock **antes** de confirmación; anticipo del 50 % antes de cocina para recojo/delivery; comanda únicamente confirmada; cobro y cierre sin logística de repartidores.

## 6. Pendientes para validar, sin abrir funciones secundarias

1. **Resuelto (2026-10-13):** el usuario aprobó los RF, criterios, prioridades Must/Should y el alcance documental de esta etapa.
2. Definir si la política de **cierre con entrega registrada y saldo cero** (RN-21) se aprueba.
3. Confirmar el objetivo de rendimiento RNF-08 o dejarlo como referencia de prueba académica.
4. Ratificar las exclusiones aún propuestas en la ETAPA 01.

Estos puntos de decisión específicos siguen documentados, pero no anulan la aprobación del documento de ETAPA 03. Su resolución requerirá confirmación cuando corresponda. La política de devoluciones se limita a decisión del Administrador, sin crear un módulo de reembolsos.

## 7. Validación

- [x] Identificadores RF, RNF, RN y CA diferenciados.
- [x] Requisitos redactados por los **7 módulos existentes**.
- [x] Cada RF cuenta con criterio de aceptación observable.
- [x] Reglas críticas de roles, stock, pagos y comandas representadas.
- [x] Prioridades iniciales justificadas por un proyecto académico de aplicaciones móviles.
- [x] Sin módulos adicionales ni arquitectura o implementación.
- [x] Revisión y aprobación expresa del usuario (2026-10-13).
- [x] Estados de aprobación formal de ETAPA 01 y ETAPA 02 ratificados por el usuario (2026-10-13).

**Estado final: ETAPA 03 APROBADA POR EL USUARIO (2026-10-13).** ETAPA 04 elaborada por autorización previa, pendiente de su propia aprobación. Los pendientes específicos no se dan por resueltos sin acuerdo expreso.
