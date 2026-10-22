"""M05 kitchen HTTP adapters."""

from restaurant_app.modules.m05_kitchen.adapters.inbound.http.errors import (
    install_kitchen_error_handlers,
)
from restaurant_app.modules.m05_kitchen.adapters.inbound.http.routes import router

__all__ = ["install_kitchen_error_handlers", "router"]
