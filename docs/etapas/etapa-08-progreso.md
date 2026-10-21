# ETAPA 08 — Registro de continuidad Codex / AGY

**Estado actual:** 08.00 y 08.01 verificados técnicamente; 08.02 pendiente de traspaso/instrucción. La ETAPA 08 completa no está aprobada. Los CA transversales que requieren módulos futuros siguen pendientes de integración real.

**Plan estable:** [`etapa-08.md`](etapa-08.md) · **Rama:** `develop` · **Repositorio único:** `restaurant-app-backend-v2` · **Workspace local compartido:** `~/proyectos/restaurant-app-v2/restaurant-app-backend-v2` · **RF oficiales:** `etapa-03-requisitos.md`. ETAPA 07 aprobada por el usuario (2026-10-21); ETAPA 08 en desarrollo, no aprobada como etapa completa.

## 1. Tablero de bloques

Estados permitidos: `PENDIENTE`, `EN CURSO`, `BLOQUEADO`, `IMPLEMENTADO SIN VERIFICAR`, `VERIFICADO`. No marcar `VERIFICADO` sin resultados concretos.

| Bloque | Responsable sugerido | Estado | RF validados | Evidencia | Siguiente dependencia |
|---|---|---|---|---|---|
| 08.00 Línea base | AGY | VERIFICADO | — | 19/19 unit pass, ruff ✓, mypy ✓, ORM=14 tablas, Alembic head=0002, /health 200/503 | 08.01 |
| 08.01 M01 Accesos | Codex | VERIFICADO | RF-M01-01 (2/2 CA); infraestructura de RF-M01-02…05 verificada; CA transversales pendientes en sus bloques | 50/50 pruebas en PostgreSQL Docker existente antes de retirar la BD de prueba; alta inicial + login/logout reales; Ruff, formato, mypy, OpenAPI y Alembic check ✓; ver §2–3 | 08.02 pendiente de instrucción/traspaso |
| 08.02 M02 Catálogo | AGY | PENDIENTE | — | — | 08.03 |
| 08.03 M03 Mesas | Codex | PENDIENTE | — | — | 08.04 |
| 08.04 M04 Solicitudes | AGY | PENDIENTE | — | — | 08.05 |
| 08.05 M06 Anticipo | Codex | PENDIENTE | — | — | 08.06 |
| 08.06 M05 Cocina base | AGY | PENDIENTE | — | — | 08.07 |
| 08.07 ConfirmOrder | Codex | PENDIENTE | — | — | 08.08 |
| 08.08 M06 Caja | AGY | PENDIENTE | — | — | 08.09 |
| 08.09 M07 + seguimiento | Codex | PENDIENTE | — | — | 08.10 |
| 08.10 Validación integral | AGY | PENDIENTE | — | — | Revisión usuario |

## 2. Último punto de control (actualizar SIEMPRE)

- **Fecha / agente:** 2026-10-21 / Codex, cierre técnico del bloque 08.01. Skill `restaurant-fastapi-slice` aplicada a los slices y a la revisión de permisos M01.
- **Directorio/rama verificados:** `/home/heizen27/proyectos/restaurant-app-v2/restaurant-app-backend-v2`, `develop`, HEAD `76d0ac7` (`origin/develop`); cambios M01 locales sin commit. Discrepancia con el checkpoint anterior (`9ef4f85`): el nuevo HEAD ya contenía puertos, dominio y `login_user.py` incompleto con digest de `"pending"`; ese trabajo no estaba verificado. Se terminó y reemplazó el flujo sin duplicar 08.00.
- **RF/CA verificados:** RF-M01-01, CA-M01-01-01 y CA-M01-01-02 (registro/login válido e inválido). M01-02…05 tienen sesión, roles, política y asignación implementadas y pruebas técnicas, pero sus CA de operación transversal conservan verificación E2E pendiente en los bloques propietarios (tabla §3).
- **API/slices M01 implementados:** `POST /api/v1/auth/register`, `/login`, `/guest`, `/refresh`, `/logout`, `POST /api/v1/users/{user_id}/roles`; handlers separados en `application/use_cases/<verbo_objeto>/`. Registro asigna solo `CUSTOMER`; invitado carece de usuario, rol y refresh; Argon2id; JWT HS256 con `iss`/`aud`/tipo/expiración; refresh de un solo uso con digest SHA-256 y rotación atómica; logout y control de sesión en BD; roles vigentes resueltos de BD, unión de permisos y bypass `SUPER_ADMIN`. HTTP y handler comprueban autorización. 401, 403, 409 y 422 sin eco de contraseñas probados.
- **Archivos modificados:** `.env.example`; `src/restaurant_app/core/{config,dependencies}.py`, `main.py`; `src/restaurant_app/modules/m01_access/{domain/entities.py,application/ports/,application/use_cases/,application/results.py,adapters/inbound/http/,adapters/outbound/,public.py}`; `tests/{test_m01_use_cases.py,test_m01_security_adapters.py,integration/test_m01_access.py}`. Los dos casos de uso planos heredados se sustituyeron por directorios de slice. Sin cambios al frontend ni a tablas/migraciones.
- **PostgreSQL verificado:** por decisión expresa del usuario se usa solo su contenedor `postgres` en 5432. La base normal nueva `restaurant_app` se creó allí y se migró hasta `20261021_0002`: consulta real → 14 tablas de aplicación + `alembic_version` y seis roles seed. `alembic check` → sin operaciones nuevas; `/health` de la API con `.env` local → 200 y `database: up`. La `.env` ignorada por Git usa `postgres` con la contraseña proporcionada por el usuario y una clave JWT aleatoria local no registrada aquí. Para las 50 pruebas se usó antes `restaurant_app_test` con autorización destructiva exacta (`TEST_DATABASE_DSN` + `ALLOW_DESTRUCTIVE_TEST_DATABASE=restaurant_app_test`); tras comprobar que no contenía usuarios ni sesiones y por instrucción expresa del usuario, se eliminó. No se tocaron `restaurante_app` ni `restaurant_test`, ambas preexistentes. El contenedor Compose adicional creado por error en 55432, su volumen y su red también se retiraron; solo queda `postgres`.
- **Alta inicial `SUPER_ADMIN`:** el usuario autorizó expresamente crear la primera cuenta y proporcionó correo y contraseña. Se hizo una operación administrativa única y transaccional **solo en `restaurant_app`**, sin endpoint ni migración nuevos, con precondición de cero usuarios y cero Super Administradores. El primer intento de invocación falló por expansión de marcadores SQL en la terminal; se comprobó rollback (cero usuarios/roles) antes de reintentar. El alta final produjo **un usuario activo con solo `SUPER_ADMIN`**, hash `$argon2id` y ninguna contraseña en la documentación. La sesión HTTP real confirmó `/login` 200 y `/logout` 204; el único token usado quedó revocado. La contraseña inicial reutiliza la de PostgreSQL por elección del usuario; se recomienda rotar una de las dos antes de exponer la API. Las asignaciones ordinarias posteriores siguen exigiendo otro `SUPER_ADMIN` en el handler.
- **Pruebas ejecutadas (resultados reales):**
  - `pytest tests/ -m "not integration" -q --no-cov` tras conectar la BD normal → **39 passed, 11 deselected en 3.20 s**; los 11 de integración se ejecutaron antes contra la BD de prueba autorizada.
  - `pytest tests/ -q --tb=short --no-cov`, con `TEST_DATABASE_DSN` autorizado y credenciales solo en el entorno del proceso → **50 passed en 3.06 s** (incluye siete pruebas de migración/seguridad y cuatro M01 contra PostgreSQL real).
  - `ruff check src/ tests/` → **All checks passed**; `ruff format --check src/ tests/` → **129 files already formatted**.
  - `mypy --config-file=pyproject.toml` → **sin errores en 119 archivos**; `git diff --check` → sin errores.
  - `alembic check` en `restaurant_app` del contenedor existente → **No new upgrade operations detected**; `GET /health` con `.env` local → **200**, `database: up`.
- **Revalidación de cierre (2026-10-21):** `pytest tests/ -m "not integration" -q --no-cov` → **39 passed, 11 deselected en 1.17 s**; `ruff check src/ tests/` → **All checks passed**; `ruff format --check src/ tests/` → **129 files already formatted**; `mypy --config-file=pyproject.toml` → **sin errores en 119 archivos**; `alembic check` → **No new upgrade operations detected**. `GET /openapi.json` → **200**, seis rutas M01 presentes y seguridad Bearer en asignación de roles. La integración completa **no se repitió** porque `restaurant_app_test` fue eliminada por petición del usuario; el resultado previo de 50/50 permanece registrado arriba. No se recreó esa base ni otro contenedor.
- **Decisiones y límites pendientes:** el usuario confirmó que solo otro `SUPER_ADMIN` puede conceder `SUPER_ADMIN`; la guarda existente del handler y la prueba correspondiente se conservan. El alta inicial solicitada quedó realizada sin abrir un flujo público reutilizable. HTTPS para despliegue Internet (RNF-03) no se puede verificar en esta etapa local. Los CA que requieren crear/aprobar pedidos, funciones de Mozo, Caja u otros módulos se revalidarán al existir esos casos de uso.
- **Revisión de otros agentes:** tres auditorías de solo lectura de contrato, esquema y seguridad antes de la implementación; no equivalen a aprobación de la ETAPA 08 ni a revisión independiente del código final. La verificación técnica del bloque no sustituye la revisión del usuario.
- **Siguiente acción exacta:** detenerse tras 08.01 y esperar revisión/traspaso del usuario; 08.02 sigue pendiente. Al implementar módulos posteriores, revalidar los CA M01 transversales de la matriz §3. No aprobar la ETAPA 08 por inferencia.
- **Commit/push:** NO autorizado de forma automática; no inventar hash de trabajo sin commit.

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
