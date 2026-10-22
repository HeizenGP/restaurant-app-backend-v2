"""Record an approved service, pickup, or commercial delivery exactly once."""

import hashlib
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m04_orders.public import FulfillmentOrderReader
from restaurant_app.modules.m05_kitchen.public import KitchenProgressReader
from restaurant_app.modules.m07_fulfillment.application.ports.fulfillment_repository import (
    FulfillmentRepository,
)
from restaurant_app.modules.m07_fulfillment.domain.entities import Fulfillment, FulfillmentKind
from restaurant_app.modules.m07_fulfillment.domain.errors import (
    FulfillmentConflictError,
    FulfillmentNotFoundError,
    InvalidFulfillmentRequestError,
)


class RecordFulfillment:
    """Use one order-row lock and one UoW for audit plus idempotency."""

    def __init__(
        self,
        orders: FulfillmentOrderReader,
        kitchen: KitchenProgressReader,
        fulfillments: FulfillmentRepository,
        *,
        kind: FulfillmentKind,
        modality: str,
        role: RoleCode,
    ) -> None:
        self._orders = orders
        self._kitchen = kitchen
        self._fulfillments = fulfillments
        self._kind = kind
        self._modality = modality
        self._authorize = AuthorizeRoles(role)

    async def __call__(self, *, actor: Principal, order_id: UUID, request_key: str) -> Fulfillment:
        self._authorize(actor)
        assert actor.user_id is not None
        if not 1 <= len(request_key) <= 128 or not request_key.strip():
            raise InvalidFulfillmentRequestError("Idempotency-Key must contain 1 to 128 characters")
        fingerprint = hashlib.sha256(f"{order_id}:{self._kind.value}".encode()).hexdigest()
        replay_order_id = await self._fulfillments.find_request(
            operation="RECORD_FULFILLMENT",
            actor_id=actor.user_id,
            key=request_key,
            fingerprint=fingerprint,
        )
        if replay_order_id is not None:
            fulfillment = await self._fulfillments.get(replay_order_id)
            if fulfillment is None or fulfillment.kind is not self._kind:
                raise FulfillmentConflictError("Stored fulfillment result is unavailable")
            return fulfillment

        order = await self._orders.get_order(order_id, lock=True)
        if order is None:
            raise FulfillmentNotFoundError("Order not found")
        if order.modality != self._modality:
            raise FulfillmentConflictError("Fulfillment kind does not match order modality")
        existing = await self._fulfillments.get(order_id)
        if existing is not None:
            if existing.kind is self._kind:
                return existing
            raise FulfillmentConflictError("Order already has another fulfillment kind")
        if order.status != "CONFIRMED":
            raise FulfillmentConflictError("Only confirmed orders can be fulfilled")
        progress = await self._kitchen.get_progress(order_id)
        if progress is None or progress.status != "READY":
            raise FulfillmentConflictError("Kitchen ticket must be READY before fulfillment")
        return await self._fulfillments.record(
            actor_id=actor.user_id,
            order_id=order_id,
            kind=self._kind,
            key=request_key,
            fingerprint=fingerprint,
        )
