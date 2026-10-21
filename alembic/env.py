"""Alembic environment using the application's asynchronous database URL."""

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.schema import ForeignKeyConstraint

import restaurant_app.db_models  # noqa: F401  # register all mapped tables
from restaurant_app.core.config import get_settings
from restaurant_app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", str(get_settings().database_url).replace("%", "%%"))
target_metadata = Base.metadata


def _foreign_key_signature(constraint: ForeignKeyConstraint) -> tuple[Any, ...]:
    """Normalize PostgreSQL's omitted default-schema qualifier for comparisons."""

    targets = tuple(
        element.target_fullname.removeprefix("public.") for element in constraint.elements
    )
    options = tuple((element.onupdate, element.ondelete) for element in constraint.elements)
    return constraint.table.name, tuple(constraint.column_keys), targets, options


def include_object(
    object_: Any,
    _: str | None,
    type_: str,
    __: bool,
    compare_to: Any,
) -> bool:
    """Ignore only equivalent FKs whose ``public`` qualifier reflection omits."""

    if (
        type_ == "foreign_key_constraint"
        and isinstance(object_, ForeignKeyConstraint)
        and isinstance(compare_to, ForeignKeyConstraint)
    ):
        return _foreign_key_signature(object_) != _foreign_key_signature(compare_to)
    return True


def run_migrations_offline() -> None:
    """Render migrations without opening a database connection."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure and execute migrations on a synchronous proxy connection."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and bridge Alembic's operations safely."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Execute migrations using SQLAlchemy's async engine."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
