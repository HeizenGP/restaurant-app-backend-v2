"""Cashier collection endpoints — RF-M06-01, 05, 06."""

from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.public import CurrentPrincipal
from restaurant_app.modules.m01_access.adapters.outbound.models import UserModel
from restaurant_app.modules.m03_tables.adapters.outbound.models import RestaurantTableModel, TableAccountModel
from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderModel
from restaurant_app.modules.m06_payments.adapters.inbound.http.dependencies import (
    Cashier,
    get_payment_summary_handler,
    get_table_account_handler,
    record_collection_handler,
    record_table_account_payment_handler,
)
from restaurant_app.modules.m06_payments.adapters.inbound.http.schemas import (
    PaymentSummaryResponse,
    RecordCollectionRequest,
    TableAccountSummaryResponse,
    TableCheckoutRequest,
)
from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel
from restaurant_app.modules.m06_payments.adapters.outbound.table_account_repository import SqlAlchemyTableAccountRepository
from restaurant_app.modules.m06_payments.application.use_cases.record_table_account_payment.checkout import RecordTableCheckout
from restaurant_app.modules.m06_payments.domain.errors import InvalidPaymentRequestError

collection_router = APIRouter(prefix="/orders", tags=["M06 cashier"])
payments_router = APIRouter(prefix="/payments", tags=["M06 payments"])
table_accounts_router = APIRouter(prefix="/tables", tags=["M06 table accounts"])
RequestKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


class PaymentRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    order_id: str | None
    table_account_id: str | None = None
    kind: str
    amount: float
    method_code: str | None = None
    reference_code: str | None = None
    recorded_by_user_id: str
    recorded_at: str
    cashier_name: str | None = None
    table_code: str | None = None
    cash_shift_id: UUID | None = None


@payments_router.get("", response_model=list[PaymentRecordResponse])
async def list_all_payments(
    actor: Cashier,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    since: date | None = None,
    until: date | None = None,
    method: Literal["EFECTIVO", "YAPE", "PLIN", "TARJETA"] | None = None,
    kind: Literal["ADVANCE", "COLLECTION"] | None = None,
    resource_id: UUID | None = None,
) -> list[PaymentRecordResponse]:
    """Page and filter immutable collection records, including historical advances."""
    if (since and until and until < since) or until == date.max:
        raise HTTPException(422, "El periodo indicado es inválido")
    lima = ZoneInfo("America/Lima")
    statement = (
        select(PaymentModel, UserModel.display_name, RestaurantTableModel.code)
        .join(UserModel, UserModel.id == PaymentModel.recorded_by_user_id)
        .outerjoin(OrderModel, OrderModel.id == PaymentModel.order_id)
        .outerjoin(TableAccountModel, TableAccountModel.id == PaymentModel.table_account_id)
        .outerjoin(RestaurantTableModel, or_(
            RestaurantTableModel.id == OrderModel.table_id,
            RestaurantTableModel.id == TableAccountModel.table_id,
        ))
        .order_by(PaymentModel.recorded_at.desc(), PaymentModel.id.desc()).limit(limit).offset(offset)
    )
    if since:
        statement = statement.where(PaymentModel.recorded_at >= datetime.combine(since, time.min, lima))
    if until:
        statement = statement.where(PaymentModel.recorded_at < datetime.combine(until + timedelta(days=1), time.min, lima))
    if method:
        statement = statement.where(PaymentModel.method_code == method)
    if kind:
        statement = statement.where(PaymentModel.kind == kind)
    if resource_id:
        statement = statement.where(or_(
            PaymentModel.id == resource_id, PaymentModel.order_id == resource_id,
            PaymentModel.table_account_id == resource_id,
        ))
    models = (await session.execute(statement)).all()
    return [
        PaymentRecordResponse(
            id=str(m.id),
            order_id=str(m.order_id) if m.order_id is not None else None,
            table_account_id=(str(m.table_account_id) if m.table_account_id is not None else None),
            kind=m.kind,
            amount=float(m.amount),
            method_code=m.method_code,
            reference_code=m.reference_code,
            recorded_by_user_id=str(m.recorded_by_user_id),
            recorded_at=m.recorded_at.isoformat(),
            cashier_name=cashier_name, table_code=table_code, cash_shift_id=m.cash_shift_id,
        )
        for m, cashier_name, table_code in models
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


@table_accounts_router.get(
    "/{table_id}/account",
    response_model=TableAccountSummaryResponse,
)
async def get_table_account(
    table_id: UUID,
    actor: CurrentPrincipal,
    session: DatabaseSession,
) -> TableAccountSummaryResponse:
    summary = await get_table_account_handler(session)(actor=actor, table_id=table_id)
    return TableAccountSummaryResponse.from_domain(summary)


@table_accounts_router.post(
    "/{table_id}/account/payments",
    response_model=TableAccountSummaryResponse,
)
async def record_table_account_payment(
    table_id: UUID,
    body: RecordCollectionRequest,
    request_key: RequestKey,
    actor: Cashier,
    session: DatabaseSession,
) -> TableAccountSummaryResponse:
    summary = await record_table_account_payment_handler(session)(
        actor=actor,
        table_id=table_id,
        amount=body.amount,
        method_code=body.method_code,
        reference_code=body.reference_code,
        request_key=request_key,
    )
    return TableAccountSummaryResponse.from_domain(summary)


@table_accounts_router.post("/{table_id}/account/checkout", response_model=TableAccountSummaryResponse)
async def checkout_table_account(
    table_id: UUID, body: TableCheckoutRequest, request_key: RequestKey,
    actor: Cashier, session: DatabaseSession,
) -> TableAccountSummaryResponse:
    quantities = {item.item_id: item.quantity for item in body.items}
    if len(quantities) != len(body.items):
        raise InvalidPaymentRequestError("Cada producto debe aparecer una sola vez por línea")
    result = await RecordTableCheckout(SqlAlchemyTableAccountRepository(session))(
        actor=actor, table_id=table_id, account_id=body.account_id, key=request_key,
        legs=tuple((p.amount, p.method_code, p.reference_code) for p in body.payments),
        items=quantities,
    )
    return TableAccountSummaryResponse.from_domain(result)
