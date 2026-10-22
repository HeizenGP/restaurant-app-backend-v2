"""Register and confirm a waiter order without a second approval."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m04_orders.application.use_cases.confirm_order import ConfirmOrder
from restaurant_app.modules.m04_orders.application.use_cases.create_order import CreateOrder
from restaurant_app.modules.m04_orders.domain.entities import (
    Channel,
    Modality,
    Order,
    RequestedItem,
)


class CreateWaiterOrder:
    """Both actions share the request's one SQLAlchemy session and commit."""

    def __init__(self, create: CreateOrder, confirm: ConfirmOrder) -> None:
        self._create = create
        self._confirm = confirm

    async def __call__(
        self,
        *,
        actor: Principal,
        request_key: str,
        table_id: UUID,
        items: tuple[RequestedItem, ...],
    ) -> Order:
        AuthorizeRoles(RoleCode.WAITER)(actor)
        order = await self._create(
            actor=actor,
            request_key=request_key,
            modality=Modality.LOCAL,
            channel=Channel.WAITER,
            items=items,
            table_id=table_id,
            delivery_address=None,
            contact_name=None,
            contact_phone=None,
        )
        return await self._confirm(actor=actor, order_id=order.id, request_key=request_key)
