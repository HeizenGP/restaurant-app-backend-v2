"""Expected advance-verification failures."""


class AdvanceError(Exception):
    """Base M06 advance failure."""


class AdvanceNotFoundError(AdvanceError):
    """Order is absent or not visible to the principal."""


class AdvanceConflictError(AdvanceError):
    """Order state, modality, or idempotency key prevents verification."""


class InvalidAdvanceRequestError(AdvanceError):
    """The request key is invalid."""
