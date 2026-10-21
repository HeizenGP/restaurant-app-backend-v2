"""Tests for typed environment configuration."""

import pytest
from pydantic import ValidationError

from restaurant_app.core.config import AppEnvironment, Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment is AppEnvironment.LOCAL
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url.scheme == "postgresql+asyncpg"
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


def test_settings_reject_synchronous_postgresql_driver() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        Settings(
            _env_file=None,
            database_url="postgresql://restaurant_app:password@localhost/restaurant_app",
        )


def test_settings_reject_debug_in_production() -> None:
    with pytest.raises(ValidationError, match="debug must be disabled"):
        Settings(_env_file=None, environment="production", debug=True)


def test_settings_repr_does_not_expose_database_credentials() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://restaurant_app:private-value@localhost/restaurant_app",
    )

    assert "private-value" not in repr(settings)
