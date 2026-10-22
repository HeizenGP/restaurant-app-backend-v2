"""Approve or reject only a pending APP request under its modality policy."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m04_orders.application.ports.order_repository import (
    OrderRepository,
    TableOccupancy,
)
from restaurant_app.modules.m04_orders.domain.entities import Channel, Modality, Order, OrderStatus
from restaurant_app.modules.m04_orders.domain.errors import OrderConflictError, OrderNotFoundError


class DecideOrder:
    def __init__(self, orders: OrderRepository, tables: TableOccupancy) -> None:
        self._orders = orders
        self._tables = tables

    async def __call__(
        self, *, actor: Principal, order_id: UUID, approved: bool, table_verified: bool
    ) -> Order:
        candidate = await self._orders.get_order(order_id)
        if candidate is None:
            raise OrderNotFoundError
        if candidate.modality is Modality.LOCAL:
            AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)(actor)
        else:
            AuthorizeRoles(RoleCode.ADMIN)(actor)
        if candidate.channel is not Channel.APP:
            raise OrderConflictError("Only APP requests use this decision workflow")
        if approved and candidate.modality is Modality.LOCAL and not table_verified:
            raise OrderConflictError("Local APP approval requires in-person table verification")
        target = OrderStatus.APPROVED if approved else OrderStatus.REJECTED
        if candidate.status == target:
            return candidate
        if candidate.status != OrderStatus.REQUESTED:
            raise OrderConflictError("Request has already been decided")
        table = None
        if approved and candidate.modality is Modality.LOCAL:
            assert candidate.table_id is not None
            # Lock table before order: CreateOrder locks table before reading owner orders.
            table = await self._tables.lock_table(candidate.table_id)
            if table is None:
                raise OrderConflictError("The selected table is unavailable")
        order = await self._orders.get_order(order_id, lock=True)
        if order is None:
            raise OrderNotFoundError
        if order.status == target:
            return order
        if order.status != OrderStatus.REQUESTED:
            raise OrderConflictError("Request has already been decided")
        assert actor.user_id is not None
        if table is not None:
            assert order.table_id is not None
            if table.is_occupied:
                if table.occupancy_started_at is None:
                    raise OrderConflictError("The selected table has no current occupancy")
                if await self._orders.has_conflicting_verified_table_owner(
                    table_id=order.table_id,
                    occupied_since=table.occupancy_started_at,
                    customer_user_id=order.customer_user_id,
                    guest_session_id=order.guest_session_id,
                ):
                    raise OrderConflictError("The table belongs to another customer")
            else:
                table = await self._tables.occupy(order.table_id, actor_id=actor.user_id)
            if table.occupancy_started_at is None:
                raise OrderConflictError("The selected table has no current occupancy")
        return await self._orders.decide_order(
            order_id,
            approved=approved,
            actor_id=actor.user_id,
            table_verified=approved and order.modality is Modality.LOCAL,
        )
