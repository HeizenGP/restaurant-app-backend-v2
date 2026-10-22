"""M05 public contracts for ticket creation and preparation progress."""

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True, slots=True)
class KitchenProgress:
    status: str
    started_at: datetime | None
    ready_at: datetime | None


class KitchenProgressReader(Protocol):
    async def get_progress(self, order_id: UUID) -> KitchenProgress | None: ...


class SqlAlchemyKitchenProgressReader:
    """Observe committed kitchen state without exposing M05 persistence to M07."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_progress(self, order_id: UUID) -> KitchenProgress | None:
        ticket = (
            await self._session.scalars(
                select(KitchenTicketModel).where(KitchenTicketModel.order_id == order_id)
            )
        ).one_or_none()
        if ticket is None:
            return None
        return KitchenProgress(ticket.status, ticket.started_at, ticket.ready_at)
