"""M05 public contract for creating one ticket inside the caller's UoW."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m05_kitchen.adapters.outbound.models import KitchenTicketModel


class KitchenTicketConflict(Exception):
    """A ticket already exists for the order."""


class TicketIssuer(Protocol):
    async def create_for_order(self, order_id: UUID) -> UUID: ...

    async def exists_for_order(self, order_id: UUID) -> bool: ...


class SqlAlchemyTicketIssuer:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_for_order(self, order_id: UUID) -> UUID:
        ticket = KitchenTicketModel(order_id=order_id)
        self._session.add(ticket)
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise KitchenTicketConflict("A ticket already exists for this order") from error
        return ticket.id

    async def exists_for_order(self, order_id: UUID) -> bool:
        return (
            await self._session.scalar(
                select(KitchenTicketModel.id).where(KitchenTicketModel.order_id == order_id)
            )
        ) is not None
