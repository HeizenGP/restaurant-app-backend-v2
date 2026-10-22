# ETAPA 08 — Plan de implementación backend | Chifa ASIA

**Estado:** 08.00–08.10 verificados técnicamente en backend; ETAPA 08 pendiente de aprobación final expresa del usuario.

**Rama:** `develop` · **Único repositorio editable:** `restaurant-app-backend-v2` · **Workspace compartido Codex/AGY:** `~/proyectos/restaurant-app-v2/restaurant-app-backend-v2` (`/home/heizen27/proyectos/restaurant-app-v2/restaurant-app-backend-v2`). **Frontend intocable en ETAPA 08.**  
**Fuentes de verdad:** `AGENTS.md`, `docs/etapas/README.md`, `docs/etapas/etapa-03-requisitos.md` (40 RF / 48 CA), `etapa-03.md` (RN/RNF), `etapa-04.md` (CU), `etapa-05.md` (arquitectura), `etapa-06.md` (BD), `etapa-07.md` (infraestructura). Consultar solo fragmentos pertinentes.  
**Progreso vivo / punto de reanudación:** [`etapa-08-progreso.md`](etapa-08-progreso.md). **No confundir este plan con evidencia de funcionalidades terminadas.**

## 1. Objetivo y límites

Implementar **40/40 RF** de los módulos M01–M07 como casos de uso, endpoints REST y pruebas trazables a sus **48 criterios de aceptación**, reutilizando FastAPI, PostgreSQL 17, SQLAlchemy Async, Alembic, Docker y las 14 tablas configuradas en ETAPA 07. Mantener monolito modular + arquitectura hexagonal + Vertical Slicing, prefijo `/api/v1`, JWT/Argon2, idempotencia y contratos públicos entre módulos.

**Fuera de alcance:** Flutter/UI/Figma (ETAPAS 09–10), microservicios, pasarelas reales, SUNAT, automatización WhatsApp, SMS/push externos, GPS/rutas/repartidores, inventario de ingredientes, comprobantes sin RF/CA autorizados, cambios de negocio no aprobados. No remodelar la BD aprobada por conveniencia. Migraciones incrementales solo si son imprescindibles y justificadas.

**Decisiones abiertas:** RN-20 y RN-21 requieren ratificación de texto (sin deshacer lo ya exigido por RF/RNF); RNF-08 no posee cifra aprobada; emisión de comprobantes simulados no tiene RF/CA. Bloquear **solo el caso de uso afectado**, registrarlo en progreso y solicitar decisión; jamás inventarla. **Permisos M07 aprobados expresamente para 08.09:** Mozo registra servido en mesa; Administrador registra recojo en tienda, entrega comercial de delivery y cierre; Super Administrador conserva acceso total. Esto no concede al Administrador permiso de Cajero ni incorpora repartidores/rutas.

## 2. Coordinación Codex + Antigravity y ahorro de tokens

- **Mismo workspace local, un escritor activo por bloque:** Codex y AGY operan sobre `/home/heizen27/proyectos/restaurant-app-v2/restaurant-app-backend-v2` en `develop`. Uno implementa y el otro revisa secuencialmente; no editar archivos simultáneamente. No hace falta transferir código entre máquinas: ambos ven los mismos archivos locales, incluidos cambios sin commit. Antes de ceder el turno, actualizar el checkpoint y asegurar que no queden comandos/procesos de escritura del agente anterior.
- **Skill obligatoria para cada slice:** backend `.agents/skills/restaurant-fastapi-slice/SKILL.md`; respetar las reglas `AGENTS.md`. **No activar Skill Flutter** antes de ETAPA 10. Seleccionar RF/CA y CU puntuales, no cargar todos los documentos ni ambas copias de `docs/` en contexto.
- **Inicio de sesión mínima:** ubicarse en el workspace backend indicado, confirmar rama `develop` y `git status`; leer `AGENTS.md` + **progreso** + bloque activo de **este plan** + RF/CA y Skill específicos. Revisar archivos locales existentes; no confiar en memoria conversacional ni asumir pruebas ejecutadas.
- **Fin de bloque:** actualizar *solo* `etapa-08-progreso.md` con RF/CA realmente validados, rutas/casos de uso, comandos y resultado, bloqueos, archivos tocados y próxima acción concreta. Marcar `HECHO` solo con evidencia; si se agotan tokens, registrar `EN CURSO` y cómo continuar.
- **Control de versiones y alcance:** no hacer `commit`, `push` ni `merge` sin autorización. Durante ETAPA 08 se edita **exclusivamente el backend**, incluidos `docs/` y `AGENTS.md`; no editar ni sincronizar archivos con el frontend. El estado del workspace local prevalece sobre una copia remota aún no publicada.
- **Orden por dependencias**, no por apariencia de completitud. Un RF cruzado no se marca `HECHO` hasta probar su integración real. No prometer 40/40 si faltan decisiones aprobatorias.

## 3. Orden oficial de bloques y responsables sugeridos

| Bloque | Implementador / revisor | Objetivo y RF propietarios | Dependencia / puerta de salida |
|---|---|---|---|
| **08.00 — Línea base** | **Codex / AGY** | Auditar ETAPA 07, `/health`, ORM, Alembic `20261021_0002`, pruebas, Swagger, pendientes; acordar contratos mínimos sin implementar negocio | Inventario y línea base registrados; no tocar ETAPAS aprobadas |
| **08.01 — M01 Accesos** | **Codex / AGY** | **RF-M01-01…05**: registro/login, sesión invitado, JWT/Argon2, revocación/expiración, seis roles acumulativos, superadmin y permisos | Unitarias + integración auth; 401/403 y secretos seguros |
| **08.02 — M02 Catálogo base** | **AGY / Codex** | **RF-M02-01…04**: categorías, productos, precio, existencia manual, habilitación, movimiento auditado | Autorización admin, catálogo cliente, stock no negativo; **M02-05/06 esperan 08.07** |
| **08.03 — M03 Mesas** | **Codex / AGY** | **RF-M03-01…04**: registro/distribución, consulta, ocupación y vínculo preparado con local | Mozo/Admin autorizados según regla; **solo Administrador libera**; asociación real se prueba con M04 |
| **08.04 — M04 Solicitudes** | **AGY / Codex** | **RF-M04-01,02,04…08,11**: modalidades, canales, carrito a snapshot inmutable, total, solicitudes, verificación presencial y aprobaciones/rechazo | Validar invitado, mesa/dirección, actor, canal y estados; **M04-03/09 esperan 08.07, M04-10 espera 08.09** |
| **08.05 — M06 Anticipo** | **Codex / AGY** | **RF-M06-02…04**: 50 % redondeado al céntimo superior, verificación exclusiva Admin/Superadmin, pago simulado único, lectura para confirmación | Enviar a cocina permanece bloqueado hasta confirmar pedido; verificar anticipo no concede rol Cajero |
| **08.06 — M05 Cocina base** | **AGY / Codex** | **RF-M05-02…04**: lectura de contenido por comanda, RECEIVED → PREPARING → READY, declaración manual de todos los ítems preparados | Cocina únicamente con permiso; **M05-01 queda pendiente de 08.07** |
| **08.07 — Confirmación transversal** | **Codex / AGY** | **RF-M04-03,09 + RF-M02-05,06 + RF-M05-01**. Integrar M04 ↔ M02 ↔ M06 ↔ M05 con **una UoW SQLAlchemy** y puertos públicos | Confirmar local Mozo directo, app local tras verificación, pickup/delivery con anticipo previo; comanda única, stock exacto, rollback, concurrencia/idempotencia probadas |
| **08.08 — M06 Caja/cobros** | **AGY / Codex** | **RF-M06-01,05,06**: cobros parciales/último saldo, consulta por pedido, múltiples pagos, no sobrepago; medios simulados | Solo Cajero/Superadmin o rol Cajero acumulado; probar dos pagos simultáneos e idempotencia; bloquear cierre con deuda |
| **08.09 — M07 Cumplimiento/cierre** | **Codex / AGY** | **RF-M07-01…04 + RF-M04-10**: servido, recojo, entrega comercial, cierre, seguimiento compuesto | Mesa/recogida/delivery según modalidad; `READY` y saldo cero; permisos M07 aprobados y registrados en §1 |
| **08.10 — Cierre integral** | **AGY / Codex** | Trazabilidad **40 RF / 48 CA**, respuestas HTTP, OpenAPI, auditoría, pruebas negativas, carrera concurrencial, revisión de seguridad | Sin RF pendiente oculto; reporte veraz de pruebas y bloqueos; **solicitar aprobación al usuario** |

> **Conteo sin duplicados:** M01 5 (08.01), M02 4+2 (08.02/08.07), M03 4 (08.03), M04 8+2+1 (08.04/08.07/08.09), M05 3+1 (08.06/08.07), M06 3+3 (08.05/08.08), M07 4 (08.09) = **40 RF**. Los CA se leen **por identificador** desde ETAPA 03. Una fila de esta tabla expresa asignación, nunca aprobación ni prueba ejecutada.

## 4. Contratos de integración obligatorios

1. **Crear pedido:** cabecera y líneas en **una transacción superior**; respetar el trigger de `xmin`/`pg_current_xact_id()::xid`, sin `SAVEPOINT` entre cabecera y líneas ni actualizar la cabecera antes de incluir todas las líneas. Congelar snapshots e importe. Comprender las limitaciones documentadas en ETAPA 07.
2. **Aprobación:** local APP requiere verificar mesa presencialmente y aprobación Mozo/Admin; local WAITER no exige segunda aprobación; APP PICKUP/DELIVERY solo Admin; PHONE/WHATSAPP son altas manuales de Admin. Rechazado no confirma ni genera comanda.
3. **Anticipo:** para PICKUP/DELIVERY `CEIL(total_amount * 50) / 100`; verificar registra **un solo** `payments(kind='ADVANCE')` ya confirmado; `ConfirmOrder` **consulta**, nunca vuelve a cobrar. Restante = total - anticipo; no se registra un cobro cero.
4. **ConfirmOrder:** bloqueo y orden estable de productos, comprobación de habilitación/stock, descuento único y movimiento único por línea, cambio M04 y **una** comanda M05 en **un commit**. Falla = rollback completo; manejar claves idempotentes y diferencias de payload; los módulos se comunican por puertos públicos, no por repositorios ajenos.
5. **Cobros y cierre:** saldo derivado de pagos históricos; impedir sobrepago/repeticiones; roles Caja distintos de permiso de verificar anticipo; registrar entrega/servicio y cerrar solo con saldo cero. Devoluciones = **decisión manual registrada**, no reembolso automatizado.
6. **Cocina:** no se expone comanda de no confirmados; `READY` únicamente tras declaración explícita del personal de cocina de que todo está preparado. La lectura compone `orders` + `order_items` + `kitchen_tickets` + `payments` + `fulfillments`, sin duplicar estados.

## 5. Definición de HECHO por bloque (gate)

- [ ] RF y CA asignados identificados; permisos y reglas aprobadas verificados, decisiones abiertas aisladas.
- [ ] Slice con dominio sin dependencias de FastAPI/ORM, puertos, adaptadores y contrato HTTP `/api/v1`, código reutilizado cuando proceda.
- [ ] Pruebas **positivas, negativas, de autorización e idempotencia** según el bloque, incluida integración PostgreSQL cuando toca. **08.07/08.08 incluyen concurrencia real**: dos sesiones UoW, barrera determinista, timeout y verificación en tercera transacción.
- [ ] `ruff`, `mypy`, `pytest`, `alembic check` pertinentes y OpenAPI coherente; diferenciar aprobado, fallido, omitido y no ejecutado.
- [ ] Trazabilidad `RF/CA → slice/caso de uso → endpoint → pruebas` en `etapa-08-progreso.md`; revisor registra hallazgos y se resuelven antes del siguiente bloque.
- [ ] Sin nueva funcionalidad o permiso inventado; no tocar frontend. El usuario aprueba **la etapa final**, no la mera creación de documentación.

## 6. Recuperación de contexto cuando se agoten tokens

Al iniciar **una nueva conversación** en Codex o AGY, usar **solo** este prompt mínimo:

> Continúa la ETAPA 08 de Chifa ASIA desde `docs/etapas/etapa-08-progreso.md`. Lee `AGENTS.md`, el bloque activo de `docs/etapas/etapa-08.md`, los RF/CA aplicables de `etapa-03-requisitos.md` y la Skill `.agents/skills/restaurant-fastapi-slice/SKILL.md`. Comprueba `git status` y archivos existentes. No repitas bloques HECHO, no inventes decisiones, no hagas commit/push. Implementa/verifica **solo el siguiente bloque permitido**, actualiza el registro de continuidad con evidencias reales y detente al terminar el bloque o ante una decisión bloqueante.

**Regla de recuperación:** el nuevo agente debe leer primero el registro de progreso, no reconstruir lo ocurrido a partir de mensajes o logs extensos. Codex y AGY comparten el mismo directorio local, pero **no** asumir que los cambios sin commit existen en GitHub u otra máquina. Si el registro discrepa del código, prevalece la **verificación del código y pruebas**, documentando la discrepancia.
