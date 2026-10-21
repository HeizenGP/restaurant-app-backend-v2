# ETAPA 07 — Configuración técnica | Chifa ASIA

**Estado:** IMPLEMENTADA / PENDIENTE DE REVISIÓN Y APROBACIÓN

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
  Settings y variables `RESTAURANT_*`.
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
La contraseña de `.env.example` es solo un marcador local.

## 3. PostgreSQL, ORM y Alembic

La revisión `20261021_0001` reproduce ETAPA 06: 14 tablas de la aplicación, seis
roles, 17 índices explícitos, ocho funciones PL/pgSQL, nueve triggers y la vista
`order_payment_summary`. Alembic añade `alembic_version`, que no forma parte de las
14 tablas aprobadas.

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
- inserción de líneas en la transacción de creación, comparando `xmin` con
  `txid_current() % 4294967296`;
- inmutabilidad de total, líneas, movimientos y datos financieros;
- stock no negativo y movimiento de pedido confirmado;
- anticipo exacto `CEIL(total_amount * 50) / 100`, saldos derivados, un anticipo por
  pedido y ausencia de sobrepago;
- estados/campos coherentes de cocina e idempotencia de pagos.

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
`restaurant_app_stage07_test` sobre la imagen PostgreSQL 17.11 fijada por digest.
Solo recibió la migración Alembic.

| Comprobación | Resultado |
|---|---|
| `pip install -e ".[dev]"` y `pip check` | correcto, sin dependencias rotas |
| `ruff check src tests alembic` | correcto |
| `mypy src` | correcto, 89 archivos |
| Alembic offline SQL | generado correctamente |
| `alembic upgrade head` desde vacío | correcto, `20261021_0001` |
| `alembic downgrade base` y nuevo `upgrade head` | correcto |
| `alembic check` | `No new upgrade operations detected` |
| catálogo PostgreSQL | 14 tablas + `alembic_version`, 17 índices, 8 funciones, 9 triggers, 1 vista, 6 roles |
| suite sin DSN | 16 correctas, 7 omitidas explícitamente |
| suite con `TEST_DATABASE_DSN` y opt-in destructivo | 23 correctas, cobertura 96 % |
| Uvicorn + `GET /health` | HTTP 200, API `ok`, PostgreSQL `up` |

Las siete pruebas de integración verifican catálogo exacto, FK inválida,
cabecera/líneas en una transacción, total diferido, inserción tardía, inmutabilidad,
stock, movimiento confirmado, estado de cocina, anticipo redondeado, idempotencia,
segundo anticipo independiente, sobrepago e historial financiero. Antes de conectarse,
la suite exige `ALLOW_DESTRUCTIVE_TEST_DATABASE=1` y un nombre de base que contenga
`test` o `stage07`; de lo contrario se detiene sin ejecutar `TRUNCATE`.

```json
{"status":"ok","service":"Restaurant App V2 API","version":"0.1.0","environment":"test","checks":{"database":"up"}}
```

### 5.2 Docker

Docker Engine 29.4.3 levantó el servicio `postgres` con Compose y el healthcheck quedó
`healthy`. Sobre ese contenedor se ejecutaron `upgrade head`, `alembic check`,
`downgrade base`, un nuevo `upgrade head`, las 23 pruebas y Uvicorn con `/health` en
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
- `alembic/` y `tests/`;
- `README.md`, este documento y el plan maestro.

**Frontend:**

- `apps/customer_app/`, `apps/staff_app/`;
- `README.md`, este documento y el plan maestro.

No hubo `commit`, `push`, `merge` ni escritura remota.

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

# Base descartable ya migrada; el nombre debe contener test o stage07.
ALLOW_DESTRUCTIVE_TEST_DATABASE=1 \
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

## 8. Pendientes y cierre

- RN-20, RN-21, RNF-08, permisos M07 y comprobantes simulados siguen pendientes.
- No avanzar a ETAPA 08 ni aprobar automáticamente esta etapa.

**Cierre técnico:** FastAPI, Alembic y PostgreSQL fueron ejecutados mediante Docker
Compose; ambos proyectos Flutter compilan y pasan sus verificaciones técnicas. ETAPA 07
queda **IMPLEMENTADA / PENDIENTE DE REVISIÓN Y APROBACIÓN**.
