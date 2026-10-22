"""Approve or reject only a pending APP request under its modality policy."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m04_orders.application.ports.order_repository import OrderRepository
from restaurant_app.modules.m04_orders.domain.entities import Channel, Modality, Order, OrderStatus
from restaurant_app.modules.m04_orders.domain.errors import OrderConflictError, OrderNotFoundError


class DecideOrder:
    def __init__(self, orders: OrderRepository) -> None:
        self._orders = orders

    async def __call__(
        self, *, actor: Principal, order_id: UUID, approved: bool, table_verified: bool
    ) -> Order:
        order = await self._orders.get_order(order_id, lock=True)
        if order is None:
            raise OrderNotFoundError
        if order.modality is Modality.LOCAL:
            AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)(actor)
        else:
            AuthorizeRoles(RoleCode.ADMIN)(actor)
        if order.channel is not Channel.APP:
            raise OrderConflictError("Only APP requests use this decision workflow")
        if approved and order.modality is Modality.LOCAL and not table_verified:
            raise OrderConflictError("Local APP approval requires in-person table verification")
        target = OrderStatus.APPROVED if approved else OrderStatus.REJECTED
        if order.status == target:
            return order
        if order.status != OrderStatus.REQUESTED:
            raise OrderConflictError("Request has already been decided")
        assert actor.user_id is not None
        return await self._orders.decide_order(
            order_id,
            approved=approved,
            actor_id=actor.user_id,
            table_verified=approved and order.modality is Modality.LOCAL,
        )
