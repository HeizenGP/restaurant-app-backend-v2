"""Read-only handover contract consumed by M06 cashier in ETAPA 08."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m07_fulfillment.adapters.outbound.models import FulfillmentModel


class HandoverReader(Protocol):
    async def has_handover(self, order_id: UUID, *, kind: str) -> bool: ...


class SqlAlchemyHandoverReader:
    """Only observes an already recorded pickup/delivery; does not create it."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_handover(self, order_id: UUID, *, kind: str) -> bool:
        return (
            await self._session.scalar(
                select(FulfillmentModel.id).where(
                    FulfillmentModel.order_id == order_id,
                    FulfillmentModel.kind == kind,
                )
            )
        ) is not None
