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
    TableAccountSummary,
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


class TableAccountLineResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class TableAccountOrderResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    status: str
    total_amount: Decimal
    paid_amount: Decimal
    balance: Decimal
    created_at: datetime
    lines: list[TableAccountLineResponse]


class TableAccountPaymentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    order_id: UUID | None
    amount: Decimal
    kind: str
    method_code: str | None
    reference_code: str | None
    recorded_by_user_id: UUID
    recorded_at: datetime


class TableAccountSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

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
    orders: list[TableAccountOrderResponse]
    payments: list[TableAccountPaymentResponse]

    @classmethod
    def from_domain(cls, summary: TableAccountSummary) -> Self:
        return cls(
            id=summary.id,
            table_id=summary.table_id,
            table_code=summary.table_code,
            status=summary.status,
            customer_user_id=summary.customer_user_id,
            guest_session_id=summary.guest_session_id,
            opened_at=summary.opened_at,
            closed_at=summary.closed_at,
            total_amount=summary.total_amount,
            advance_amount=summary.advance_amount,
            paid_amount=summary.paid_amount,
            balance=summary.balance,
            orders=[
                TableAccountOrderResponse(
                    id=order.id,
                    status=order.status,
                    total_amount=order.total_amount,
                    paid_amount=order.paid_amount,
                    balance=order.balance,
                    created_at=order.created_at,
                    lines=[
                        TableAccountLineResponse(
                            product_id=line.product_id,
                            product_name=line.product_name,
                            quantity=line.quantity,
                            unit_price=line.unit_price,
                            subtotal=line.subtotal,
                        )
                        for line in order.lines
                    ],
                )
                for order in summary.orders
            ],
            payments=[
                TableAccountPaymentResponse(
                    id=payment.id,
                    order_id=payment.order_id,
                    amount=payment.amount,
                    kind=payment.kind,
                    method_code=payment.method_code,
                    reference_code=payment.reference_code,
                    recorded_by_user_id=payment.recorded_by_user_id,
                    recorded_at=payment.recorded_at,
                )
                for payment in summary.payments
            ],
        )
