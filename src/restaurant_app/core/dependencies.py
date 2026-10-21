"""Technical dependencies shared by the HTTP entry point."""

import logging
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.core.config import Settings
from restaurant_app.core.database import DatabaseResources, session_scope

logger = logging.getLogger(__name__)


def get_database_resources(request: Request) -> DatabaseResources:
    """Return the resources owned by the current FastAPI application."""

    return cast(DatabaseResources, request.app.state.database)


def get_app_settings(request: Request) -> Settings:
    """Return the settings used to build the current FastAPI application."""

    return cast(Settings, request.app.state.settings)


DatabaseResourcesDependency = Annotated[
    DatabaseResources,
    Depends(get_database_resources),
]


async def get_db_session(
    resources: DatabaseResourcesDependency,
) -> AsyncIterator[AsyncSession]:
    """Expose the application-owned transaction boundary to FastAPI."""

    async with session_scope(resources) as session:
        yield session


async def database_is_ready(resources: DatabaseResourcesDependency) -> bool:
    """Run a side-effect-free query used by the technical health endpoint."""

    try:
        async with resources.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except OSError, SQLAlchemyError, TimeoutError:
        logger.warning("PostgreSQL readiness check failed", exc_info=True)
        return False
    return True


DatabaseSession = Annotated[AsyncSession, Depends(get_db_session, scope="function")]
DatabaseReady = Annotated[bool, Depends(database_is_ready)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
