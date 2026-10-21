# ETAPA 08 — Registro de continuidad Codex / AGY

**Estado actual:** 08.00, 08.01 y 08.02 verificados técnicamente; 08.02 queda listo para revisión del usuario. 08.03 no iniciado. La ETAPA 08 completa no está aprobada. Los CA transversales que requieren módulos futuros siguen pendientes de integración real.

**Plan estable:** [`etapa-08.md`](etapa-08.md) · **Rama:** `develop` · **Repositorio único:** `restaurant-app-backend-v2` · **Workspace local compartido:** `~/proyectos/restaurant-app-v2/restaurant-app-backend-v2` · **RF oficiales:** `etapa-03-requisitos.md`. ETAPA 07 aprobada por el usuario (2026-10-21); ETAPA 08 en desarrollo, no aprobada como etapa completa.

## 1. Tablero de bloques

Estados permitidos: `PENDIENTE`, `EN CURSO`, `BLOQUEADO`, `IMPLEMENTADO SIN VERIFICAR`, `VERIFICADO`. No marcar `VERIFICADO` sin resultados concretos.

| Bloque | Responsable sugerido | Estado | RF validados | Evidencia | Siguiente dependencia |
|---|---|---|---|---|---|
| 08.00 Línea base | AGY | VERIFICADO | — | 19/19 unit pass, ruff ✓, mypy ✓, ORM=14 tablas, Alembic head=0002, /health 200/503 | 08.01 |
| 08.01 M01 Accesos | Codex | VERIFICADO | RF-M01-01 (2/2 CA); infraestructura de RF-M01-02…05 verificada; CA transversales pendientes en sus bloques | 50/50 pruebas en PostgreSQL Docker existente antes de retirar la BD de prueba; alta inicial + login/logout reales; Ruff, formato, mypy, OpenAPI y Alembic check ✓; ver §3 | 08.02 implementado; CA transversales posteriores |
| 08.02 M02 Catálogo | Codex | VERIFICADO | RF-M02-01…03 (CA completos); RF-M02-04 implementado, CA-M02-04-01 parcial hasta M04 | 56/56 pruebas en PostgreSQL Docker existente; Ruff, formato, mypy, OpenAPI y Alembic check ✓; stock 8→12 y movimiento auditado; ver §2–3 | Revisión del usuario; 08.03 no iniciado |
| 08.03 M03 Mesas | Codex | PENDIENTE | — | — | 08.04 |
| 08.04 M04 Solicitudes | AGY | PENDIENTE | — | — | 08.05 |
| 08.05 M06 Anticipo | Codex | PENDIENTE | — | — | 08.06 |
| 08.06 M05 Cocina base | AGY | PENDIENTE | — | — | 08.07 |
| 08.07 ConfirmOrder | Codex | PENDIENTE | — | — | 08.08 |
| 08.08 M06 Caja | AGY | PENDIENTE | — | — | 08.09 |
| 08.09 M07 + seguimiento | Codex | PENDIENTE | — | — | 08.10 |
| 08.10 Validación integral | AGY | PENDIENTE | — | — | Revisión usuario |

## 2. Último punto de control (actualizar SIEMPRE)

- **Fecha / agente:** 2026-10-21 / Codex, cierre técnico del bloque 08.02. Se aplicó la Skill `restaurant-fastapi-slice`: dominio y puertos separados de FastAPI/ORM, slices por caso de uso y autorización tanto en HTTP como en el handler.
- **Workspace y discrepancia comprobada:** `/home/heizen27/proyectos/restaurant-app-v2/restaurant-app-backend-v2`, rama `develop`, HEAD `6f40058` alineado con `origin/develop` al comenzar; árbol limpio antes de 08.02. El checkpoint 08.01 registraba HEAD `76d0ac7` y cambios M01 sin commit; el estado real actual ya contenía M01 en HEAD. No se rehizo 08.00/08.01 ni se atribuyó ese avance a este bloque. Los cambios 08.02 siguen locales y sin commit.
- **RF/CA y límites:** RF-M02-01/CA-M02-01-01, RF-M02-02/CA-M02-02-01 y RF-M02-03/CA-M02-03-01 verificados por API y PostgreSQL. RF-M02-04 permite habilitar/deshabilitar y el catálogo público refleja el cambio, pero CA-M02-04-01 solo es **parcial**: impedir incorporación a un pedido nuevo se debe comprobar con M04 en 08.04. RF-M02-05/06, validación y descuento de stock al confirmar, pertenecen a 08.07 y no se implementaron. RN-20 sigue pendiente de ratificación; no se inventó un flujo de pedido.
- **API y slices:** `GET /api/v1/catalog/categories`, `GET /api/v1/catalog/categories/{category_id}/products`; alta/edición administrativa de categorías y productos con `POST`/`PATCH`; `PUT /api/v1/catalog/products/{product_id}/stock` fija existencia absoluta y `PATCH /api/v1/catalog/products/{product_id}/availability` cambia habilitación manual. Los handlers `list_catalog`, `save_category`, `save_product`, `adjust_stock` y `set_product_availability` usan un puerto de catálogo y repositorio SQLAlchemy Async. El catálogo público expone nombre, precio y `available_for_sale` calculado desde habilitación y stock positivo, sin revelar cantidad exacta. Escrituras restringidas a `ADMIN`/`SUPER_ADMIN`, con 401/403, 404/409/422 probados.
- **Stock y esquema:** stock no negativo y actualización manual atómica mediante bloqueo de fila `FOR UPDATE`; ajuste 8→12 deja 12 y un movimiento `MANUAL` de +4 con actor y fecha. El mismo valor no genera un movimiento ficticio. Se reutilizan las tablas aprobadas `categories`, `products`, `stock_movements`; **sin migraciones ni tablas nuevas**. La disponibilidad manual no equivale todavía a una validación de pedido en `ConfirmOrder`.
- **Archivos de 08.02:** `src/restaurant_app/modules/m02_catalog_stock/{domain/{entities,errors}.py,application/ports/catalog_repository.py,application/use_cases/{list_catalog,save_category,save_product,adjust_stock,set_product_availability}/,adapters/inbound/http/{__init__,dependencies,errors,routes,schemas}.py,adapters/outbound/{__init__,repositories}.py}`, `src/restaurant_app/main.py`, `tests/test_m02_use_cases.py`, `tests/integration/test_m02_catalog.py`. Ajuste mínimo en `src/restaurant_app/modules/m01_access/adapters/inbound/http/errors.py`: serialización segura de `ctx` en respuestas 422; no añade funcionalidad M01. Solo esta bitácora se actualizó en `docs/`; frontend intacto.
- **PostgreSQL de pruebas:** se usó exclusivamente el contenedor existente `postgres` en 5432. Para integración se creó `restaurant_m02_test` dentro de él, se migró a `20261021_0002` y se autorizó exactamente con `TEST_DATABASE_DSN` + `ALLOW_DESTRUCTIVE_TEST_DATABASE=restaurant_m02_test`. Tras las pruebas se comprobó que sus tablas de usuarios, productos y movimientos estaban vacías, y se eliminó esa base temporal. `docker ps` confirma `postgres` en ejecución y `psql -lqt` confirma que solo siguen `restaurant_app`, `restaurant_test`, `restaurante_app` y las bases de sistema; ninguna de las tres bases persistentes fue usada para pruebas destructivas. La base temporal de datos de prueba se eliminó sin respaldo, después de comprobar su identidad y contenido.
- **Pruebas y chequeos reales:**
  - `pytest tests/ -m "not integration" -q --no-cov` → **43 passed, 13 deselected en 2.14 s**.
  - `pytest tests/ -q --tb=short --no-cov` contra `restaurant_m02_test` autorizada → **56 passed en 4.93 s**. Hubo una primera ejecución con **1 fallo** al serializar `Decimal` en un 422; se corrigió el manejador de errores y se repitió la suite completa con 56/56. Las dos pruebas M02 de integración cubren catálogo, permisos, valores inválidos, 8→12, auditoría y deshabilitación.
  - `ruff check src/ tests/` → **All checks passed**; `ruff format --check src/ tests/` → **149 files already formatted**; `mypy --config-file=pyproject.toml` → **sin errores en 137 archivos fuente**; `git diff --check` → sin errores.
  - `alembic check` sobre `restaurant_app` → **No new upgrade operations detected**. `GET /openapi.json` → **200**; siete patrones de ruta M02 y esquema Bearer en todas las operaciones de escritura.
- **Antecedente 08.01 conservado:** 50/50 pruebas en PostgreSQL Docker y verificación de roles/sesiones registrados al cierre anterior; el usuario autorizó entonces el primer `SUPER_ADMIN` en `restaurant_app`. Sus CA transversales siguen con el estado indicado en §3. No se cambió esa cuenta ni se publicaron credenciales en 08.02.
- **Siguiente acción exacta:** detenerse tras 08.02 y esperar revisión del usuario. No iniciar 08.03. Cuando M04 y ConfirmOrder existan, revalidar CA-M02-04-01 y RF-M02-05/06 en sus bloques previstos; no marcarlos completos por inferencia.
- **Commit/push:** no realizados ni autorizados. La verificación técnica de 08.02 no aprueba la ETAPA 08 completa.

## 3. Matriz de trazabilidad (actualizar por RF realmente verificado)

| RF / CA | Bloque | Caso de uso / slice | Endpoint REST | Pruebas ejecutadas | Resultado |
|---|---|---|---|---|---|
| RF-M01-01 / CA-M01-01-01 | 08.01 | `register_user`, `login_user` | `POST /api/v1/auth/register`, `/login` | `tests/test_m01_use_cases.py`, `tests/integration/test_m01_access.py`; suite completa 50/50 | VERIFICADO |
| RF-M01-01 / CA-M01-01-02 | 08.01 | `login_user` | `POST /api/v1/auth/login` | credenciales ausentes/incorrectas indistinguibles, 401; suite 50/50 | VERIFICADO |
| RF-M01-02 / CA-M01-02-01 | 08.01 + 08.04 | `start_guest_session`, `authenticate_request` | `POST /api/v1/auth/guest` | sesión GUEST sin cuenta/rol/refresh y 403 probados; iniciar pedido aún no existe | PARCIAL; E2E 08.04 |
| RF-M01-03 / CA-M01-03-01 | 08.01 + bloques Mozo | `authenticate_request`, `authorize_roles` | `/login`; guard público M01 para endpoints futuros | WAITER autorizado por política pura; funciones reales de Mozo aún no existen | PARCIAL; E2E posterior |
| RF-M01-04 / CA-M01-04-01 | 08.01 + 08.08 | `assign_user_role`, `authorize_roles` | `POST /api/v1/users/{user_id}/roles` | roles acumulados en BD y guard Admin+Cajero probados; función Caja aún no existe | PARCIAL; E2E 08.08 |
| RF-M01-05 / CA-M01-05-01 | 08.01 + módulos posteriores | `authorize_roles` | guard público M01 para endpoints futuros | bypass `SUPER_ADMIN` probado; acceso real a cada módulo pendiente | PARCIAL; E2E posterior |
| RF-M01-05 / CA-M01-05-02 | 08.01 + 08.04/08.07 | `authorize_roles` | guard público M01 para aprobación futura | CASHIER solo rechazado por política; aprobar pedido aún no existe | PARCIAL; E2E posterior |
| RF-M02-01 / CA-M02-01-01 | 08.02 | `list_catalog` | `GET /api/v1/catalog/categories/{category_id}/products` | `tests/integration/test_m02_catalog.py`: nombre, precio y disponibilidad pública; suite 56/56 | VERIFICADO |
| RF-M02-02 / CA-M02-02-01 | 08.02 | `save_category`, `save_product` | `POST /api/v1/catalog/categories`, `PATCH /api/v1/catalog/categories/{category_id}`, `POST /api/v1/catalog/products`, `PATCH /api/v1/catalog/products/{product_id}` | alta y edición Admin; lectura pública refleja cambio; 401/403/404/409/422 | VERIFICADO |
| RF-M02-03 / CA-M02-03-01 | 08.02 | `adjust_stock` | `PUT /api/v1/catalog/products/{product_id}/stock` | 8→12, movimiento +4 `MANUAL` con actor/fecha; repetición 12 sin movimiento; negativo 422 | VERIFICADO |
| RF-M02-04 / CA-M02-04-01 | 08.02 + 08.04 | `set_product_availability`, lectura de catálogo | `PATCH /api/v1/catalog/products/{product_id}/availability` | producto con stock deshabilitado aparece no vendible; incorporación a nuevo pedido aún sin caso de uso | PARCIAL; E2E 08.04 |
| RF-M02-05 / CA-M02-05-01 y RF-M02-06 / CA-M02-06-01…02 | 08.07 | `ConfirmOrder` futuro | Sin endpoint | No implementados ni probados en 08.02 | PENDIENTE; 08.07 |

**Regla:** agregar filas conforme avance cada bloque, referenciando identificadores exactos `RF-Mxx-yy` y `CA-Mxx-yy-zz` de ETAPA 03. No copiar los 40 RF completos aquí ni duplicar pruebas; enlazar rutas y comandos relevantes. Un RF asignado a un bloque no equivale a un RF probado.

## 4. Reglas de traspaso de agentes

1. Antes de dejar el trabajo por límite de tokens, escribir el punto de control con los archivos sin terminar, error/hipótesis comprobada y **una acción siguiente**; conservar `EN CURSO` si corresponde.
2. El nuevo agente accede al **mismo directorio local del backend**, lee primero esta bitácora, el bloque activo, la Skill backend y RF/CA pertinentes. Verifica `pwd`, rama, `git status` y código existente; si no coincide con el registro, documenta la discrepancia antes de modificarlo. No necesita exportar/importar archivos entre Codex y AGY.
3. El implementador es el único que modifica archivos de su bloque; el otro realiza revisión secuencial y registra riesgos. No mezclar cambios en el mismo directorio/archivo a la vez.
4. Tras una verificación real, actualizar tabla de bloques y matriz RF/CA. Nunca reportar `HECHO` por compilación incompleta o prueba no ejecutada.
5. Mantener esta bitácora y `etapa-08.md` **solo en el backend durante ETAPA 08**; no editar ni sincronizar el repositorio frontend. No realizar commit/push sin orden expresa del usuario.

## 5. Prompts mínimos de sesión

**Codex (implementar):** «Retoma Chifa ASIA ETAPA 08 desde `docs/etapas/etapa-08-progreso.md`. Consulta el bloque activo de `etapa-08.md`, la Skill `restaurant-fastapi-slice` y solo RF/CA relevantes. Verifica código y Git. Implementa y prueba únicamente el bloque actual. Actualiza checkpoint y detente.»

**AGY (revisar o tomar turno):** «Lee `docs/etapas/etapa-08-progreso.md` y el bloque activo. Como revisor, audita RF/CA, arquitectura hexagonal, permisos, integración PostgreSQL y pruebas sin editar archivos del implementador. Si es tu turno, implementa solo el bloque asignado y registra los resultados antes de entregar el control.»
