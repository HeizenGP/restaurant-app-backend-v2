"""Isolated M03 handler coverage for RF-M03-01/02/04."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError
from restaurant_app.modules.m03_tables.application.use_cases.list_tables import (
    GetTable,
    ListTables,
)
from restaurant_app.modules.m03_tables.application.use_cases.save_table import SaveTable
from restaurant_app.modules.m03_tables.application.use_cases.set_table_occupancy import (
    SetTableOccupancy,
)
from restaurant_app.modules.m03_tables.domain.entities import RestaurantTable
from restaurant_app.modules.m03_tables.domain.errors import (
    InvalidTableValueError,
    TableNotFoundError,
)


def principal(*roles: RoleCode, kind: SessionKind = SessionKind.USER) -> Principal:
    return Principal(
        user_id=uuid4() if kind is SessionKind.USER else None,
        session_id=uuid4(),
        roles=frozenset(roles),
        kind=kind,
    )


def table() -> RestaurantTable:
    return RestaurantTable(
        id=uuid4(),
        code="M-01",
        area_label="Salón",
        is_occupied=False,
        updated_at=datetime.now(UTC),
        updated_by_user_id=None,
    )


def repository() -> SimpleNamespace:
    return SimpleNamespace(
        list_tables=AsyncMock(),
        get_table=AsyncMock(),
        create_table=AsyncMock(),
        update_table=AsyncMock(),
        set_occupancy=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_public_distribution_and_staff_detail() -> None:
    repo = repository()
    existing = table()
    repo.list_tables.return_value = [existing]
    repo.get_table.return_value = existing
    assert await ListTables(repo)() == [existing]
    assert await GetTable(repo)(actor=principal(RoleCode.WAITER), table_id=existing.id) == existing
    with pytest.raises(AuthorizationError):
        await GetTable(repo)(actor=principal(RoleCode.CUSTOMER), table_id=existing.id)
    with pytest.raises(AuthorizationError):
        await GetTable(repo)(actor=principal(kind=SessionKind.GUEST), table_id=existing.id)
    repo.get_table.return_value = None
    with pytest.raises(TableNotFoundError):
        await GetTable(repo)(actor=principal(RoleCode.ADMIN), table_id=uuid4())


@pytest.mark.asyncio
async def test_only_admin_saves_distribution_and_validates_values() -> None:
    repo = repository()
    existing = table()
    repo.create_table.return_value = existing
    repo.update_table.return_value = existing
    handler = SaveTable(repo)
    with pytest.raises(AuthorizationError):
        await handler(
            actor=principal(RoleCode.WAITER),
            code="M-01",
            area_label="Salón",
            change_area_label=True,
        )
    repo.create_table.assert_not_awaited()
    admin = principal(RoleCode.ADMIN)
    with pytest.raises(InvalidTableValueError):
        await handler(actor=admin, code="  ", area_label=None, change_area_label=True)
    with pytest.raises(InvalidTableValueError):
        await handler(actor=admin, code="M-01", area_label="  ", change_area_label=True)
    created = await handler(
        actor=admin, code=" M-01 ", area_label=" Salón ", change_area_label=True
    )
    assert created == existing
    repo.create_table.assert_awaited_once_with(
        code="M-01", area_label="Salón", actor_id=admin.user_id
    )
    with pytest.raises(InvalidTableValueError):
        await handler(
            actor=admin,
            table_id=created.id,
            code=None,
            area_label=None,
            change_area_label=False,
        )
    await handler(
        actor=principal(RoleCode.SUPER_ADMIN),
        table_id=created.id,
        code=None,
        area_label=None,
        change_area_label=True,
    )
    repo.update_table.assert_awaited_once()


@pytest.mark.asyncio
async def test_waiter_can_occupy_but_only_admin_can_release() -> None:
    repo = repository()
    existing = table()
    repo.set_occupancy.return_value = existing
    handler = SetTableOccupancy(repo)
    waiter = principal(RoleCode.WAITER)
    await handler(actor=waiter, table_id=existing.id, is_occupied=True)
    repo.set_occupancy.assert_awaited_once_with(
        existing.id, is_occupied=True, actor_id=waiter.user_id
    )
    with pytest.raises(AuthorizationError):
        await handler(actor=waiter, table_id=existing.id, is_occupied=False)
    with pytest.raises(AuthorizationError):
        await handler(actor=principal(RoleCode.CASHIER), table_id=existing.id, is_occupied=True)
    assert repo.set_occupancy.await_count == 1
    admin = principal(RoleCode.ADMIN)
    await handler(actor=admin, table_id=existing.id, is_occupied=False)
    repo.set_occupancy.assert_awaited_with(existing.id, is_occupied=False, actor_id=admin.user_id)
    await handler(actor=principal(RoleCode.SUPER_ADMIN), table_id=existing.id, is_occupied=False)
