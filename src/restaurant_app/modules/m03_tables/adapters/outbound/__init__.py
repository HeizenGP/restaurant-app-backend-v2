"""M03 outbound adapters."""

from restaurant_app.modules.m03_tables.adapters.outbound.repositories import (
    SqlAlchemyTableRepository,
)

__all__ = ["SqlAlchemyTableRepository"]
