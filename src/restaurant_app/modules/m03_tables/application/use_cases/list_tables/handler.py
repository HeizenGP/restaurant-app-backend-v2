"""Public distribution and authorized staff occupancy reads (RF-M03-01/02/04)."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m03_tables.application.ports.table_repository import TableRepository
from restaurant_app.modules.m03_tables.domain.entities import RestaurantTable
from restaurant_app.modules.m03_tables.domain.errors import TableNotFoundError


class ListTables:
    def __init__(self, tables: TableRepository) -> None:
        self._tables = tables

    async def __call__(self) -> list[RestaurantTable]:
        return await self._tables.list_tables()


class GetTable:
    def __init__(self, tables: TableRepository) -> None:
        self._tables = tables
        self._authorize = AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)

    async def __call__(self, *, actor: Principal, table_id: UUID) -> RestaurantTable:
        self._authorize(actor)
        table = await self._tables.get_table(table_id)
        if table is None:
            raise TableNotFoundError
        return table
