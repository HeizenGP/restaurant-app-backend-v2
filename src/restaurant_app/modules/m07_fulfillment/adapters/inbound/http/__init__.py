"""M07 HTTP entry point."""

from restaurant_app.modules.m07_fulfillment.adapters.inbound.http.errors import (
    install_fulfillment_error_handlers,
)
from restaurant_app.modules.m07_fulfillment.adapters.inbound.http.routes import router

__all__ = ["install_fulfillment_error_handlers", "router"]
