"""Isolated M04 request registration and decision rules."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError
from restaurant_app.modules.m04_orders.application.use_cases.create_order import CreateOrder
from restaurant_app.modules.m04_orders.application.use_cases.decide_order import DecideOrder
from restaurant_app.modules.m04_orders.application.use_cases.get_order import GetOrder
from restaurant_app.modules.m04_orders.domain.entities import (
    Channel,
    Modality,
    Order,
    OrderLine,
    ProductQuote,
    RequestedItem,
    TableAvailability,
)
from restaurant_app.modules.m04_orders.domain.errors import (
    InvalidOrderError,
    OrderConflictError,
    OrderNotFoundError,
    ProductUnavailableError,
)


def principal(*roles: RoleCode, guest: bool = False) -> Principal:
    return Principal(
        user_id=None if guest else uuid4(),
        session_id=uuid4(),
        roles=frozenset(roles),
        kind=SessionKind.GUEST if guest else SessionKind.USER,
    )


def order(*, modality: Modality = Modality.LOCAL, status: str = "REQUESTED") -> Order:
    product_id = uuid4()
    return Order(
        id=uuid4(),
        modality=modality,
        channel=Channel.APP,
        status=status,
        customer_user_id=None,
        guest_session_id=None,
        created_by_user_id=None,
        table_id=uuid4() if modality is Modality.LOCAL else None,
        delivery_address="Av. Lima 123" if modality is Modality.DELIVERY else None,
        contact_name="Ana",
        contact_phone="999111222",
        total_amount=Decimal("24.00"),
        lines=(OrderLine(product_id, "Chaufa", 2, Decimal("12.00")),),
        created_at=datetime.now(UTC),
        decided_by_user_id=None,
        decided_at=None,
        table_verified_at=None,
    )


@pytest.mark.asyncio
async def test_create_app_guest_snapshots_total_and_rejects_disabled() -> None:
    orders = SimpleNamespace(find_request=AsyncMock(return_value=None), create_order=AsyncMock())
    product_id = uuid4()
    products = SimpleNamespace(
        get_product=AsyncMock(
            return_value=ProductQuote(product_id, "Chaufa", Decimal("12.00"), True)
        )
    )
    existing = order()
    assert existing.table_id is not None
    tables = SimpleNamespace(
        get_table=AsyncMock(return_value=TableAvailability(existing.table_id, False))
    )
    handler = CreateOrder(orders, products, tables)
    guest = principal(guest=True)
    orders.create_order.return_value = existing
    result = await handler(
        actor=guest,
        request_key="request-1",
        modality=Modality.LOCAL,
        channel=Channel.APP,
        items=(RequestedItem(product_id, 2),),
        table_id=existing.table_id,
        delivery_address=None,
        contact_name=None,
        contact_phone=None,
    )
    assert result == existing
    kwargs = orders.create_order.await_args.kwargs
    assert kwargs["guest_session_id"] == guest.session_id
    assert kwargs["customer_user_id"] is None
    assert kwargs["lines"][0].unit_price_snapshot == Decimal("12.00")
    assert kwargs["lines"][0].quantity == 2
    tables.get_table.return_value = TableAvailability(existing.table_id, True)
    with pytest.raises(InvalidOrderError):
        await handler(
            actor=guest,
            request_key="occupied-table",
            modality=Modality.LOCAL,
            channel=Channel.APP,
            items=(RequestedItem(product_id, 2),),
            table_id=existing.table_id,
            delivery_address=None,
            contact_name=None,
            contact_phone=None,
        )
    tables.get_table.return_value = TableAvailability(existing.table_id, False)
    products.get_product.return_value = ProductQuote(product_id, "Chaufa", Decimal("12"), False)
    with pytest.raises(ProductUnavailableError):
        await handler(
            actor=guest,
            request_key="request-2",
            modality=Modality.LOCAL,
            channel=Channel.APP,
            items=(RequestedItem(product_id, 2),),
            table_id=existing.table_id,
            delivery_address=None,
            contact_name=None,
            contact_phone=None,
        )


@pytest.mark.asyncio
async def test_creation_permissions_shape_and_idempotent_replay() -> None:
    existing = order(modality=Modality.PICKUP)
    orders = SimpleNamespace(
        find_request=AsyncMock(return_value=existing), create_order=AsyncMock()
    )
    products = SimpleNamespace(get_product=AsyncMock())
    tables = SimpleNamespace(get_table=AsyncMock())
    handler = CreateOrder(orders, products, tables)
    admin = principal(RoleCode.ADMIN)
    item = RequestedItem(uuid4(), 1)
    result = await handler(
        actor=admin,
        request_key="manual-1",
        modality=Modality.PICKUP,
        channel=Channel.WHATSAPP,
        items=(item,),
        table_id=None,
        delivery_address=None,
        contact_name="Ana",
        contact_phone="999111222",
    )
    assert result == existing
    orders.create_order.assert_not_awaited()
    with pytest.raises(AuthorizationError):
        await handler(
            actor=principal(RoleCode.WAITER),
            request_key="manual-2",
            modality=Modality.PICKUP,
            channel=Channel.PHONE,
            items=(item,),
            table_id=None,
            delivery_address=None,
            contact_name="Ana",
            contact_phone="999111222",
        )
    with pytest.raises(InvalidOrderError):
        await handler(
            actor=admin,
            request_key="manual-3",
            modality=Modality.DELIVERY,
            channel=Channel.PHONE,
            items=(item,),
            table_id=None,
            delivery_address=None,
            contact_name="Ana",
            contact_phone="999111222",
        )


@pytest.mark.asyncio
async def test_decision_requires_in_person_local_check_and_admin_for_delivery() -> None:
    local = order()
    repo = SimpleNamespace(
        get_order=AsyncMock(return_value=local), decide_order=AsyncMock(return_value=local)
    )
    handler = DecideOrder(repo)
    waiter = principal(RoleCode.WAITER)
    with pytest.raises(OrderConflictError):
        await handler(actor=waiter, order_id=local.id, approved=True, table_verified=False)
    repo.decide_order.assert_not_awaited()
    await handler(actor=waiter, order_id=local.id, approved=True, table_verified=True)
    repo.decide_order.assert_awaited_once_with(
        local.id, approved=True, actor_id=waiter.user_id, table_verified=True
    )
    admin = principal(RoleCode.ADMIN)
    await handler(actor=admin, order_id=local.id, approved=True, table_verified=True)
    repo.decide_order.assert_awaited_with(
        local.id, approved=True, actor_id=admin.user_id, table_verified=True
    )
    with pytest.raises(AuthorizationError):
        await handler(
            actor=principal(RoleCode.CASHIER),
            order_id=local.id,
            approved=False,
            table_verified=False,
        )
    repo.get_order.return_value = order(modality=Modality.DELIVERY)
    with pytest.raises(AuthorizationError):
        await handler(actor=waiter, order_id=local.id, approved=False, table_verified=False)
    repo.get_order.return_value = None
    with pytest.raises(OrderNotFoundError):
        await handler(
            actor=principal(RoleCode.ADMIN), order_id=uuid4(), approved=False, table_verified=False
        )


@pytest.mark.asyncio
async def test_read_hides_another_customers_order() -> None:
    existing = order()
    repo = SimpleNamespace(get_order=AsyncMock(return_value=existing))
    with pytest.raises(OrderNotFoundError):
        await GetOrder(repo)(actor=principal(RoleCode.CUSTOMER), order_id=existing.id)
    assert await GetOrder(repo)(actor=principal(RoleCode.ADMIN), order_id=existing.id) == existing
