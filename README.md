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

La configuración usa variables con prefijo `RESTAURANT_`. Cambia la contraseña
de ejemplo antes de levantar PostgreSQL. El diagnóstico queda disponible en
`http://127.0.0.1:8000/health`.

`database/schema.sql` es la línea base SQL aprobada y la migración Alembic es su
mecanismo ejecutable equivalente. **No apliques ambos sobre la misma base.**

## Verificación

```bash
ruff check src tests alembic
mypy src
pytest
alembic check
```

Las pruebas PostgreSQL requieren una base descartable ya migrada. Por seguridad,
el nombre debe contener `test` o `stage07` y el truncado exige opt-in explícito:

```bash
ALLOW_DESTRUCTIVE_TEST_DATABASE=1 \
TEST_DATABASE_DSN=postgresql://usuario:clave@127.0.0.1:5432/restaurant_app_test \
  pytest -m integration
```

- [Plan maestro de etapas 00–11](docs/etapas/README.md)
- [ETAPA 07 — configuración técnica](docs/etapas/etapa-07.md)
- [Guía para Codex y AGY](docs/agentes/README.md)

**Estado:** ETAPA 07 implementada y pendiente de revisión y aprobación expresa.
