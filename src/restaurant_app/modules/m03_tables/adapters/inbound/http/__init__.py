"""M03 HTTP adapter exports."""

from restaurant_app.modules.m03_tables.adapters.inbound.http.errors import (
    install_table_error_handlers,
)
from restaurant_app.modules.m03_tables.adapters.inbound.http.routes import router

__all__ = ["install_table_error_handlers", "router"]
