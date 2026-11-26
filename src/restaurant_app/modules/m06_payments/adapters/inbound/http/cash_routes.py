"""Register operations over M06 collections and persisted shifts."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.adapters.outbound.models import UserModel
from restaurant_app.modules.m06_payments.adapters.inbound.http.dependencies import Cashier
from restaurant_app.modules.m06_payments.adapters.outbound.cash_shifts import get_open_shift
from restaurant_app.modules.m06_payments.adapters.outbound.models import CashShiftModel, PaymentModel
from restaurant_app.modules.m06_payments.domain.errors import PaymentConflictError

router = APIRouter(prefix="/cash-shifts", tags=["M06 register"])
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class OpenShiftRequest(BaseModel):
    initial_amount: Money
    notes: str | None = Field(default=None, max_length=500)


class CloseShiftRequest(BaseModel):
    counted_cash: Money
    notes: str | None = Field(default=None, max_length=500)


class CashShiftResponse(BaseModel):
    id: UUID
    opened_at: datetime
    opened_by: str
    initial_amount: Decimal
    opening_notes: str | None
    closed_at: datetime | None
    closed_by: str | None
    counted_cash: Decimal | None
    closing_notes: str | None
    totals: dict[str, Decimal]
    expected_cash: Decimal
    difference: Decimal | None


async def _summaries(session: DatabaseSession, shifts: list[CashShiftModel]) -> list[CashShiftResponse]:
    if not shifts:
        return []
    users = {shift.opened_by_id for shift in shifts}
    users.update(shift.closed_by_id for shift in shifts if shift.closed_by_id)
    names = dict((await session.execute(
        select(UserModel.id, UserModel.display_name).where(UserModel.id.in_(users))
    )).tuples().all())
    totals: dict[UUID, dict[str, Decimal]] = {}
    rows = await session.execute(
        select(PaymentModel.cash_shift_id, PaymentModel.method_code, func.sum(PaymentModel.amount))
        .where(PaymentModel.cash_shift_id.in_([shift.id for shift in shifts]))
        .group_by(PaymentModel.cash_shift_id, PaymentModel.method_code)
    )
    for shift_id, method, amount in rows:
        if shift_id is not None and method is not None:
            totals.setdefault(shift_id, {})[method] = amount

    result = []
    for shift in shifts:
        methods = totals.get(shift.id, {})
        expected = shift.initial_amount + methods.get("EFECTIVO", Decimal(0))
        result.append(CashShiftResponse(
            id=shift.id,
            opened_at=shift.opened_at,
            opened_by=names[shift.opened_by_id],
            initial_amount=shift.initial_amount,
            opening_notes=shift.opening_notes,
            closed_at=shift.closed_at,
            closed_by=names.get(shift.closed_by_id) if shift.closed_by_id else None,
            counted_cash=shift.counted_cash,
            closing_notes=shift.closing_notes,
            totals=methods,
            expected_cash=expected,
            difference=shift.counted_cash - expected if shift.counted_cash is not None else None,
        ))
    return result


@router.get("/current")
async def current_shift(actor: Cashier, session: DatabaseSession) -> CashShiftResponse | None:
    shift = await get_open_shift(session)
    return (await _summaries(session, [shift]))[0] if shift else None


@router.get("")
async def list_shifts(
    actor: Cashier,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CashShiftResponse]:
    shifts = await session.scalars(
        select(CashShiftModel).where(CashShiftModel.closed_at.is_not(None))
        .order_by(CashShiftModel.opened_at.desc(), CashShiftModel.id)
        .limit(limit).offset(offset)
    )
    return await _summaries(session, list(shifts))


@router.post("", status_code=201)
async def open_shift(body: OpenShiftRequest, actor: Cashier, session: DatabaseSession) -> CashShiftResponse:
    if await get_open_shift(session, lock=True) is not None:
        raise PaymentConflictError("Ya existe un turno de caja abierto")
    assert actor.user_id is not None
    shift = CashShiftModel(
        opened_at=datetime.now(UTC), opened_by_id=actor.user_id,
        initial_amount=body.initial_amount, opening_notes=body.notes,
    )
    session.add(shift)
    await session.flush()
    return (await _summaries(session, [shift]))[0]


@router.post("/{shift_id}/close")
async def close_shift(
    shift_id: UUID, body: CloseShiftRequest, actor: Cashier, session: DatabaseSession
) -> CashShiftResponse:
    shift = await get_open_shift(session, lock=True)
    if shift is None or shift.id != shift_id:
        raise PaymentConflictError("Ese turno ya no está abierto")
    assert actor.user_id is not None
    shift.closed_at = datetime.now(UTC)
    shift.closed_by_id = actor.user_id
    shift.counted_cash = body.counted_cash
    shift.closing_notes = body.notes
    await session.flush()
    return (await _summaries(session, [shift]))[0]
