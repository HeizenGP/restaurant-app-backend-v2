"""Expected business errors for M03 table operations."""


class TableError(Exception):
    """Base error mapped at the HTTP boundary."""


class TableNotFoundError(TableError):
    """The selected table does not exist."""


class TableCodeConflictError(TableError):
    """A table already has the requested visible code."""


class TableOccupancyConflictError(TableError):
    """Table occupancy cannot be changed because of pending active orders."""


class TableAccountConflictError(TableError):
    """An open table account belongs to another service session."""


class InvalidTableValueError(TableError):
    """An input violates the approved table constraints."""
