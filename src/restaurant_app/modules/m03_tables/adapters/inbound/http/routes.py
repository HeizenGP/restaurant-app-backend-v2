"""M03 REST endpoints for approved RF-M03-01/02/04 only."""

from uuid import UUID

from fastapi import APIRouter, status

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.public import AuthorizeRoles, RoleCode
from restaurant_app.modules.m03_tables.adapters.inbound.http.dependencies import (
    TableAdmin,
    TableStaff,
)
from restaurant_app.modules.m03_tables.adapters.inbound.http.schemas import (
    PublicTableResponse,
    StaffTableResponse,
    TableCreateRequest,
    TableOccupancyRequest,
    TablePatchRequest,
)
from restaurant_app.modules.m03_tables.adapters.outbound import SqlAlchemyTableRepository
from restaurant_app.modules.m03_tables.application.use_cases.list_tables import (
    GetTable,
    ListTables,
)
from restaurant_app.modules.m03_tables.application.use_cases.save_table import SaveTable
from restaurant_app.modules.m03_tables.application.use_cases.set_table_occupancy import (
    SetTableOccupancy,
)

router = APIRouter(prefix="/tables", tags=["M03 tables"])


@router.get("", response_model=list[PublicTableResponse])
async def list_tables(session: DatabaseSession) -> list[PublicTableResponse]:
    tables = await ListTables(SqlAlchemyTableRepository(session))()
    return [PublicTableResponse.from_domain(table) for table in tables]


@router.get("/{table_id}", response_model=StaffTableResponse)
async def get_table(
    table_id: UUID, actor: TableStaff, session: DatabaseSession
) -> StaffTableResponse:
    table = await GetTable(SqlAlchemyTableRepository(session))(actor=actor, table_id=table_id)
    return StaffTableResponse.from_domain(table)


@router.post("", response_model=StaffTableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    payload: TableCreateRequest, actor: TableAdmin, session: DatabaseSession
) -> StaffTableResponse:
    table = await SaveTable(SqlAlchemyTableRepository(session))(
        actor=actor,
        code=payload.code,
        area_label=payload.area_label,
        change_area_label=True,
    )
    return StaffTableResponse.from_domain(table)


@router.patch("/{table_id}", response_model=StaffTableResponse)
async def update_table(
    table_id: UUID, payload: TablePatchRequest, actor: TableAdmin, session: DatabaseSession
) -> StaffTableResponse:
    table = await SaveTable(SqlAlchemyTableRepository(session))(
        actor=actor,
        table_id=table_id,
        code=payload.code,
        area_label=payload.area_label,
        change_area_label="area_label" in payload.model_fields_set,
    )
    return StaffTableResponse.from_domain(table)


@router.patch("/{table_id}/occupancy", response_model=StaffTableResponse)
async def set_table_occupancy(
    table_id: UUID, payload: TableOccupancyRequest, actor: TableStaff, session: DatabaseSession
) -> StaffTableResponse:
    if not payload.is_occupied:
        AuthorizeRoles(RoleCode.ADMIN)(actor)
    table = await SetTableOccupancy(SqlAlchemyTableRepository(session))(
        actor=actor, table_id=table_id, is_occupied=payload.is_occupied
    )
    return StaffTableResponse.from_domain(table)
