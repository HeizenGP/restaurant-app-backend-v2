"""Persistence operations consumed by M03 use cases."""

from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m03_tables.domain.entities import RestaurantTable


class TableRepository(Protocol):
    async def list_tables(self) -> list[RestaurantTable]: ...

    async def get_table(self, table_id: UUID) -> RestaurantTable | None: ...

    async def create_table(
        self, *, code: str, area_label: str | None, actor_id: UUID
    ) -> RestaurantTable: ...

    async def update_table(
        self,
        table_id: UUID,
        *,
        code: str | None,
        area_label: str | None,
        change_area_label: bool,
        actor_id: UUID,
    ) -> RestaurantTable: ...

    async def set_occupancy(
        self, table_id: UUID, *, is_occupied: bool, actor_id: UUID | None = None
    ) -> RestaurantTable: ...
