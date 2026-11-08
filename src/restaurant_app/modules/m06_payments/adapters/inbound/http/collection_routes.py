"""Cashier collection endpoints — RF-M06-01, 05, 06."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.public import CurrentPrincipal
from restaurant_app.modules.m06_payments.adapters.inbound.http.dependencies import (
    Cashier,
    get_payment_summary_handler,
    record_collection_handler,
)
from restaurant_app.modules.m06_payments.adapters.inbound.http.schemas import (
    PaymentSummaryResponse,
    RecordCollectionRequest,
)
from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel

collection_router = APIRouter(prefix="/orders", tags=["M06 cashier"])
payments_router = APIRouter(prefix="/payments", tags=["M06 payments"])
RequestKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


class PaymentRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    order_id: str
    kind: str
    amount: float
    method_code: str | None = None
    reference_code: str | None = None
    recorded_by_user_id: str
    recorded_at: str


@payments_router.get("", response_model=list[PaymentRecordResponse])
async def list_all_payments(
    actor: Cashier,
    session: DatabaseSession,
    limit: int = 100,
) -> list[PaymentRecordResponse]:
    """Query recent payments across all orders."""
    statement = select(PaymentModel).order_by(PaymentModel.recorded_at.desc()).limit(limit)
    models = (await session.scalars(statement)).all()
    return [
        PaymentRecordResponse(
            id=str(m.id),
            order_id=str(m.order_id),
            kind=m.kind,
            amount=float(m.amount),
            method_code=m.method_code,
            reference_code=m.reference_code,
            recorded_by_user_id=str(m.recorded_by_user_id),
            recorded_at=m.recorded_at.isoformat(),
        )
        for m in models
    ]


@collection_router.post(
    "/{order_id}/payments",
    response_model=PaymentSummaryResponse,
    status_code=200,
)
async def record_payment(
    order_id: UUID,
    body: RecordCollectionRequest,
    request_key: RequestKey,
    actor: Cashier,
    session: DatabaseSession,
) -> PaymentSummaryResponse:
    """Register a partial or complete collection for a confirmed order."""
    summary = await record_collection_handler(session)(
        actor=actor,
        order_id=order_id,
        amount=body.amount,
        method_code=body.method_code,
        reference_code=body.reference_code,
        request_key=request_key,
    )
    return PaymentSummaryResponse.from_domain(summary)


@collection_router.get(
    "/{order_id}/payments",
    response_model=PaymentSummaryResponse,
)
async def get_payment_summary(
    order_id: UUID,
    actor: CurrentPrincipal,
    session: DatabaseSession,
) -> PaymentSummaryResponse:
    """Query the payment history and balance for an order."""
    summary = await get_payment_summary_handler(session)(actor=actor, order_id=order_id)
    return PaymentSummaryResponse.from_domain(summary)
