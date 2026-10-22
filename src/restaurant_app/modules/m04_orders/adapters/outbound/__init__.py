"""M04 orders outbound adapters."""

from restaurant_app.modules.m04_orders.adapters.outbound.repositories import (
    SqlAlchemyOrderRepository,
)

__all__ = ["SqlAlchemyOrderRepository"]
