"""Pure values for simulated advances, collections and derived balances."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from uuid import UUID


def required_advance(total_amount: Decimal) -> Decimal:
    """Half the immutable order total, rounded up to the next PEN cent."""

    if total_amount <= 0:
        raise ValueError("Order total must be positive")
    return (total_amount * Decimal("0.50")).quantize(Decimal("0.01"), rounding=ROUND_CEILING)


# ---------------------------------------------------------------------------
# Advance (08.05)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Collection (08.08)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CollectionPayment:
    id: UUID
    order_id: UUID
    amount: Decimal
    method_code: str | None
    recorded_by_user_id: UUID
    recorded_at: datetime
    reference_code: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentSummary:
    """Full payment view: advance + collections against the order total."""

    order_id: UUID
    order_status: str
    total_amount: Decimal
    paid_amount: Decimal
    balance: Decimal
    payments: tuple[CollectionPayment | AdvancePayment, ...]

    @property
    def payment_status(self) -> str:
        if self.balance <= 0:
            return "PAID"
        return "PARTIAL" if self.paid_amount > 0 else "UNPAID"


# ---------------------------------------------------------------------------
# Consolidated table account
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TableAccountLine:
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass(frozen=True, slots=True)
class TableAccountOrder:
    id: UUID
    status: str
    total_amount: Decimal
    paid_amount: Decimal
    created_at: datetime
    lines: tuple[TableAccountLine, ...]

    @property
    def balance(self) -> Decimal:
        return self.total_amount - self.paid_amount


@dataclass(frozen=True, slots=True)
class TableAccountPayment:
    id: UUID
    order_id: UUID | None
    amount: Decimal
    kind: str
    method_code: str | None
    reference_code: str | None
    recorded_by_user_id: UUID
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class TableAccountSummary:
    id: UUID
    table_id: UUID
    table_code: str
    status: str
    customer_user_id: UUID | None
    guest_session_id: UUID | None
    opened_at: datetime
    closed_at: datetime | None
    total_amount: Decimal
    advance_amount: Decimal
    paid_amount: Decimal
    balance: Decimal
    orders: tuple[TableAccountOrder, ...]
    payments: tuple[TableAccountPayment, ...]


@dataclass(frozen=True, slots=True)
class TableAccountChargeState:
    id: UUID
    table_id: UUID
    order_ids: tuple[UUID, ...]
    order_statuses: tuple[str, ...]
    total_amount: Decimal
    paid_amount: Decimal

    @property
    def balance(self) -> Decimal:
        return self.total_amount - self.paid_amount
