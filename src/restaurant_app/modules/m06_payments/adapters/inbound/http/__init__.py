"""HTTP entry point for the M06 advance slice."""

from .errors import install_advance_error_handlers
from .routes import router

__all__ = ["install_advance_error_handlers", "router"]
