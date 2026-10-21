"""M02 catalog and stock HTTP adapters."""

from .errors import install_catalog_error_handlers
from .routes import router

__all__ = ["install_catalog_error_handlers", "router"]
