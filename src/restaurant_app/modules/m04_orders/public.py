"""Read-only M04 contract for the future M06 advance slice.

Consumers depend on this snapshot, never on M04 persistence or domain internals.
The caller supplies its shared transaction and decides whether to lock the order.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m04_orders.adapters.outbound.repositories import (
    SqlAlchemyOrderRepository,
)


@dataclass(frozen=True, slots=True)
class OrderForAdvance:
    id: UUID
    modality: str
    status: str
    total_amount: Decimal
    customer_user_id: UUID | None
    guest_session_id: UUID | None


class AdvanceOrderReader(Protocol):
    async def get_order(self, order_id: UUID, *, lock: bool = False) -> OrderForAdvance | None: ...


class SqlAlchemyAdvanceOrderReader:
    def __init__(self, session: AsyncSession) -> None:
        self._orders = SqlAlchemyOrderRepository(session)

    async def get_order(self, order_id: UUID, *, lock: bool = False) -> OrderForAdvance | None:
        order = await self._orders.get_order(order_id, lock=lock)
        if order is None:
            return None
        return OrderForAdvance(
            id=order.id,
            modality=order.modality.value,
            status=order.status,
            total_amount=order.total_amount,
            customer_user_id=order.customer_user_id,
            guest_session_id=order.guest_session_id,
        )
