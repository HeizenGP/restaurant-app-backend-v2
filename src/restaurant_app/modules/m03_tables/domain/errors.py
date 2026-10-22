"""Expected business errors for M03 table operations."""


class TableError(Exception):
    """Base error mapped at the HTTP boundary."""


class TableNotFoundError(TableError):
    """The selected table does not exist."""


class TableCodeConflictError(TableError):
    """A table already has the requested visible code."""


class InvalidTableValueError(TableError):
    """An input violates the approved table constraints."""
