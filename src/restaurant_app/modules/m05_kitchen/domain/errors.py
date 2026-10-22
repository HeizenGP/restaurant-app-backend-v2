"""Expected failures for a kitchen-ticket operation."""


class KitchenError(Exception):
    """Base M05 failure."""


class KitchenTicketNotFound(KitchenError):
    """Ticket is absent or its order is not enabled for kitchen."""


class KitchenTransitionConflict(KitchenError):
    """The ticket cannot perform the requested transition."""
