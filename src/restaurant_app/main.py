"""FastAPI application factory and technical health endpoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, cast

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from restaurant_app.core.config import AppEnvironment, Settings, get_settings
from restaurant_app.core.database import DatabaseResources, create_database_resources
from restaurant_app.core.dependencies import DatabaseReady
from restaurant_app.modules.m01_access.adapters.inbound.http import (
    install_access_error_handlers,
)
from restaurant_app.modules.m01_access.adapters.inbound.http import (
    router as access_router,
)
from restaurant_app.modules.m02_catalog_stock.adapters.inbound.http import (
    install_catalog_error_handlers,
)
from restaurant_app.modules.m02_catalog_stock.adapters.inbound.http import (
    router as catalog_router,
)
from restaurant_app.modules.m02_catalog_stock.seed import seed_initial_catalog
from restaurant_app.modules.m03_tables.adapters.inbound.http import install_table_error_handlers
from restaurant_app.modules.m03_tables.adapters.inbound.http import router as table_router
from restaurant_app.modules.m03_tables.seed import seed_initial_tables
from restaurant_app.modules.m04_orders.adapters.inbound.http import install_order_error_handlers
from restaurant_app.modules.m04_orders.adapters.inbound.http import router as order_router
from restaurant_app.modules.m05_kitchen.adapters.inbound.http import (
    install_kitchen_error_handlers,
)
from restaurant_app.modules.m05_kitchen.adapters.inbound.http import router as kitchen_router
from restaurant_app.modules.m06_payments.adapters.inbound.http import (
    collection_router,
    install_advance_error_handlers,
    install_payment_error_handlers,
    payments_router,
    table_accounts_router,
)
from restaurant_app.modules.m06_payments.adapters.inbound.http import router as advance_router
from restaurant_app.modules.m07_fulfillment.adapters.inbound.http import (
    install_fulfillment_error_handlers,
)
from restaurant_app.modules.m07_fulfillment.adapters.inbound.http import (
    router as fulfillment_router,
)
from restaurant_app.modules.m07_fulfillment.adapters.inbound.http.delivery_routes import (
    delivery_router,
)
from restaurant_app.modules.reports import reports_router


class HealthChecks(BaseModel):
    """Availability of required technical dependencies."""

    model_config = ConfigDict(frozen=True)

    database: Literal["up", "down"]


class HealthResponse(BaseModel):
    """Non-sensitive API health payload."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: AppEnvironment
    checks: HealthChecks


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Execute startup hooks and release this application's technical resources on shutdown."""

    settings = getattr(application.state, "settings", None)
    environment = getattr(settings, "environment", None)
    if environment != AppEnvironment.TEST:
        database = getattr(application.state, "database", None)
        if database is not None and hasattr(database, "session_factory"):
            try:
                await seed_initial_catalog(database.session_factory)
                await seed_initial_tables(database.session_factory)
            except Exception as exc:
                logging.getLogger("restaurant_app.catalog.seed").warning(
                    "Initial seeding skipped on startup: %s", exc
                )

    yield
    resources = cast(DatabaseResources, application.state.database)
    await resources.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application and register completed functional slices."""

    app_settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, app_settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.database = create_database_resources(app_settings)
    install_access_error_handlers(application)
    install_catalog_error_handlers(application)
    install_table_error_handlers(application)
    install_order_error_handlers(application)
    install_kitchen_error_handlers(application)
    install_advance_error_handlers(application)
    install_payment_error_handlers(application)
    install_fulfillment_error_handlers(application)
    application.include_router(access_router, prefix=app_settings.api_v1_prefix)
    application.include_router(catalog_router, prefix=app_settings.api_v1_prefix)
    application.include_router(table_router, prefix=app_settings.api_v1_prefix)
    application.include_router(order_router, prefix=app_settings.api_v1_prefix)
    application.include_router(kitchen_router, prefix=app_settings.api_v1_prefix)
    application.include_router(advance_router, prefix=app_settings.api_v1_prefix)
    application.include_router(collection_router, prefix=app_settings.api_v1_prefix)
    application.include_router(payments_router, prefix=app_settings.api_v1_prefix)
    application.include_router(table_accounts_router, prefix=app_settings.api_v1_prefix)
    application.include_router(reports_router, prefix=app_settings.api_v1_prefix)
    application.include_router(fulfillment_router, prefix=app_settings.api_v1_prefix)
    application.include_router(delivery_router, prefix=app_settings.api_v1_prefix)

    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    application.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    cors_kwargs: dict[str, object] = {
        "allow_credentials": False,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type", "Idempotency-Key", "Accept"],
    }
    if app_settings.environment == AppEnvironment.LOCAL:
        cors_kwargs["allow_origin_regex"] = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        cors_kwargs["allow_origins"] = app_settings.cors_origins or ["*"]
    elif app_settings.cors_origins:
        cors_kwargs["allow_origins"] = app_settings.cors_origins

    if "allow_origins" in cors_kwargs or "allow_origin_regex" in cors_kwargs:
        application.add_middleware(CORSMiddleware, **cors_kwargs)

    @application.get(
        "/health",
        response_model=HealthResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
        summary="Check API and PostgreSQL availability",
        tags=["technical"],
    )
    async def health_check(response: Response, database_ready: DatabaseReady) -> HealthResponse:
        if not database_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return HealthResponse(
                status="degraded",
                service=app_settings.app_name,
                version=app_settings.app_version,
                environment=app_settings.environment,
                checks=HealthChecks(database="down"),
            )
        return HealthResponse(
            status="ok",
            service=app_settings.app_name,
            version=app_settings.app_version,
            environment=app_settings.environment,
            checks=HealthChecks(database="up"),
        )

    return application


app = create_app()
