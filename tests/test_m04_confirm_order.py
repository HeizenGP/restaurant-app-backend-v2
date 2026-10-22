"""Isolated authorization, state and port orchestration for 08.07."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError
from restaurant_app.modules.m02_catalog_stock.public import StockConfirmationError
from restaurant_app.modules.m04_orders.application.use_cases.confirm_order import ConfirmOrder
from restaurant_app.modules.m04_orders.domain.entities import (
    Channel,
    Modality,
    Order,
    OrderLine,
    TableAvailability,
)
from restaurant_app.modules.m04_orders.domain.errors import (
    OrderConflictError,
    ProductUnavailableError,
)
from restaurant_app.modules.m06_payments.public import VerifiedAdvance


def actor(role: RoleCode) -> Principal:
    return Principal(uuid4(), uuid4(), frozenset({role}), SessionKind.USER)


def approved_order(*, modality: Modality = Modality.LOCAL) -> Order:
    now = datetime.now(UTC)
    return Order(
        id=uuid4(),
        modality=modality,
        channel=Channel.APP,
        status="APPROVED",
        customer_user_id=uuid4(),
        guest_session_id=None,
        created_by_user_id=None,
        table_id=uuid4() if modality is Modality.LOCAL else None,
        delivery_address="Av. Lima 123" if modality is Modality.DELIVERY else None,
        contact_name="Ana",
        contact_phone="999111222",
        total_amount=Decimal("20.00"),
        lines=(OrderLine(uuid4(), "Chaufa", 2, Decimal("10.00"), uuid4()),),
        created_at=now,
        decided_by_user_id=uuid4(),
        decided_at=now,
        table_verified_at=now if modality is Modality.LOCAL else None,
    )


def handler(order: Order):
    now = datetime.now(UTC)
    orders = SimpleNamespace(
        find_confirmation=AsyncMock(return_value=None),
        get_order=AsyncMock(return_value=order),
        mark_confirmed=AsyncMock(return_value=replace(order, status="CONFIRMED")),
        record_confirmation=AsyncMock(),
    )
    tables = SimpleNamespace(
        get_table=AsyncMock(
            return_value=TableAvailability(
                order.table_id or uuid4(), True, now - timedelta(minutes=1)
            )
        )
    )
    stock = SimpleNamespace(debit_order=AsyncMock())
    advances = SimpleNamespace(
        get_verified_advance=AsyncMock(
            return_value=VerifiedAdvance(order.id, Decimal("10.00"), now)
        )
    )
    tickets = SimpleNamespace(
        create_for_order=AsyncMock(return_value=uuid4()),
        exists_for_order=AsyncMock(return_value=True),
    )
    return ConfirmOrder(orders, tables, stock, advances, tickets), orders, stock, advances, tickets


@pytest.mark.asyncio
async def test_local_app_confirmation_uses_ports_and_requires_current_verification() -> None:
    order = approved_order()
    use_case, orders, stock, advances, tickets = handler(order)
    waiter = actor(RoleCode.WAITER)
    result = await use_case(actor=waiter, order_id=order.id, request_key="local-confirm")
    assert result.status == "CONFIRMED"
    allocation = stock.debit_order.await_args.args[0][0]
    assert allocation.order_item_id == order.lines[0].id
    assert allocation.quantity == 2
    assert stock.debit_order.await_args.kwargs["actor_id"] == waiter.user_id
    advances.get_verified_advance.assert_not_awaited()
    tickets.create_for_order.assert_awaited_once_with(order.id)
    orders.record_confirmation.assert_awaited_once()
    orders.get_order.return_value = replace(order, table_verified_at=None)
    with pytest.raises(OrderConflictError):
        await use_case(actor=waiter, order_id=order.id, request_key="unverified")


@pytest.mark.asyncio
async def test_remote_requires_admin_approved_state_and_exact_advance() -> None:
    order = approved_order(modality=Modality.DELIVERY)
    use_case, orders, stock, advances, _ = handler(order)
    with pytest.raises(AuthorizationError):
        await use_case(actor=actor(RoleCode.WAITER), order_id=order.id, request_key="no-role")
    admin = actor(RoleCode.ADMIN)
    advances.get_verified_advance.return_value = None
    with pytest.raises(OrderConflictError):
        await use_case(actor=admin, order_id=order.id, request_key="no-advance")
    stock.debit_order.assert_not_awaited()
    advances.get_verified_advance.return_value = VerifiedAdvance(
        order.id, Decimal("9.99"), datetime.now(UTC)
    )
    with pytest.raises(OrderConflictError):
        await use_case(actor=admin, order_id=order.id, request_key="wrong-advance")
    orders.get_order.return_value = replace(order, status="REJECTED")
    with pytest.raises(OrderConflictError):
        await use_case(actor=admin, order_id=order.id, request_key="rejected")
    stock.debit_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_stock_failure_prevents_confirmation_and_ticket() -> None:
    order = approved_order()
    use_case, orders, stock, _, tickets = handler(order)
    stock.debit_order.side_effect = StockConfirmationError("insufficient stock")
    with pytest.raises(ProductUnavailableError):
        await use_case(actor=actor(RoleCode.WAITER), order_id=order.id, request_key="no-stock")
    orders.mark_confirmed.assert_not_awaited()
    tickets.create_for_order.assert_not_awaited()
    orders.record_confirmation.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_replay_does_not_repeat_effects() -> None:
    order = replace(approved_order(), status="CONFIRMED")
    use_case, orders, stock, advances, tickets = handler(order)
    orders.find_confirmation.return_value = order.id
    result = await use_case(actor=actor(RoleCode.ADMIN), order_id=order.id, request_key="same")
    assert result == order
    tickets.exists_for_order.assert_awaited_once_with(order.id)
    stock.debit_order.assert_not_awaited()
    advances.get_verified_advance.assert_not_awaited()
    orders.mark_confirmed.assert_not_awaited()
