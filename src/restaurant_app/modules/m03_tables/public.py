"""Read-only table lookup exported to the local-order slice."""

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
