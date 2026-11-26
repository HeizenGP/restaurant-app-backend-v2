"""Project consolidated payments consistently onto each order."""

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderItemModel, OrderModel
from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel, TablePaymentAllocation

ZERO = Decimal("0.00")


async def allocate_order_payments(
    session: AsyncSession, orders: list[OrderModel], payments: Iterable[PaymentModel],
) -> tuple[dict[UUID, Decimal], dict[UUID, list[tuple[PaymentModel, Decimal]]]]:
    """Reserve explicit allocations before distributing legacy payments oldest-first."""
    paid: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    projected: dict[UUID, list[tuple[PaymentModel, Decimal]]] = defaultdict(list)
    consolidated = []
    for payment in payments:
        if payment.order_id is not None:
            paid[payment.order_id] += payment.amount
        else:
            consolidated.append(payment)

    requested = {
        payment.allocation_request_id for payment in consolidated if payment.allocation_request_id
    }
    by_request: dict[UUID, dict[UUID, Decimal]] = defaultdict(dict)
    if requested:
        rows = await session.execute(
            select(
                TablePaymentAllocation.request_id, OrderItemModel.order_id,
                func.sum(TablePaymentAllocation.quantity * OrderItemModel.unit_price_snapshot),
            )
            .join(OrderItemModel, OrderItemModel.id == TablePaymentAllocation.item_id)
            .where(TablePaymentAllocation.request_id.in_(requested))
            .group_by(TablePaymentAllocation.request_id, OrderItemModel.order_id)
        )
        for request, order, amount in rows:
            by_request[request][order] = amount

    for targeted in (True, False):
        for payment in consolidated:
            if (payment.allocation_request_id is not None) != targeted:
                continue
            remaining = payment.amount
            for order in orders:
                if payment.allocation_request_id is not None:
                    entitlement = by_request[payment.allocation_request_id]
                    capacity = entitlement.get(order.id, ZERO)
                else:
                    capacity = max(order.total_amount - paid[order.id], ZERO)
                amount = min(capacity, remaining)
                if amount > 0:
                    paid[order.id] += amount
                    projected[order.id].append((payment, amount))
                    if payment.allocation_request_id is not None:
                        entitlement[order.id] -= amount
                    remaining -= amount
                if remaining <= 0:
                    break
    return paid, projected
