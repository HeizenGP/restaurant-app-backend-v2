"""Tests for typed environment configuration."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from restaurant_app.core.config import AppEnvironment, Settings


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep configuration tests independent from the caller's local environment."""

    for variable_name in tuple(os.environ):
        if variable_name.startswith(("POSTGRES_", "RESTAURANT_")):
            monkeypatch.delenv(variable_name)


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment is AppEnvironment.LOCAL
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url.scheme == "postgresql+asyncpg"
    assert settings.database_url.path == "/restaurant_app"
    assert settings.cors_origins == []


def test_settings_read_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESTAURANT_ENVIRONMENT", "test")
    monkeypatch.setenv("RESTAURANT_API_V1_PREFIX", "/api/v2/")
    monkeypatch.setenv(
        "RESTAURANT_CORS_ORIGINS",
        '["http://localhost:5173/", "http://localhost:5173"]',
    )

    settings = Settings(_env_file=None)

    assert settings.environment is AppEnvironment.TEST
    assert settings.api_v1_prefix == "/api/v2"
    assert settings.cors_origins == ["http://localhost:5173"]


def test_settings_build_async_dsn_from_shared_postgres_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "55432")
    monkeypatch.setenv("POSTGRES_DB", "restaurant/app?test")
    monkeypatch.setenv("POSTGRES_USER", "restaurant/user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "s:p/@ce?#%")

    settings = Settings(_env_file=None)

    assert str(settings.database_url) == (
        "postgresql+asyncpg://restaurant%2Fuser:s%3Ap%2F%40ce%3F%23%25@"
        "db.internal:55432/restaurant%2Fapp%3Ftest"
    )


def test_env_example_and_compose_share_one_postgres_password_source() -> None:
    repository_root = Path(__file__).parents[1]
    example = (repository_root / ".env.example").read_text(encoding="utf-8")
    compose = (repository_root / "compose.yaml").read_text(encoding="utf-8")
    alembic_configuration = (repository_root / "alembic.ini").read_text(encoding="utf-8")

    assert "POSTGRES_PASSWORD=replace-this-local-password" in example
    assert "RESTAURANT_DATABASE_URL" not in example
    assert "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?" in compose
    assert '"127.0.0.1:${POSTGRES_PORT:-5432}:5432"' in compose
    assert "sqlalchemy.url =\n" in alembic_configuration
    assert "postgresql+asyncpg://" not in alembic_configuration


def test_settings_reject_debug_in_production() -> None:
    with pytest.raises(ValidationError, match="debug must be disabled"):
        Settings(_env_file=None, environment="production", debug=True)


def test_settings_reject_placeholder_password_outside_local_or_test() -> None:
    with pytest.raises(ValidationError, match="replace the local PostgreSQL password"):
        Settings(_env_file=None, environment="staging")


def test_settings_repr_does_not_expose_database_credentials() -> None:
    settings = Settings(
        _env_file=None,
        postgres_password="private-value",
    )

    assert "private-value" not in repr(settings)
