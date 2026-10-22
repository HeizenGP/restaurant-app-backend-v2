"""Read-only M06 contracts for confirmation and future order closure."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m06_payments.adapters.outbound.collection_repositories import (
    SqlAlchemyCollectionRepository,
)
from restaurant_app.modules.m06_payments.adapters.outbound.repositories import (
    SqlAlchemyAdvanceRepository,
)
from restaurant_app.modules.m06_payments.domain.entities import required_advance


@dataclass(frozen=True, slots=True)
class VerifiedAdvance:
    order_id: UUID
    amount: Decimal
    recorded_at: datetime


class AdvanceReader(Protocol):
    async def get_verified_advance(self, order_id: UUID) -> VerifiedAdvance | None: ...


class SqlAlchemyAdvanceReader:
    """Use the caller's session; this reader never creates or repeats a payment."""

    def __init__(self, session: AsyncSession) -> None:
        self._advances = SqlAlchemyAdvanceRepository(session)

    async def get_verified_advance(self, order_id: UUID) -> VerifiedAdvance | None:
        payment = await self._advances.get_advance(order_id)
        if payment is None:
            return None
        return VerifiedAdvance(
            order_id=payment.order_id,
            amount=payment.amount,
            recorded_at=payment.recorded_at,
        )


def required_advance_amount(total_amount: Decimal) -> Decimal:
    """The approved 50% rule, exported without exposing M06 internals."""

    return required_advance(total_amount)


class PaymentBalanceReader(Protocol):
    async def get_balance(self, order_id: UUID, *, total_amount: Decimal) -> Decimal: ...


class SqlAlchemyPaymentBalanceReader:
    """Expose derived balance to M07 without implementing its close operation."""

    def __init__(self, session: AsyncSession) -> None:
        self._payments = SqlAlchemyCollectionRepository(session)

    async def get_balance(self, order_id: UUID, *, total_amount: Decimal) -> Decimal:
        return total_amount - await self._payments.sum_paid(order_id)
