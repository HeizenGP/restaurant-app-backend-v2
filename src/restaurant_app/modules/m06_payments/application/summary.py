"""Build the advance view from an immutable M04 order and an M06 payment."""

from decimal import Decimal

from restaurant_app.modules.m04_orders.public import OrderForAdvance
from restaurant_app.modules.m06_payments.domain.entities import (
    AdvancePayment,
    AdvanceSummary,
    required_advance,
)


def advance_summary(order: OrderForAdvance, payment: AdvancePayment | None) -> AdvanceSummary:
    verified = payment.amount if payment is not None else Decimal("0.00")
    return AdvanceSummary(
        order_id=order.id,
        order_status=order.status,
        total_amount=order.total_amount,
        required_amount=required_advance(order.total_amount),
        verified_amount=verified,
        remaining_amount=order.total_amount - verified,
        verified_at=payment.recorded_at if payment is not None else None,
    )
