"""Serialize register changes and new collections in the current transaction."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m06_payments.adapters.outbound.models import CashShiftModel
from restaurant_app.modules.m06_payments.domain.errors import PaymentConflictError


async def get_open_shift(session: AsyncSession, *, lock: bool = False) -> CashShiftModel | None:
    if lock:
        # A transaction lock also covers the interval in which no shift exists.
        await session.execute(text("SELECT pg_advisory_xact_lock(606, 1)"))
    return await session.scalar(select(CashShiftModel).where(CashShiftModel.closed_at.is_(None)))


async def require_open_shift(session: AsyncSession) -> CashShiftModel:
    shift = await get_open_shift(session, lock=True)
    if shift is None:
        raise PaymentConflictError("Abre un turno de caja antes de registrar un cobro")
    return shift
