"""M06 advance and cashier collection request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from restaurant_app.modules.m06_payments.domain.entities import (
    AdvancePayment,
    AdvanceSummary,
    CollectionPayment,
    PaymentSummary,
)


class AdvanceSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: UUID
    order_status: str
    total_amount: Decimal
    required_amount: Decimal
    verified_amount: Decimal
    remaining_amount: Decimal
    verified_at: datetime | None

    @classmethod
    def from_domain(cls, summary: AdvanceSummary) -> Self:
        return cls(
            order_id=summary.order_id,
            order_status=summary.order_status,
            total_amount=summary.total_amount,
            required_amount=summary.required_amount,
            verified_amount=summary.verified_amount,
            remaining_amount=summary.remaining_amount,
            verified_at=summary.verified_at,
        )


# ---------------------------------------------------------------------------
# Collection schemas (08.08)
# ---------------------------------------------------------------------------


class RecordCollectionRequest(BaseModel):
    """Body for POST /orders/{order_id}/payments."""

    model_config = ConfigDict(frozen=True)

    amount: Decimal
    method_code: str
    reference_code: str | None = None


class PaymentItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    kind: str
    amount: Decimal
    method_code: str | None
    reference_code: str | None
    recorded_by_user_id: UUID
    recorded_at: datetime


class PaymentSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: UUID
    order_status: str
    total_amount: Decimal
    paid_amount: Decimal
    balance: Decimal
    payment_status: str
    payments: list[PaymentItemResponse]

    @classmethod
    def from_domain(cls, summary: PaymentSummary) -> Self:
        items: list[PaymentItemResponse] = []
        for p in summary.payments:
            if isinstance(p, CollectionPayment):
                items.append(
                    PaymentItemResponse(
                        id=p.id,
                        kind="COLLECTION",
                        amount=p.amount,
                        method_code=p.method_code,
                        reference_code=p.reference_code,
                        recorded_by_user_id=p.recorded_by_user_id,
                        recorded_at=p.recorded_at,
                    )
                )
            elif isinstance(p, AdvancePayment):
                items.append(
                    PaymentItemResponse(
                        id=p.id,
                        kind="ADVANCE",
                        amount=p.amount,
                        method_code=None,
                        reference_code=None,
                        recorded_by_user_id=p.recorded_by_user_id,
                        recorded_at=p.recorded_at,
                    )
                )
        return cls(
            order_id=summary.order_id,
            order_status=summary.order_status,
            total_amount=summary.total_amount,
            paid_amount=summary.paid_amount,
            balance=summary.balance,
            payment_status=summary.payment_status,
            payments=items,
        )
