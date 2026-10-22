"""Pure advance values; no payment gateway or collection workflow."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from uuid import UUID


def required_advance(total_amount: Decimal) -> Decimal:
    """Half the immutable order total, rounded up to the next PEN cent."""

    if total_amount <= 0:
        raise ValueError("Order total must be positive")
    return (total_amount * Decimal("0.50")).quantize(Decimal("0.01"), rounding=ROUND_CEILING)


@dataclass(frozen=True, slots=True)
class AdvancePayment:
    id: UUID
    order_id: UUID
    amount: Decimal
    recorded_by_user_id: UUID
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class AdvanceSummary:
    order_id: UUID
    order_status: str
    total_amount: Decimal
    required_amount: Decimal
    verified_amount: Decimal
    remaining_amount: Decimal
    verified_at: datetime | None
