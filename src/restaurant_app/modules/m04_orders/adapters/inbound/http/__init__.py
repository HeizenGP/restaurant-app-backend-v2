"""M04 request HTTP adapters."""

from restaurant_app.modules.m04_orders.adapters.inbound.http.errors import (
    install_order_error_handlers,
)
from restaurant_app.modules.m04_orders.adapters.inbound.http.routes import router

__all__ = ["install_order_error_handlers", "router"]
