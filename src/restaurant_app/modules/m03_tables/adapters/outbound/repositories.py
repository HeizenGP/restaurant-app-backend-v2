"""SQLAlchemy Async persistence for the approved restaurant_tables table."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m03_tables.adapters.outbound.models import RestaurantTableModel
from restaurant_app.modules.m03_tables.domain.entities import RestaurantTable
from restaurant_app.modules.m03_tables.domain.errors import (
    TableCodeConflictError,
    TableNotFoundError,
)


class SqlAlchemyTableRepository:
    """Use the request-owned transaction; lock rows for occupancy changes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _table(model: RestaurantTableModel) -> RestaurantTable:
        return RestaurantTable(
            id=model.id,
            code=model.code,
            area_label=model.area_label,
            is_occupied=model.is_occupied,
            updated_at=model.updated_at,
            updated_by_user_id=model.updated_by_user_id,
        )

    async def list_tables(self) -> list[RestaurantTable]:
        statement = select(RestaurantTableModel).order_by(
            RestaurantTableModel.area_label, RestaurantTableModel.code
        )
        return [self._table(row) for row in (await self._session.scalars(statement)).all()]

    async def get_table(self, table_id: UUID, *, lock: bool = False) -> RestaurantTable | None:
        if lock:
            model = (
                await self._session.scalars(
                    select(RestaurantTableModel)
                    .where(RestaurantTableModel.id == table_id)
                    .with_for_update(read=True)
                )
            ).one_or_none()
        else:
            model = await self._session.get(RestaurantTableModel, table_id)
        return None if model is None else self._table(model)

    async def create_table(
        self, *, code: str, area_label: str | None, actor_id: UUID
    ) -> RestaurantTable:
        model = RestaurantTableModel(code=code, area_label=area_label, updated_by_user_id=actor_id)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise TableCodeConflictError from error
        await self._session.refresh(model)
        return self._table(model)

    async def update_table(
        self,
        table_id: UUID,
        *,
        code: str | None,
        area_label: str | None,
        change_area_label: bool,
        actor_id: UUID,
    ) -> RestaurantTable:
        statement = (
            select(RestaurantTableModel)
            .where(RestaurantTableModel.id == table_id)
            .with_for_update()
        )
        model = (await self._session.scalars(statement)).one_or_none()
        if model is None:
            raise TableNotFoundError
        changed = False
        if code is not None and model.code != code:
            model.code = code
            changed = True
        if change_area_label and model.area_label != area_label:
            model.area_label = area_label
            changed = True
        if changed:
            model.updated_at = func.clock_timestamp()
            model.updated_by_user_id = actor_id
            try:
                await self._session.flush()
            except IntegrityError as error:
                raise TableCodeConflictError from error
            await self._session.refresh(model)
        return self._table(model)

    async def set_occupancy(
        self, table_id: UUID, *, is_occupied: bool, actor_id: UUID
    ) -> RestaurantTable:
        statement = (
            select(RestaurantTableModel)
            .where(RestaurantTableModel.id == table_id)
            .with_for_update()
        )
        model = (await self._session.scalars(statement)).one_or_none()
        if model is None:
            raise TableNotFoundError
        if model.is_occupied != is_occupied:
            model.is_occupied = is_occupied
            model.updated_at = func.clock_timestamp()
            model.updated_by_user_id = actor_id
            await self._session.flush()
            await self._session.refresh(model)
        return self._table(model)
