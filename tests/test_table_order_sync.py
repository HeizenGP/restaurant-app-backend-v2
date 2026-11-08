"""Unit tests for table-order synchronization, occupancy on creation, and unpaid release guard."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m04_orders.application.use_cases.create_order import CreateOrder
from restaurant_app.modules.m04_orders.domain.entities import (
    Channel,
    Modality,
    Order,
    ProductQuote,
    RequestedItem,
    TableAvailability,
)
from restaurant_app.modules.m04_orders.domain.errors import InvalidOrderError


def make_user(role: RoleCode = RoleCode.CUSTOMER) -> Principal:
    return Principal(
        user_id=uuid4(),
        session_id=uuid4(),
        roles=frozenset({role}),
        kind=SessionKind.USER,
    )


@pytest.mark.asyncio
async def test_app_order_occupies_table_immediately() -> None:
    table_id = uuid4()
    product_id = uuid4()

    orders = SimpleNamespace(
        find_request=AsyncMock(return_value=None),
        create_order=AsyncMock(
            return_value=Order(
                id=uuid4(),
                modality=Modality.LOCAL,
                channel=Channel.APP,
                status="REQUESTED",
                customer_user_id=uuid4(),
                guest_session_id=None,
                created_by_user_id=None,
                table_id=table_id,
                delivery_address=None,
                contact_name=None,
                contact_phone=None,
                total_amount=Decimal("35.00"),
                lines=(),
                created_at=datetime.now(UTC),
                decided_by_user_id=None,
                decided_at=None,
                table_verified_at=None,
            )
        ),
        has_verified_active_table_order=AsyncMock(return_value=False),
    )
    products = SimpleNamespace(
        get_product=AsyncMock(
            return_value=ProductQuote(
                id=product_id,
                name="Aeropuerto de Pollo",
                price=Decimal("35.00"),
                is_available=True,
            )
        )
    )
    tables = SimpleNamespace(get_table=AsyncMock(return_value=TableAvailability(table_id, False)))
    table_occupancy = SimpleNamespace(
        lock_table=AsyncMock(return_value=TableAvailability(table_id, False)),
        occupy=AsyncMock(return_value=TableAvailability(table_id, True, datetime.now(UTC))),
    )

    handler = CreateOrder(orders, products, tables, waiter_tables=table_occupancy)
    customer = make_user()

    created = await handler(
        actor=customer,
        request_key="req-sync-1",
        modality=Modality.LOCAL,
        channel=Channel.APP,
        items=(RequestedItem(product_id, 1),),
        table_id=table_id,
        delivery_address=None,
        contact_name=None,
        contact_phone=None,
    )

    assert created is not None
    table_occupancy.occupy.assert_awaited_once_with(table_id, actor_id=customer.user_id)


@pytest.mark.asyncio
async def test_second_user_cannot_order_on_occupied_table() -> None:
    table_id = uuid4()
    product_id = uuid4()
    occupied_since = datetime.now(UTC)

    orders = SimpleNamespace(
        find_request=AsyncMock(return_value=None),
        create_order=AsyncMock(),
        has_verified_active_table_order=AsyncMock(return_value=False),
    )
    products = SimpleNamespace(
        get_product=AsyncMock(
            return_value=ProductQuote(
                id=product_id,
                name="Aeropuerto de Pollo",
                price=Decimal("35.00"),
                is_available=True,
            )
        )
    )
    tables = SimpleNamespace(
        get_table=AsyncMock(return_value=TableAvailability(table_id, True, occupied_since))
    )
    table_occupancy = SimpleNamespace(
        lock_table=AsyncMock(return_value=TableAvailability(table_id, True, occupied_since)),
        occupy=AsyncMock(),
    )

    handler = CreateOrder(orders, products, tables, waiter_tables=table_occupancy)
    second_customer = make_user()

    with pytest.raises(InvalidOrderError, match="The selected table is occupied"):
        await handler(
            actor=second_customer,
            request_key="req-sync-2",
            modality=Modality.LOCAL,
            channel=Channel.APP,
            items=(RequestedItem(product_id, 1),),
            table_id=table_id,
            delivery_address=None,
            contact_name=None,
            contact_phone=None,
        )

    table_occupancy.occupy.assert_not_awaited()
