"""Expected M06 payment failures."""


class AdvanceError(Exception):
    """Base M06 advance failure."""


class AdvanceNotFoundError(AdvanceError):
    """Order is absent or not visible to the principal."""


class AdvanceConflictError(AdvanceError):
    """Order state, modality, or idempotency key prevents verification."""


class InvalidAdvanceRequestError(AdvanceError):
    """The request key is invalid."""


# ---------------------------------------------------------------------------
# Collection errors (08.08)
# ---------------------------------------------------------------------------


class PaymentError(Exception):
    """Base M06 cashier/collection failure."""


class PaymentNotFoundError(PaymentError):
    """Order or payment not found."""


class PaymentConflictError(PaymentError):
    """Overpayment, duplicate, or invalid state."""


class InvalidPaymentRequestError(PaymentError):
    """Bad request data for collection."""
