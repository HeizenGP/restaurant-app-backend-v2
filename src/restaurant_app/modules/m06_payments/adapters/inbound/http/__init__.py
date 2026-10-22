"""HTTP entry point for the M06 advance slice."""

from .collection_routes import collection_router
from .errors import install_advance_error_handlers, install_payment_error_handlers
from .routes import router

__all__ = [
    "collection_router",
    "install_advance_error_handlers",
    "install_payment_error_handlers",
    "router",
]
