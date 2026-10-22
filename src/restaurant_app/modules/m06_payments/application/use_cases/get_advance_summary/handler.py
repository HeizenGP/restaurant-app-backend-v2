"""Quote the mandatory advance for its owner or an administrator."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import Principal, RoleCode
from restaurant_app.modules.m06_payments.application.ports.advance_repository import (
    AdvanceOrderReader,
    AdvanceRepository,
)
from restaurant_app.modules.m06_payments.application.summary import advance_summary
from restaurant_app.modules.m06_payments.domain.entities import AdvanceSummary
from restaurant_app.modules.m06_payments.domain.errors import (
    AdvanceConflictError,
    AdvanceNotFoundError,
)


class GetAdvanceSummary:
    def __init__(self, orders: AdvanceOrderReader, advances: AdvanceRepository) -> None:
        self._orders = orders
        self._advances = advances

    async def __call__(self, *, actor: Principal, order_id: UUID) -> AdvanceSummary:
        order = await self._orders.get_order(order_id)
        if order is None or not (
            actor.has_any_role(RoleCode.ADMIN)
            or (actor.user_id is not None and actor.user_id == order.customer_user_id)
            or (actor.user_id is None and actor.session_id == order.guest_session_id)
        ):
            raise AdvanceNotFoundError
        if order.modality not in {"PICKUP", "DELIVERY"}:
            raise AdvanceConflictError("Local orders do not require an advance")
        payment = await self._advances.get_advance(order_id)
        return advance_summary(order, payment)
