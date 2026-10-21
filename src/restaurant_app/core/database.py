"""SQLAlchemy Async resources, declarative base, and transaction boundaries."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from restaurant_app.core.config import Settings


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base shared only by outbound SQLAlchemy adapters."""

    metadata = MetaData(naming_convention={"fk": "%(table_name)s_%(column_0_name)s_fkey"})


@dataclass(frozen=True, slots=True)
class DatabaseResources:
    """Engine and session factory owned by one FastAPI application instance."""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    async def dispose(self) -> None:
        """Close this application's connection pool."""

        await self.engine.dispose()


def create_database_resources(settings: Settings) -> DatabaseResources:
    """Build database resources from the same settings used by the application."""

    engine = create_async_engine(
        str(settings.database_url),
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return DatabaseResources(engine=engine, session_factory=session_factory)


@asynccontextmanager
async def session_scope(resources: DatabaseResources) -> AsyncIterator[AsyncSession]:
    """Provide one session and one atomic transaction for an application operation."""

    async with resources.session_factory() as session, session.begin():
        yield session
