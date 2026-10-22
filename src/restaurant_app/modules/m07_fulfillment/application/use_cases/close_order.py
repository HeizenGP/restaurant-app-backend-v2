"""Close an attended, kitchen-ready, fully paid order atomically."""

import hashlib
from decimal import Decimal
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m04_orders.public import FulfillmentOrderReader, OrderForFulfillment
from restaurant_app.modules.m05_kitchen.public import KitchenProgressReader
from restaurant_app.modules.m06_payments.public import PaymentBalanceReader
from restaurant_app.modules.m07_fulfillment.application.ports.fulfillment_repository import (
    FulfillmentRepository,
)
from restaurant_app.modules.m07_fulfillment.domain.entities import FulfillmentKind
from restaurant_app.modules.m07_fulfillment.domain.errors import (
    FulfillmentConflictError,
    FulfillmentNotFoundError,
    InvalidFulfillmentRequestError,
)

KIND_BY_MODALITY = {
    "LOCAL": FulfillmentKind.SERVED,
    "PICKUP": FulfillmentKind.PICKED_UP,
    "DELIVERY": FulfillmentKind.DELIVERED,
}


class CloseOrder:
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
        self._authorize = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(
        self, *, actor: Principal, order_id: UUID, request_key: str
    ) -> OrderForFulfillment:
        self._authorize(actor)
        assert actor.user_id is not None
        if not 1 <= len(request_key) <= 128 or not request_key.strip():
            raise InvalidFulfillmentRequestError("Idempotency-Key must contain 1 to 128 characters")
        fingerprint = hashlib.sha256(str(order_id).encode()).hexdigest()
        replay_order_id = await self._fulfillments.find_request(
            operation="CLOSE_ORDER",
            actor_id=actor.user_id,
            key=request_key,
            fingerprint=fingerprint,
        )
        if replay_order_id is not None:
            replay = await self._orders.get_order(replay_order_id)
            if replay is None or replay.status != "CLOSED":
                raise FulfillmentConflictError("Stored closure result is unavailable")
            return replay

        order = await self._orders.get_order(order_id, lock=True)
        if order is None:
            raise FulfillmentNotFoundError("Order not found")
        if order.status == "CLOSED":
            return order
        if order.status != "CONFIRMED":
            raise FulfillmentConflictError("Only confirmed orders can be closed")
        progress = await self._kitchen.get_progress(order_id)
        if progress is None or progress.status != "READY":
            raise FulfillmentConflictError("Kitchen ticket must be READY before closure")
        fulfillment = await self._fulfillments.get(order_id)
        if fulfillment is None or fulfillment.kind is not KIND_BY_MODALITY[order.modality]:
            raise FulfillmentConflictError("Required service or delivery has not been recorded")
        balance = await self._payments.get_balance(order_id, total_amount=order.total_amount)
        if balance != Decimal("0.00"):
            raise FulfillmentConflictError(f"Outstanding balance: S/ {balance:.2f}")
        closed = await self._orders.close_order(order_id, actor_id=actor.user_id)
        await self._fulfillments.record_close(
            actor_id=actor.user_id,
            order_id=order_id,
            key=request_key,
            fingerprint=fingerprint,
        )
        return closed
