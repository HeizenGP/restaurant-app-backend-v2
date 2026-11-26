"""Expected M02 failures, independent of HTTP and persistence."""


class CatalogError(Exception):
    """Base class for safe catalog failures."""


class CategoryNotFoundError(CatalogError):
    """The requested category does not exist."""


class ProductNotFoundError(CatalogError):
    """The requested product does not exist."""


class CategoryNameConflictError(CatalogError):
    """A category already has the requested name."""


class InvalidCatalogValueError(CatalogError):
    """A value violates the approved catalog or stock rules."""


class StaleStockQuantityError(CatalogError):
    """The stock snapshot used for a manual adjustment is no longer current."""
