"""Smoke tests for the technical FastAPI endpoint."""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from restaurant_app.core.config import AppEnvironment, Settings
from restaurant_app.core.dependencies import database_is_ready
from restaurant_app.main import create_app


def build_test_app(*, database_ready: bool, cors_origins: list[str] | None = None) -> FastAPI:
    settings = Settings(
        _env_file=None,
        environment=AppEnvironment.TEST,
        postgres_db="restaurant_app_test",
        postgres_password="test",
        cors_origins=cors_origins or [],
    )
    application = create_app(settings)

    async def override_database_is_ready() -> bool:
        return database_ready

    application.dependency_overrides[database_is_ready] = override_database_is_ready
    return application


def test_health_reports_api_and_database_available() -> None:
    application = build_test_app(database_ready=True)

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "ok",
        "service": "Restaurant App V2 API",
        "version": "0.1.0",
        "environment": "test",
        "checks": {"database": "up"},
    }


def test_create_app_uses_injected_settings_for_database_resources() -> None:
    settings = Settings(
        _env_file=None,
        environment=AppEnvironment.TEST,
        postgres_db="settings_owned_database",
        postgres_password="test",
    )

    application = create_app(settings)

    assert application.state.settings is settings
    assert application.state.database.engine.url.database == "settings_owned_database"

    with TestClient(application):
        pass


def test_health_reports_database_unavailable_without_leaking_details() -> None:
    application = build_test_app(database_ready=False)

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"] == {"database": "down"}


def test_configured_cors_origin_is_allowed() -> None:
    application = build_test_app(
        database_ready=True,
        cors_origins=["http://localhost:5173"],
    )

    with TestClient(application) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_lifespan_startup_triggers_seed_outside_test_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    mock_seed = AsyncMock()
    monkeypatch.setattr("restaurant_app.main.seed_initial_catalog", mock_seed)

    settings = Settings(
        _env_file=None,
        environment=AppEnvironment.LOCAL,
        postgres_password="replace-this-local-password",
    )
    application = create_app(settings)
    with TestClient(application):
        pass

    mock_seed.assert_awaited_once()
