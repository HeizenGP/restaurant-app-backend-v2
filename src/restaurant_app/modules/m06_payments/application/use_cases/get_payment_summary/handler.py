"""Query payment summary for its owner or authorized cashier."""

from decimal import Decimal
from uuid import UUID

from restaurant_app.modules.m01_access.public import Principal, RoleCode
from restaurant_app.modules.m06_payments.application.ports.collection_repository import (
    CollectionOrderReader,
    CollectionRepository,
)
from restaurant_app.modules.m06_payments.domain.entities import PaymentSummary
from restaurant_app.modules.m06_payments.domain.errors import PaymentNotFoundError


class GetPaymentSummary:
    """Return the full payment view for an order (advance + collections)."""

    def __init__(
        self,
        orders: CollectionOrderReader,
        payments: CollectionRepository,
    ) -> None:
        self._orders = orders
        self._payments = payments

    async def __call__(self, *, actor: Principal, order_id: UUID) -> PaymentSummary:
        order = await self._orders.get_order_for_collection(order_id)
        if order is None or not (
            actor.has_any_role(RoleCode.CASHIER)
            or (actor.user_id is not None and actor.user_id == order.customer_user_id)
            or (actor.user_id is None and actor.session_id == order.guest_session_id)
        ):
            raise PaymentNotFoundError("Order not found")

        all_payments = await self._payments.list_payments(order_id)
        paid = sum((payment.amount for payment in all_payments), Decimal("0.00"))
        return PaymentSummary(
            order_id=order_id,
            order_status=order.status,
            total_amount=order.total_amount,
            paid_amount=paid,
            balance=order.total_amount - paid,
            payments=tuple(all_payments),
        )
