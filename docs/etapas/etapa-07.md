# ETAPA 07 — Configuración técnica | Chifa ASIA

**Estado:** APROBADA EXPRESAMENTE POR EL USUARIO (2026-10-21) · infraestructura ejecutable y verificación documentada; las decisiones de negocio pendientes permanecen abiertas.

**Fecha de implementación y verificación:** 2026-10-21 · **Rama:** `develop`

**Base aprobada:** ETAPA 05 (arquitectura) y ETAPA 06 (PostgreSQL, 14 tablas/DER).

La etapa deja infraestructura ejecutable y pruebas técnicas; no implementa ninguno de
los 40 RF. El desarrollo funcional sigue reservado para la ETAPA 08 y la interfaz de
negocio para las ETAPAS 09–10.

## 1. Estado inicial comprobado

Se revisaron `AGENTS.md`, el plan maestro, ETAPAS 05–07, las Skills
`restaurant-fastapi-slice` y `restaurant-flutter-slice`, el DER/diccionario aprobado y
`database/schema.sql`.

- Backend real: `develop`, HEAD inicial `69d92cd`, alineado con
  `origin/develop`; tenía documentación y el SQL aprobado, pero no una aplicación
  Python ejecutable.
- Frontend real: `develop`, HEAD inicial `34f69be`, alineado con
  `origin/develop`; no tenía aplicaciones Flutter.
- Los documentos compartidos eran iguales al iniciar.
- Las Skills se usaron como reglas de arquitectura. No se implementaron slices
  funcionales.
- Se conservaron siete módulos M01–M07, seis actores, 40 RF, 11 RNF y los pendientes
  aprobados. No se modificaron las ETAPAS 00–06.

## 2. Backend implementado

### 2.1 Base técnica

- Proyecto empaquetado desde `src/restaurant_app/` con Python 3.14.
- FastAPI mediante `create_app`, configuración tipada e inmutable con Pydantic
  Settings. Las opciones de aplicación, pool y CORS usan `RESTAURANT_*`; la
  conexión usa exclusivamente `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`,
  `POSTGRES_USER` y `POSTGRES_PASSWORD`.
- SQLAlchemy Async + `asyncpg`, pool con `pool_pre_ping`, fábrica de sesiones y
  frontera transaccional por operación. Cada instancia de FastAPI crea y libera sus
  recursos de base de datos desde la misma configuración inyectada.
- CORS solo para orígenes explícitos, sin comodín ni credenciales.
- Endpoint exclusivamente técnico `GET /health`; no hay rutas de negocio.
- Monolito modular hexagonal M01–M07 con `domain/`, `application/ports/`,
  `application/use_cases/`, adaptadores y `public.py`, todavía sin casos de uso.
- Registro de modelos solo para Alembic en `db_models.py`; los modelos pertenecen a
  sus módulos.
- Convención estable de claves foráneas y comparación Alembic que normaliza únicamente
  la omisión de `public` por PostgreSQL. `alembic check` queda sin deriva.
- `.env.example`, secretos/artefactos excluidos y `compose.yaml` reproducible.
  Docker y la API comparten base, usuario, contraseña y puerto; la API construye
  internamente un único DSN async y PostgreSQL se publica solo en loopback.

### 2.2 Versiones comprobadas

| Componente | Versión ejecutada |
|---|---:|
| Python | 3.14.4 |
| PostgreSQL | 17.11 |
| Docker CLI / Engine | 29.4.3 / 29.4.3 |
| FastAPI | 0.156.8 |
| SQLAlchemy | 2.1.5 |
| asyncpg | 0.32.0 |
| Alembic | 1.20.0 |
| Pydantic Settings | 2.16.1 |
| Uvicorn | 0.54.0 |
| PyJWT / pwdlib | 2.15.1 / 0.3.1 |
| pytest / pytest-asyncio / pytest-cov | 9.1.1 / 1.4.0 / 7.1.0 |
| Ruff / mypy | 0.17.1 / 2.4.0 |

La imagen declarada es
`postgres:17.11-alpine3.24@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24`.
La contraseña de `.env.example` es solo un marcador local, se trata como
`SecretStr` y se rechaza en staging/producción. El `.env` real permanece ignorado
y con permisos locales restrictivos. Cambiar `POSTGRES_PASSWORD` no cambia la
contraseña almacenada en un volumen PostgreSQL ya inicializado: un volumen
descartable debe recrearse intencionalmente y un rol persistente debe rotarse
mediante PostgreSQL.

## 3. PostgreSQL, ORM y Alembic

La revisión `20261021_0001` reproduce ETAPA 06: 14 tablas de la aplicación, seis
roles, 17 índices explícitos, ocho funciones PL/pgSQL, nueve triggers y la vista
`order_payment_summary`. La revisión correctiva `20261021_0002` reemplaza una
función con `CREATE OR REPLACE FUNCTION`; no crea ni altera tablas. Alembic añade
`alembic_version`, que no forma parte de las 14 tablas aprobadas.

| Tablas aprobadas | Propietario ORM | Revisión |
|---|---|---|
| `users`, `roles`, `user_roles`, `auth_sessions` | M01 `m01_access/.../models.py` | `20261021_0001` |
| `categories`, `products`, `stock_movements` | M02 `m02_catalog_stock/.../models.py` | `20261021_0001` |
| `restaurant_tables` | M03 `m03_tables/.../models.py` | `20261021_0001` |
| `orders`, `order_items` | M04 `m04_orders/.../models.py` | `20261021_0001` |
| `kitchen_tickets` | M05 `m05_kitchen/.../models.py` | `20261021_0001` |
| `idempotency_requests` | Soporte `shared/.../models.py` | `20261021_0001` |
| `payments` | M06 `m06_payments/.../models.py` | `20261021_0001` |
| `fulfillments` | M07 `m07_fulfillment/.../models.py` | `20261021_0001` |

Se mantuvieron sin reinterpretación:

- relaciones con borrado `RESTRICT`;
- coherencia diferida cabecera/líneas y total;
- inserción de líneas en la transacción de creación, comparando `orders.xmin`,
  tipado como `xid`, con `pg_current_xact_id()::xid`;
- inmutabilidad de total, líneas, movimientos y datos financieros;
- stock no negativo y movimiento de pedido confirmado;
- anticipo exacto `CEIL(total_amount * 50) / 100`, saldos derivados, un anticipo por
  pedido y ausencia de sobrepago;
- estados/campos coherentes de cocina e idempotencia de pagos.

La corrección de `xmin` evita la API heredada `txid_*` y la aritmética manual,
pero sigue siendo una defensa física acotada. `xmin` identifica una versión de
fila con un XID de 32 bits: puede reciclarse por wraparound y cambia con cada
`UPDATE`. `pg_current_xact_id()` representa la transacción superior. Por ello,
`CreateOrder` deberá crear cabecera y líneas en una única transacción superior,
sin repartirlas entre `SAVEPOINT` anidados y sin actualizar la cabecera antes de
insertar todas las líneas. La guarda protege el alta conjunta dentro de ese
contrato; no es una versión de negocio ni un mecanismo de concurrencia optimista
duradero. No fue necesario añadir columnas ni cambiar las 14 tablas aprobadas.
Referencias: [columnas de sistema](https://www.postgresql.org/docs/17/ddl-system-columns.html),
[identificadores de transacción](https://www.postgresql.org/docs/17/transaction-id.html)
y [funciones de información de transacciones](https://www.postgresql.org/docs/17/functions-info.html).

`database/schema.sql` sigue siendo la referencia manual. No se aplicó sobre la base de
Alembic; ambos mecanismos no deben mezclarse en una misma base.

## 4. Frontend técnico implementado

- `apps/customer_app`: Flutter Android para cliente/invitado.
- `apps/staff_app`: Flutter Android y Web para personal/administración.
- API validada mediante `--dart-define=API_BASE_URL=<URL HTTP(S) absoluta>`.
- Permiso de Internet disponible también en release; el HTTP local hacia `10.0.2.2`
  se habilita únicamente mediante la configuración de seguridad del variant debug.
- Análisis estricto y pruebas unitarias del entorno API.
- Bootstrap visual mínimo; sin navegación, roles, compra, pedidos ni pantallas
  funcionales.
- No se creó tercera aplicación ni paquete compartido prematuro.

Versiones: Flutter 3.47.5 estable, Dart 3.13.4, Java 21.0.12.1 y Android SDK 36.0.0.

## 5. Verificación realmente ejecutada

### 5.1 Backend y base de datos

Se levantó con Docker Compose la base descartable vacía
`restaurant_app_stage07` sobre la imagen PostgreSQL 17.11 fijada por digest.
Solo recibió la migración Alembic.

| Comprobación | Resultado |
|---|---|
| `pip install -e ".[dev]"` y `pip check` | correcto, sin dependencias rotas |
| `ruff check src tests alembic` | correcto |
| `mypy src` | correcto, 89 archivos |
| Alembic offline SQL | generado correctamente |
| `alembic upgrade head` desde vacío | correcto, `20261021_0002` |
| actualización de una base en `20261021_0001` | correcto, aplica `20261021_0002` |
| `alembic downgrade base` y nuevo `upgrade head` | correcto |
| `alembic check` | `No new upgrade operations detected` |
| catálogo PostgreSQL | 14 tablas + `alembic_version`, 17 índices, 8 funciones, 9 triggers, 1 vista, 6 roles |
| suite sin DSN | 19 correctas, 7 omitidas explícitamente |
| suite con `TEST_DATABASE_DSN` y autorización destructiva | 26 correctas, cobertura 95 % |
| rechazo de una base anterior al `head` | correcto, antes de cualquier `TRUNCATE` |
| Uvicorn + `GET /health` | HTTP 200, API `ok`, PostgreSQL `up` |

Las siete pruebas de integración verifican catálogo exacto, FK inválida,
cabecera/líneas en una transacción, total diferido, inserción tardía, inmutabilidad,
stock, movimiento confirmado, estado de cocina, anticipo redondeado, idempotencia,
segundo anticipo independiente, sobrepago e historial financiero. Antes de conectarse,
la suite valida el esquema PostgreSQL, exige un nombre conforme a
`^[a-z0-9][a-z0-9_]*(?:_test|_stage07)$` y requiere que
`ALLOW_DESTRUCTIVE_TEST_DATABASE` sea exactamente ese nombre. Después comprueba
`current_database()` y que Alembic esté exactamente en `20261021_0002`; recién
entonces puede ejecutar `TRUNCATE`.

```json
{"status":"ok","service":"Restaurant App V2 API","version":"0.1.0","environment":"local","checks":{"database":"up"}}
```

### 5.2 Docker

Docker Engine 29.4.3 levantó el servicio `postgres` con Compose y el healthcheck quedó
`healthy`. Sobre ese contenedor se ejecutaron `upgrade head`, `alembic check`,
`downgrade base`, un nuevo `upgrade head`, las 26 pruebas y Uvicorn con `/health` en
HTTP 200. El contenedor y su volumen de verificación se eliminan al cerrar la prueba;
la imagen fijada queda en la caché normal de Docker.

### 5.3 Flutter

| Aplicación/destino | Resultado |
|---|---|
| `customer_app: flutter analyze` | sin incidencias |
| `customer_app: flutter test` | 2 correctas |
| `customer_app: flutter build apk --debug` | APK generado |
| `staff_app: flutter analyze` | sin incidencias |
| `staff_app: flutter test` | 2 correctas |
| `staff_app: flutter build apk --debug` | APK generado |
| `staff_app: flutter build web` | `build/web` generado; dry-run Wasm correcto |

Web mostró una advertencia no bloqueante por `CupertinoIcons`; el bootstrap no usa
esa fuente.
Los directorios `build`, `.dart_tool` y `.gradle` generados para esta verificación se
limpiaron después de comprobar los artefactos.

## 6. Archivos creados o modificados

**Backend:**

- `pyproject.toml`, `.env.example`, `.gitignore`, `compose.yaml`,
  `alembic.ini`;
- `src/restaurant_app/main.py`, `core/`, `db_models.py`, esqueletos M01–M07 y
  modelos SQLAlchemy;
- `alembic/` —incluida la revisión correctiva `20261021_0002`— y `tests/`;
- `README.md`, este documento y el plan maestro.

**Frontend:**

- `apps/customer_app/`, `apps/staff_app/`;
- `README.md`, este documento y el plan maestro.

Estas correcciones finales se dejan sin `commit`, `push`, `merge` ni aprobación
automática por parte del agente.

## 7. Reproducción local

### Backend

```bash
cd restaurant-app-backend-v2
cp .env.example .env
# Sustituir la contraseña local de ejemplo.
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d postgres
alembic upgrade head
uvicorn restaurant_app.main:app --reload
curl http://127.0.0.1:8000/health
```

```bash
ruff check src tests alembic
mypy src
pytest
alembic check

# Base descartable en head; autorización idéntica al nombre protegido.
ALLOW_DESTRUCTIVE_TEST_DATABASE=restaurant_app_test \
TEST_DATABASE_DSN=postgresql://usuario:clave@127.0.0.1:5432/restaurant_app_test \
  pytest -m integration
```

### Flutter

```bash
cd restaurant-app-frontend-v2/apps/customer_app
flutter pub get
flutter analyze
flutter test
flutter build apk --debug \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1

cd ../staff_app
flutter pub get
flutter analyze
flutter test
flutter build apk --debug \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
flutter build web \
  --dart-define=API_BASE_URL=http://localhost:8000/api/v1
```

## 8. Pruebas de concurrencia reservadas para ETAPA 08

No se implementaron `ConfirmOrder`, cobros ni pruebas de sus casos de uso en esta
etapa. Las pruebas actuales de PostgreSQL son secuenciales y no deben presentarse
como evidencia de concurrencia. En ETAPA 08 se deberán ejecutar contra PostgreSQL
real con dos sesiones/UoW independientes, barrera determinista sin `sleep`, timeout
y una tercera transacción que verifique el estado final.

Casos pendientes de `ConfirmOrder`:

- misma clave y hash: una sola ejecución efectiva, un descuento/movimiento por
  línea y una comanda, devolviendo el mismo resultado;
- claves distintas sobre el mismo pedido: una confirmación y un conflicto, sin
  efectos duplicados;
- dos pedidos compitiendo por existencias suficientes solo para uno: un ganador,
  stock nunca negativo y perdedor sin movimiento ni comanda;
- productos compartidos solicitados en orden inverso: finalización sin deadlock y
  efectos exactos, validando el orden estable de bloqueo por `product_id`;
- recojo/delivery: la confirmación no crea otro pago y no genera comanda sin un
  anticipo ya comprometido.

Casos pendientes de cobros:

- misma clave/hash: un único pago y saldo descontado una vez;
- misma clave con payload/hash distinto: un ganador y un conflicto `409`;
- claves distintas cuyos montos caben en el saldo: ambos pagos persisten sin
  actualización perdida;
- montos concurrentes que exceden el saldo: sin sobrepago, saldo negativo ni fila
  parcial del intento rechazado;
- anticipos concurrentes con claves distintas: exactamente un `ADVANCE` por
  `CEIL(total_amount * 50) / 100`.

Estos casos son pendientes exclusivos de ETAPA 08, no se ejecutaron y no forman
parte de las 26 pruebas reportadas para ETAPA 07. No fijan la métrica aún pendiente
de RNF-08 ni resuelven RN-20/RN-21.

## 9. Pendientes y cierre

- RN-20, RN-21, RNF-08, permisos M07 y comprobantes simulados siguen pendientes.
- **Aprobación expresa del usuario:** 2026-10-21. Se autoriza pasar a ETAPA 08, exclusivamente backend, sin resolver por inferencia los pendientes enumerados.

**Cierre técnico:** FastAPI, Alembic y PostgreSQL fueron ejecutados mediante Docker
Compose; ambos proyectos Flutter compilan y pasan sus verificaciones técnicas. ETAPA 07
queda **APROBADA POR EL USUARIO (2026-10-21)**. ETAPA 08 está autorizada, pero sus bloques funcionales aún no tienen evidencia de implementación.
