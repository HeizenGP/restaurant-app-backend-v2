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
