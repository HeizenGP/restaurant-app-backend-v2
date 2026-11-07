# Restaurant App V2 — Backend

Base técnica FastAPI de Chifa ASIA para la ETAPA 07. Incluye configuración,
PostgreSQL, SQLAlchemy Async, Alembic, modelos de las 14 tablas aprobadas y un
endpoint técnico `/health`. No contiene endpoints ni casos de uso funcionales.

## Requisitos

- Python 3.14
- PostgreSQL 17; para desarrollo se proporciona Docker Compose
- Docker Compose v2, si se utiliza el contenedor incluido

## Inicio local

```bash
cp .env.example .env
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
docker compose --env-file .env up -d --wait postgres
alembic upgrade head
uvicorn restaurant_app.main:app --reload
```

La API usa `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` y
`POSTGRES_PASSWORD` como única fuente de conexión; Compose comparte base,
usuario, contraseña y puerto, mientras `POSTGRES_HOST` identifica el destino de
la API. El DSN `postgresql+asyncpg` se deriva internamente y no existe un
`RESTAURANT_DATABASE_URL` paralelo. Las demás opciones de aplicación conservan
el prefijo `RESTAURANT_`. Cambia el marcador de contraseña en el `.env` local,
que no se versiona. El diagnóstico queda disponible en
`http://127.0.0.1:8000/health`.

## Google OAuth y recuperación de contraseña

M01 recibe un **Google ID token** en `POST /api/v1/auth/google`, verifica firma,
issuer, audiencia, expiración y correo verificado con `google-auth`, y recién
entonces emite la sesión JWT/refresh propia de KAIRO. Los usuarios nuevos se
vinculan por el claim estable `sub`; una cuenta local existente nunca se enlaza
automáticamente solo porque coincida el correo.

Configura fuera del repositorio:

- `RESTAURANT_GOOGLE_OAUTH_CLIENT_ID`: client ID de tipo **Web application** que
  el cliente Flutter usa como `GOOGLE_WEB_CLIENT_ID`.
- `RESTAURANT_SMTP_HOST`, `RESTAURANT_SMTP_PORT`,
  `RESTAURANT_SMTP_USERNAME`, `RESTAURANT_SMTP_PASSWORD` y
  `RESTAURANT_SMTP_FROM_EMAIL`: se establecen todos juntos para habilitar el
  envío real de recuperación.
- `RESTAURANT_PASSWORD_RESET_URL`: enlace confiable incluido en el correo;
  Android acepta por defecto `kairo://app/recuperar-acceso`.

Los tokens de recuperación se generan con entropía criptográfica, se guardan
solo como SHA-256, vencen, se consumen una sola vez y revocan las sesiones del
usuario al cambiar la contraseña. Si SMTP no está configurado, el endpoint
mantiene su respuesta no enumerativa, pero no puede entregar el mensaje.

## Gestión de Direcciones y Zonas de Delivery (GPS / OpenStreetMap)

El backend soporta gestión completa de direcciones con coordenadas geográficas y evaluación de zonas de cobertura desde la sede KAIRO (San Isidro, Lima: `-12.0968, -77.0353`):

- **Migración Alembic:** `20261107_0008_user_addresses.py` añade la tabla `public.user_addresses` vinculada a `users(id)` con eliminación en cascada, checks de rango de latitud `[-90, 90]` y longitud `[-180, 180]`, e índices para consulta rápida y dirección predeterminada.
- **Endpoints de Direcciones:**
  - `GET /api/v1/users/me/addresses`: Listado ordenado de direcciones del usuario autenticado (la predeterminada primero).
  - `POST /api/v1/users/me/addresses`: Creación con etiqueta (Casa, Trabajo, Otro), coordenadas, referencia e interior opcionales.
  - `PUT /api/v1/users/me/addresses/{id}`: Actualización completa o parcial de la dirección.
  - `DELETE /api/v1/users/me/addresses/{id}`: Eliminación segura (reasigna predeterminada si corresponde).
  - `POST /api/v1/users/me/addresses/{id}/set-default`: Define la dirección activa predeterminada.
- **Endpoints de Delivery y Geocoding:**
  - `POST /api/v1/delivery/check-zone`: Valida cobertura según distancia Haversine y calcula costo estimado (Zona 1: S/ 5.00, Zona 2: S/ 8.00, Zona 3: S/ 12.00, >12km: fuera de zona).
  - `GET /api/v1/delivery/zones`: Información de las zonas de cobertura tarifarias y sede del restaurante.
  - `GET /api/v1/delivery/geocode/reverse?lat=...&lon=...`: Geocodificación inversa vía OpenStreetMap Nominatim (proxy async de bajo consumo sin dependencias externas).
  - `GET /api/v1/delivery/geocode/search?q=...`: Búsqueda de direcciones sugeridas acotada a Lima, Perú.

Cambiar `POSTGRES_PASSWORD` no modifica las credenciales almacenadas en un
volumen PostgreSQL ya inicializado. Un volumen local descartable debe recrearse
de forma intencional; en una base persistente, la contraseña del rol debe rotarse
explícitamente mediante PostgreSQL.

`database/schema.sql` es la línea base SQL aprobada y la migración Alembic es su
mecanismo ejecutable equivalente. **No apliques ambos sobre la misma base.**

## Verificación

```bash
ruff check src tests alembic
mypy src
pytest
alembic check
```

Las pruebas PostgreSQL requieren una base descartable migrada al `head` exacto.
Antes de conectarse, la suite exige que el nombre termine en `_test` o
`_stage07` y que `ALLOW_DESTRUCTIVE_TEST_DATABASE` coincida exactamente con ese
nombre. Tras conectarse verifica también `current_database()` y la revisión
Alembic antes de permitir cualquier `TRUNCATE`:

```bash
ALLOW_DESTRUCTIVE_TEST_DATABASE=restaurant_app_test \
TEST_DATABASE_DSN=postgresql://usuario:clave@127.0.0.1:5432/restaurant_app_test \
  pytest -m integration
```

- [Plan maestro de etapas 00–11](docs/etapas/README.md)
- [ETAPA 07 — configuración técnica](docs/etapas/etapa-07.md)
- [Guía para Codex y AGY](docs/agentes/README.md)

**Estado:** ETAPA 07 implementada y pendiente de revisión y aprobación expresa.
