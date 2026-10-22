"""PostgreSQL adapter for existing kitchen tickets; no ticket creation here."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m05_kitchen.adapters.outbound.models import KitchenTicketModel
from restaurant_app.modules.m05_kitchen.domain.entities import KitchenStatus, KitchenTicket


class SqlAlchemyKitchenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _ticket(model: KitchenTicketModel) -> KitchenTicket:
        return KitchenTicket(
            id=model.id,
            order_id=model.order_id,
            status=KitchenStatus(model.status),
            created_at=model.created_at,
            started_at=model.started_at,
            ready_at=model.ready_at,
            started_by_user_id=model.started_by_user_id,
            ready_by_user_id=model.ready_by_user_id,
        )

    async def list_tickets(self) -> list[KitchenTicket]:
        models = (
            await self._session.scalars(
                select(KitchenTicketModel).order_by(
                    KitchenTicketModel.created_at, KitchenTicketModel.id
                )
            )
        ).all()
        return [self._ticket(model) for model in models]

    async def get_ticket(self, ticket_id: UUID, *, lock: bool = False) -> KitchenTicket | None:
        statement = select(KitchenTicketModel).where(KitchenTicketModel.id == ticket_id)
        if lock:
            statement = statement.with_for_update()
        model = (await self._session.scalars(statement)).one_or_none()
        return None if model is None else self._ticket(model)

    async def start(self, ticket_id: UUID, *, actor_id: UUID) -> KitchenTicket:
        model = await self._session.get(KitchenTicketModel, ticket_id)
        assert model is not None
        model.status = KitchenStatus.PREPARING.value
        model.started_by_user_id = actor_id
        model.started_at = func.clock_timestamp()
        await self._session.flush()
        await self._session.refresh(model)
        return self._ticket(model)

    async def mark_ready(self, ticket_id: UUID, *, actor_id: UUID) -> KitchenTicket:
        model = await self._session.get(KitchenTicketModel, ticket_id)
        assert model is not None
        model.status = KitchenStatus.READY.value
        model.ready_by_user_id = actor_id
        model.ready_at = func.clock_timestamp()
        await self._session.flush()
        await self._session.refresh(model)
        return self._ticket(model)
