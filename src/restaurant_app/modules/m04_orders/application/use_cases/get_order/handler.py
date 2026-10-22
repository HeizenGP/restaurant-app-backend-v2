"""Read a request for its owner or authorized staff without exposing other users."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import Principal, RoleCode
from restaurant_app.modules.m04_orders.application.ports.order_repository import OrderRepository
from restaurant_app.modules.m04_orders.domain.entities import Modality, Order
from restaurant_app.modules.m04_orders.domain.errors import OrderNotFoundError


def can_read(actor: Principal, order: Order) -> bool:
    return bool(
        (actor.user_id is not None and actor.user_id == order.customer_user_id)
        or (actor.user_id is None and actor.session_id == order.guest_session_id)
        or actor.has_any_role(RoleCode.ADMIN)
        or (order.modality is Modality.LOCAL and actor.has_any_role(RoleCode.WAITER))
    )


class GetOrder:
    def __init__(self, orders: OrderRepository) -> None:
        self._orders = orders

    async def __call__(self, *, actor: Principal, order_id: UUID) -> Order:
        order = await self._orders.get_order(order_id)
        if order is None or not can_read(actor, order):
            raise OrderNotFoundError
        return order


class ListOrders:
    def __init__(self, orders: OrderRepository) -> None:
        self._orders = orders

    async def __call__(self, *, actor: Principal) -> list[Order]:
        orders = await self._orders.list_orders(
            customer_user_id=actor.user_id,
            guest_session_id=actor.session_id if actor.user_id is None else None,
            staff_local=actor.has_any_role(RoleCode.WAITER),
            staff_all=actor.has_any_role(RoleCode.ADMIN),
        )
        return [order for order in orders if can_read(actor, order)]
