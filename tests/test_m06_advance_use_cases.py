"""Isolated 08.05 advance calculation, authorization and verification rules."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError
from restaurant_app.modules.m04_orders.public import OrderForAdvance
from restaurant_app.modules.m06_payments.application.use_cases.get_advance_summary import (
    GetAdvanceSummary,
)
from restaurant_app.modules.m06_payments.application.use_cases.verify_advance import VerifyAdvance
from restaurant_app.modules.m06_payments.domain.entities import AdvancePayment, required_advance
from restaurant_app.modules.m06_payments.domain.errors import (
    AdvanceConflictError,
    AdvanceNotFoundError,
)


def principal(*roles: RoleCode, guest: bool = False) -> Principal:
    return Principal(
        user_id=None if guest else uuid4(),
        session_id=uuid4(),
        roles=frozenset(roles),
        kind=SessionKind.GUEST if guest else SessionKind.USER,
    )


def order_for(
    actor: Principal, *, modality: str = "PICKUP", status: str = "APPROVED"
) -> OrderForAdvance:
    return OrderForAdvance(
        id=uuid4(),
        modality=modality,
        status=status,
        total_amount=Decimal("10.01"),
        customer_user_id=actor.user_id,
        guest_session_id=actor.session_id if actor.user_id is None else None,
    )


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        ("80.00", "40.00"),
        ("10.01", "5.01"),
        ("0.01", "0.01"),
        ("0.02", "0.01"),
    ],
)
def test_required_advance_rounds_up_to_cent(total: str, expected: str) -> None:
    assert required_advance(Decimal(total)) == Decimal(expected)
    with pytest.raises(ValueError):
        required_advance(Decimal("0.00"))


@pytest.mark.asyncio
@pytest.mark.parametrize("guest", [False, True], ids=["registered", "guest"])
async def test_quote_is_visible_to_owner_or_admin_only(guest: bool) -> None:
    owner = principal(guest=guest) if guest else principal(RoleCode.CUSTOMER)
    order = order_for(owner)
    orders = SimpleNamespace(get_order=AsyncMock(return_value=order))
    advances = SimpleNamespace(get_advance=AsyncMock(return_value=None))
    handler = GetAdvanceSummary(orders, advances)
    quote = await handler(actor=owner, order_id=order.id)
    assert quote.required_amount == Decimal("5.01")
    assert quote.verified_amount == Decimal("0.00")
    assert quote.remaining_amount == Decimal("10.01")
    assert (await handler(actor=principal(RoleCode.ADMIN), order_id=order.id)) == quote
    with pytest.raises(AdvanceNotFoundError):
        await handler(actor=principal(RoleCode.CASHIER), order_id=order.id)
    with pytest.raises(AdvanceNotFoundError):
        await handler(actor=principal(guest=guest), order_id=order.id)
    orders.get_order.return_value = order_for(owner, modality="LOCAL")
    with pytest.raises(AdvanceConflictError):
        await handler(actor=owner, order_id=order.id)


@pytest.mark.asyncio
async def test_only_admin_verifies_approved_pickup_or_delivery() -> None:
    customer = principal(RoleCode.CUSTOMER)
    admin = principal(RoleCode.ADMIN)
    order = order_for(customer, modality="DELIVERY")
    assert admin.user_id is not None
    payment = AdvancePayment(uuid4(), order.id, Decimal("5.01"), admin.user_id, datetime.now(UTC))
    orders = SimpleNamespace(get_order=AsyncMock(return_value=order))
    advances = SimpleNamespace(
        find_request=AsyncMock(return_value=None),
        get_advance=AsyncMock(return_value=None),
        record_verification=AsyncMock(return_value=payment),
    )
    handler = VerifyAdvance(orders, advances)
    with pytest.raises(AuthorizationError):
        await handler(actor=principal(RoleCode.CASHIER), order_id=order.id, request_key="a")
    result = await handler(actor=admin, order_id=order.id, request_key="a")
    assert result.required_amount == result.verified_amount == Decimal("5.01")
    assert result.remaining_amount == Decimal("5.00")
    advances.record_verification.assert_awaited_once()
    assert advances.record_verification.await_args.kwargs["amount"] == Decimal("5.01")
    assert advances.record_verification.await_args.kwargs["existing"] is None
    orders.get_order.return_value = order_for(customer, status="REQUESTED")
    with pytest.raises(AdvanceConflictError):
        await handler(actor=admin, order_id=order.id, request_key="b")
    orders.get_order.return_value = order_for(customer, status="REJECTED")
    with pytest.raises(AdvanceConflictError):
        await handler(actor=admin, order_id=order.id, request_key="c")
    orders.get_order.return_value = order_for(customer, modality="LOCAL")
    with pytest.raises(AdvanceConflictError):
        await handler(actor=admin, order_id=order.id, request_key="d")


@pytest.mark.asyncio
async def test_replay_and_existing_payment_do_not_create_another_advance() -> None:
    admin = principal(RoleCode.SUPER_ADMIN)
    order = order_for(principal(RoleCode.CUSTOMER))
    assert admin.user_id is not None
    payment = AdvancePayment(uuid4(), order.id, Decimal("5.01"), admin.user_id, datetime.now(UTC))
    orders = SimpleNamespace(get_order=AsyncMock(return_value=order))
    advances = SimpleNamespace(
        find_request=AsyncMock(return_value=order.id),
        get_advance=AsyncMock(return_value=payment),
        record_verification=AsyncMock(),
    )
    handler = VerifyAdvance(orders, advances)
    replay = await handler(actor=admin, order_id=order.id, request_key="same")
    assert replay.verified_amount == Decimal("5.01")
    advances.record_verification.assert_not_awaited()
    advances.find_request.return_value = None
    advances.record_verification.return_value = payment
    second_key = await handler(actor=admin, order_id=order.id, request_key="another")
    assert second_key == replay
    assert advances.record_verification.await_args.kwargs["existing"] == payment
    advances.get_advance.return_value = AdvancePayment(
        payment.id, order.id, Decimal("4.00"), admin.user_id, payment.recorded_at
    )
    with pytest.raises(AdvanceConflictError):
        await handler(actor=admin, order_id=order.id, request_key="invalid-history")
