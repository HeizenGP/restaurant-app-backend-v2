"""Manual occupation or administrator-only release (RF-M03-04)."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m03_tables.application.ports.table_repository import TableRepository
from restaurant_app.modules.m03_tables.domain.entities import RestaurantTable


class SetTableOccupancy:
    def __init__(self, tables: TableRepository) -> None:
        self._tables = tables
        self._authorize_staff = AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)
        self._authorize_release = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(
        self, *, actor: Principal, table_id: UUID, is_occupied: bool
    ) -> RestaurantTable:
        self._authorize_staff(actor)
        if not is_occupied:
            self._authorize_release(actor)
        assert actor.user_id is not None
        return await self._tables.set_occupancy(
            table_id, is_occupied=is_occupied, actor_id=actor.user_id
        )
