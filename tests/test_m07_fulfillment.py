"""08.09 M07 handler tests with framework-free fake ports."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError
from restaurant_app.modules.m04_orders.public import OrderForFulfillment
from restaurant_app.modules.m05_kitchen.public import KitchenProgress
from restaurant_app.modules.m07_fulfillment.application.use_cases.close_order import CloseOrder
from restaurant_app.modules.m07_fulfillment.application.use_cases.get_tracking import GetTracking
from restaurant_app.modules.m07_fulfillment.application.use_cases.record_fulfillment import (
    RecordFulfillment,
)
from restaurant_app.modules.m07_fulfillment.domain.entities import Fulfillment, FulfillmentKind
from restaurant_app.modules.m07_fulfillment.domain.errors import (
    FulfillmentConflictError,
    FulfillmentNotFoundError,
)


def actor(*roles: RoleCode) -> Principal:
    return Principal(
        user_id=uuid4(),
        session_id=uuid4(),
        roles=frozenset(roles),
        kind=SessionKind.USER,
    )


def order(modality: str = "LOCAL", status: str = "CONFIRMED") -> OrderForFulfillment:
    return OrderForFulfillment(
        id=uuid4(),
        modality=modality,
        status=status,
        total_amount=Decimal("20.00"),
        created_at=datetime.now(UTC),
        closed_by_user_id=None,
        closed_at=None,
    )


def ports(
    snapshot: OrderForFulfillment,
) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    orders = SimpleNamespace(
        get_order=AsyncMock(return_value=snapshot),
        get_visible_order=AsyncMock(return_value=snapshot),
        close_order=AsyncMock(
            return_value=replace(
                snapshot, status="CLOSED", closed_by_user_id=uuid4(), closed_at=datetime.now(UTC)
            )
        ),
    )
    kitchen = SimpleNamespace(
        get_progress=AsyncMock(return_value=KitchenProgress("READY", None, datetime.now(UTC)))
    )
    payments = SimpleNamespace(get_balance=AsyncMock(return_value=Decimal("0.00")))
    fulfillments = SimpleNamespace(
        find_request=AsyncMock(return_value=None),
        get=AsyncMock(return_value=None),
        record=AsyncMock(),
        record_close=AsyncMock(),
    )
    return orders, kitchen, payments, fulfillments


@pytest.mark.asyncio
async def test_service_requires_waiter_local_confirmed_ready_and_writes_once() -> None:
    snapshot = order()
    orders, kitchen, _, fulfillments = ports(snapshot)
    waiter = actor(RoleCode.WAITER)
    served = Fulfillment(
        uuid4(), snapshot.id, FulfillmentKind.SERVED, waiter.user_id, datetime.now(UTC)
    )
    fulfillments.record.return_value = served
    handler = RecordFulfillment(
        orders,
        kitchen,
        fulfillments,
        kind=FulfillmentKind.SERVED,
        modality="LOCAL",
        role=RoleCode.WAITER,
    )
    with pytest.raises(AuthorizationError):
        await handler(actor=actor(RoleCode.ADMIN), order_id=snapshot.id, request_key="role")
    kitchen.get_progress.return_value = KitchenProgress("PREPARING", None, None)
    with pytest.raises(FulfillmentConflictError):
        await handler(actor=waiter, order_id=snapshot.id, request_key="early")
    kitchen.get_progress.return_value = KitchenProgress("READY", None, datetime.now(UTC))
    result = await handler(actor=waiter, order_id=snapshot.id, request_key="serve")
    assert result == served
    assert orders.get_order.await_args.kwargs == {"lock": True}
    fulfillments.record.assert_awaited_once()
    fulfillments.find_request.return_value = snapshot.id
    fulfillments.get.return_value = served
    assert await handler(actor=waiter, order_id=snapshot.id, request_key="serve") == served
    fulfillments.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_handover_checks_modality_and_ready() -> None:
    snapshot = order("PICKUP")
    orders, kitchen, _, fulfillments = ports(snapshot)
    handler = RecordFulfillment(
        orders,
        kitchen,
        fulfillments,
        kind=FulfillmentKind.PICKED_UP,
        modality="PICKUP",
        role=RoleCode.ADMIN,
    )
    with pytest.raises(AuthorizationError):
        await handler(actor=actor(RoleCode.WAITER), order_id=snapshot.id, request_key="role")
    orders.get_order.return_value = replace(snapshot, modality="DELIVERY")
    with pytest.raises(FulfillmentConflictError):
        await handler(actor=actor(RoleCode.ADMIN), order_id=snapshot.id, request_key="modality")
    orders.get_order.return_value = snapshot
    kitchen.get_progress.return_value = None
    with pytest.raises(FulfillmentConflictError):
        await handler(actor=actor(RoleCode.ADMIN), order_id=snapshot.id, request_key="early")
    fulfillments.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_rejects_debt_or_missing_service_then_writes_both_records() -> None:
    snapshot = order()
    orders, kitchen, payments, fulfillments = ports(snapshot)
    administrator = actor(RoleCode.ADMIN)
    handler = CloseOrder(orders, kitchen, payments, fulfillments)
    with pytest.raises(AuthorizationError):
        await handler(actor=actor(RoleCode.CASHIER), order_id=snapshot.id, request_key="role")
    with pytest.raises(FulfillmentConflictError, match="service or delivery"):
        await handler(actor=administrator, order_id=snapshot.id, request_key="missing")
    fulfillments.get.return_value = Fulfillment(
        uuid4(), snapshot.id, FulfillmentKind.SERVED, administrator.user_id, datetime.now(UTC)
    )
    payments.get_balance.return_value = Decimal("20.00")
    with pytest.raises(FulfillmentConflictError, match=r"S/ 20\.00"):
        await handler(actor=administrator, order_id=snapshot.id, request_key="debt")
    orders.close_order.assert_not_awaited()
    payments.get_balance.return_value = Decimal("0.00")
    closed = await handler(actor=administrator, order_id=snapshot.id, request_key="close")
    assert closed.status == "CLOSED"
    orders.close_order.assert_awaited_once_with(snapshot.id, actor_id=administrator.user_id)
    fulfillments.record_close.assert_awaited_once()
    fulfillments.find_request.return_value = snapshot.id
    orders.get_order.return_value = closed
    assert await handler(actor=administrator, order_id=snapshot.id, request_key="close") == closed
    orders.close_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_tracking_composes_status_and_hides_invisible_order() -> None:
    snapshot = order(status="REQUESTED")
    orders, kitchen, payments, fulfillments = ports(snapshot)
    principal = actor(RoleCode.CUSTOMER)
    handler = GetTracking(orders, kitchen, payments, fulfillments)
    kitchen.get_progress.return_value = None
    payments.get_balance.return_value = Decimal("20.00")
    initial = await handler(actor=principal, order_id=snapshot.id)
    assert (initial.stage, initial.payment_status, initial.balance) == (
        "REQUESTED",
        "UNPAID",
        Decimal("20.00"),
    )
    orders.get_visible_order.return_value = replace(snapshot, status="CONFIRMED")
    kitchen.get_progress.return_value = KitchenProgress("READY", None, datetime.now(UTC))
    payments.get_balance.return_value = Decimal("0.00")
    ready = await handler(actor=principal, order_id=snapshot.id)
    assert (ready.stage, ready.payment_status) == ("READY", "PAID")
    orders.get_visible_order.return_value = None
    with pytest.raises(FulfillmentNotFoundError):
        await handler(actor=actor(RoleCode.CUSTOMER), order_id=snapshot.id)
