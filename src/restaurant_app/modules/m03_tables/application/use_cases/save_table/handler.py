"""Create or edit the approved table distribution (RF-M03-01)."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m03_tables.application.ports.table_repository import TableRepository
from restaurant_app.modules.m03_tables.domain.entities import RestaurantTable
from restaurant_app.modules.m03_tables.domain.errors import InvalidTableValueError


class SaveTable:
    def __init__(self, tables: TableRepository) -> None:
        self._tables = tables
        self._authorize = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(
        self,
        *,
        actor: Principal,
        code: str | None,
        area_label: str | None,
        change_area_label: bool,
        table_id: UUID | None = None,
    ) -> RestaurantTable:
        self._authorize(actor)
        normalized_code = code.strip() if code is not None else None
        if normalized_code is not None and not 1 <= len(normalized_code) <= 24:
            raise InvalidTableValueError("Table code must contain 1 to 24 characters")
        normalized_area = area_label.strip() if area_label is not None else None
        if normalized_area is not None and not 1 <= len(normalized_area) <= 80:
            raise InvalidTableValueError("Area label must contain 1 to 80 characters")
        assert actor.user_id is not None
        if table_id is None:
            if normalized_code is None:
                raise InvalidTableValueError("Table code is required")
            return await self._tables.create_table(
                code=normalized_code,
                area_label=normalized_area,
                actor_id=actor.user_id,
            )
        if normalized_code is None and not change_area_label:
            raise InvalidTableValueError("At least one table field is required")
        return await self._tables.update_table(
            table_id,
            code=normalized_code,
            area_label=normalized_area,
            change_area_label=change_area_label,
            actor_id=actor.user_id,
        )
