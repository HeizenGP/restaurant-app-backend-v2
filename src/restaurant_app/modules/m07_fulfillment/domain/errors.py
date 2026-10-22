"""Expected M07 business errors."""


class FulfillmentError(Exception):
    """A service, handover, close, or tracking request cannot be completed."""


class FulfillmentNotFoundError(FulfillmentError):
    """The order is missing or not visible to this principal."""


class FulfillmentConflictError(FulfillmentError):
    """The requested transition conflicts with persisted state."""


class InvalidFulfillmentRequestError(FulfillmentError):
    """A command contains an invalid idempotency key."""
