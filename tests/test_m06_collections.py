"""08.08 cashier rules independent of HTTP and PostgreSQL adapters."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError
from restaurant_app.modules.m04_orders.public import OrderForCollection
from restaurant_app.modules.m06_payments.application.use_cases.get_payment_summary import (
    GetPaymentSummary,
)
from restaurant_app.modules.m06_payments.application.use_cases.record_collection import (
    RecordCollection,
)
from restaurant_app.modules.m06_payments.domain.entities import AdvancePayment, CollectionPayment
from restaurant_app.modules.m06_payments.domain.errors import (
    InvalidPaymentRequestError,
    PaymentConflictError,
    PaymentNotFoundError,
)


def principal(*roles: RoleCode, guest: bool = False) -> Principal:
    return Principal(
        user_id=None if guest else uuid4(),
        session_id=uuid4(),
        roles=frozenset(roles),
        kind=SessionKind.GUEST if guest else SessionKind.USER,
    )


def order(owner: Principal, *, status: str = "CONFIRMED") -> OrderForCollection:
    return OrderForCollection(
        id=uuid4(),
        modality="LOCAL",
        status=status,
        total_amount=Decimal("10.01"),
        customer_user_id=owner.user_id,
        guest_session_id=owner.session_id if owner.user_id is None else None,
    )


def ports(
    record: OrderForCollection, paid: Decimal = Decimal("0.00")
) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    orders = SimpleNamespace(get_order_for_collection=AsyncMock(return_value=record))
    payments = SimpleNamespace(
        find_request=AsyncMock(return_value=None),
        sum_paid=AsyncMock(return_value=paid),
        record_collection=AsyncMock(),
        list_payments=AsyncMock(return_value=[]),
    )
    handovers = SimpleNamespace(has_handover=AsyncMock(return_value=False))
    return orders, payments, handovers


@pytest.mark.asyncio
async def test_cashier_records_partial_and_final_amount_without_overpayment() -> None:
    owner = principal(RoleCode.CUSTOMER)
    cashier = principal(RoleCode.CASHIER)
    record = order(owner)
    orders, payments, handovers = ports(record, Decimal("5.01"))
    handler = RecordCollection(orders, payments, handovers)
    result = await handler(
        actor=cashier,
        order_id=record.id,
        amount=Decimal("5.000"),
        method_code=" EFECTIVO ",
        request_key="collection-1",
    )
    assert result.order_id == record.id
    assert payments.record_collection.await_args.kwargs["amount"] == Decimal("5.00")
    assert payments.record_collection.await_args.kwargs["method_code"] == "EFECTIVO"
    assert orders.get_order_for_collection.await_args_list[0].kwargs == {"lock": True}
    payments.sum_paid.return_value = Decimal("5.02")
    with pytest.raises(PaymentConflictError):
        await handler(
            actor=cashier,
            order_id=record.id,
            amount=Decimal("5.00"),
            method_code="EFECTIVO",
            request_key="collection-2",
        )
    payments.sum_paid.return_value = Decimal("10.01")
    with pytest.raises(PaymentConflictError):
        await handler(
            actor=cashier,
            order_id=record.id,
            amount=Decimal("0.01"),
            method_code="EFECTIVO",
            request_key="collection-3",
        )


@pytest.mark.asyncio
async def test_collection_guards_role_state_and_money_before_write() -> None:
    owner = principal(RoleCode.CUSTOMER)
    cashier = principal(RoleCode.CASHIER)
    record = order(owner)
    orders, payments, handovers = ports(record)
    handler = RecordCollection(orders, payments, handovers)
    with pytest.raises(AuthorizationError):
        await handler(
            actor=principal(RoleCode.ADMIN),
            order_id=record.id,
            amount=Decimal("1.00"),
            method_code="EFECTIVO",
            request_key="role",
        )
    for invalid in (Decimal("0"), Decimal("-1"), Decimal("0.001"), Decimal("NaN")):
        with pytest.raises(InvalidPaymentRequestError):
            await handler(
                actor=cashier,
                order_id=record.id,
                amount=invalid,
                method_code="EFECTIVO",
                request_key="money",
            )
    with pytest.raises(InvalidPaymentRequestError):
        await handler(
            actor=cashier,
            order_id=record.id,
            amount=Decimal("1.00"),
            method_code=" ",
            request_key="method",
        )
    with pytest.raises(InvalidPaymentRequestError):
        await handler(
            actor=cashier,
            order_id=record.id,
            amount=Decimal("1.00"),
            method_code="EFECTIVO",
            request_key=" ",
        )
    orders.get_order_for_collection.return_value = order(owner, status="REQUESTED")
    with pytest.raises(PaymentConflictError):
        await handler(
            actor=cashier,
            order_id=record.id,
            amount=Decimal("1.00"),
            method_code="EFECTIVO",
            request_key="state",
        )
    payments.record_collection.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_does_not_record_again_and_payment_state_is_derived() -> None:
    owner = principal(RoleCode.CUSTOMER)
    cashier = principal(RoleCode.CASHIER)
    record = order(owner)
    orders, payments, handovers = ports(record)
    payments.find_request.return_value = record.id
    payment = CollectionPayment(
        uuid4(), record.id, Decimal("10.01"), "EFECTIVO", cashier.user_id, datetime.now(UTC)
    )
    payments.list_payments.return_value = [payment]
    summary = await RecordCollection(orders, payments, handovers)(
        actor=cashier,
        order_id=record.id,
        amount=Decimal("10.01"),
        method_code="EFECTIVO",
        request_key="replay",
    )
    assert summary.balance == Decimal("0.00")
    assert summary.payment_status == "PAID"
    payments.record_collection.assert_not_awaited()
    payments.list_payments.return_value = []
    summary = await GetPaymentSummary(orders, payments)(actor=owner, order_id=record.id)
    assert summary.payment_status == "UNPAID"
    advance = AdvancePayment(
        uuid4(), record.id, Decimal("5.01"), cashier.user_id, datetime.now(UTC)
    )
    payments.list_payments.return_value = [advance]
    summary = await GetPaymentSummary(orders, payments)(actor=owner, order_id=record.id)
    assert summary.payment_status == "PARTIAL"
    with pytest.raises(PaymentNotFoundError):
        await GetPaymentSummary(orders, payments)(
            actor=principal(RoleCode.CUSTOMER), order_id=record.id
        )
    assert (await GetPaymentSummary(orders, payments)(actor=cashier, order_id=record.id)) == summary


@pytest.mark.asyncio
@pytest.mark.parametrize(("modality", "kind"), [("PICKUP", "PICKED_UP"), ("DELIVERY", "DELIVERED")])
async def test_remote_final_collection_requires_handover_and_exact_balance(
    modality: str, kind: str
) -> None:
    owner = principal(RoleCode.CUSTOMER)
    cashier = principal(RoleCode.CASHIER)
    record = replace(order(owner), modality=modality)
    orders, payments, handovers = ports(record, Decimal("5.01"))
    handler = RecordCollection(orders, payments, handovers)
    with pytest.raises(PaymentConflictError):
        await handler(
            actor=cashier,
            order_id=record.id,
            amount=Decimal("5.00"),
            method_code="EFECTIVO",
            request_key="before-handover",
        )
    handovers.has_handover.assert_awaited_with(record.id, kind=kind)
    handovers.has_handover.return_value = True
    with pytest.raises(PaymentConflictError):
        await handler(
            actor=cashier,
            order_id=record.id,
            amount=Decimal("2.00"),
            method_code="EFECTIVO",
            request_key="partial",
        )
    await handler(
        actor=cashier,
        order_id=record.id,
        amount=Decimal("5.00"),
        method_code="EFECTIVO",
        request_key="final",
    )
    assert payments.record_collection.await_args.kwargs["amount"] == Decimal("5.00")
