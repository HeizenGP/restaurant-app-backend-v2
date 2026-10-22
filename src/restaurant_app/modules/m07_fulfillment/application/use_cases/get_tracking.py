"""Compose M04/M05/M06/M07 progress without storing a duplicate global status."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import Principal
from restaurant_app.modules.m04_orders.public import FulfillmentOrderReader
from restaurant_app.modules.m05_kitchen.public import KitchenProgressReader
from restaurant_app.modules.m06_payments.public import PaymentBalanceReader
from restaurant_app.modules.m07_fulfillment.application.ports.fulfillment_repository import (
    FulfillmentRepository,
)
from restaurant_app.modules.m07_fulfillment.domain.entities import OrderTracking
from restaurant_app.modules.m07_fulfillment.domain.errors import FulfillmentNotFoundError


class GetTracking:
    def __init__(
        self,
        orders: FulfillmentOrderReader,
        kitchen: KitchenProgressReader,
        payments: PaymentBalanceReader,
        fulfillments: FulfillmentRepository,
    ) -> None:
        self._orders = orders
        self._kitchen = kitchen
        self._payments = payments
        self._fulfillments = fulfillments

    async def __call__(self, *, actor: Principal, order_id: UUID) -> OrderTracking:
        order = await self._orders.get_visible_order(actor, order_id)
        if order is None:
            raise FulfillmentNotFoundError("Order not found")
        progress = await self._kitchen.get_progress(order_id)
        fulfillment = await self._fulfillments.get(order_id)
        balance = await self._payments.get_balance(order_id, total_amount=order.total_amount)
        paid = order.total_amount - balance
        if order.status == "CLOSED":
            stage = "CLOSED"
        elif order.status in {"REJECTED", "CANCELLED"}:
            stage = order.status
        elif fulfillment is not None:
            stage = fulfillment.kind.value
        elif progress is not None:
            stage = progress.status
        else:
            stage = order.status
        return OrderTracking(
            order_id=order_id,
            modality=order.modality,
            order_status=order.status,
            stage=stage,
            kitchen_status=None if progress is None else progress.status,
            fulfillment_kind=None if fulfillment is None else fulfillment.kind.value,
            total_amount=order.total_amount,
            paid_amount=paid,
            balance=balance,
            payment_status=("UNPAID" if paid == 0 else "PAID" if balance == 0 else "PARTIAL"),
            created_at=order.created_at,
            kitchen_started_at=None if progress is None else progress.started_at,
            kitchen_ready_at=None if progress is None else progress.ready_at,
            fulfilled_at=None if fulfillment is None else fulfillment.recorded_at,
            closed_at=order.closed_at,
        )
