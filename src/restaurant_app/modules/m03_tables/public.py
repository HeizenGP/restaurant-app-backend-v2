"""Public table contracts for local-order coordination in one transaction."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m03_tables.adapters.outbound.repositories import (
    SqlAlchemyTableRepository,
)
from restaurant_app.modules.m03_tables.domain.entities import RestaurantTable


class TableLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._tables = SqlAlchemyTableRepository(session)

    async def get_table(self, table_id: UUID, *, lock: bool = False) -> RestaurantTable | None:
        return await self._tables.get_table(table_id, lock=lock)


class TableOccupancy:
    """M04 may occupy a physically verified table; release remains M03 admin-only."""

    def __init__(self, session: AsyncSession) -> None:
        self._tables = SqlAlchemyTableRepository(session)

    async def lock_table(self, table_id: UUID) -> RestaurantTable | None:
        return await self._tables.get_table(table_id, lock=True, write=True)

    async def occupy(self, table_id: UUID, *, actor_id: UUID | None = None) -> RestaurantTable:
        return await self._tables.set_occupancy(table_id, is_occupied=True, actor_id=actor_id)


class TableAccountRegistry:
    """Public M03 contract used by M04 to attach orders to one table visit."""

    def __init__(self, session: AsyncSession) -> None:
        self._tables = SqlAlchemyTableRepository(session)

    async def get_or_create(
        self,
        table_id: UUID,
        *,
        customer_user_id: UUID | None,
        guest_session_id: UUID | None,
        opened_by_user_id: UUID | None,
    ) -> UUID:
        return await self._tables.get_or_create_open_account(
            table_id,
            customer_user_id=customer_user_id,
            guest_session_id=guest_session_id,
            opened_by_user_id=opened_by_user_id,
        )
