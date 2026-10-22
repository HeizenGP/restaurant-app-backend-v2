"""Record a cashier collection against a confirmed order."""

import hashlib
from decimal import Decimal
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m06_payments.application.ports.collection_repository import (
    CollectionHandoverReader,
    CollectionOrderReader,
    CollectionRepository,
)
from restaurant_app.modules.m06_payments.domain.entities import PaymentSummary
from restaurant_app.modules.m06_payments.domain.payment_methods import validate_collection_method
from restaurant_app.modules.m06_payments.domain.errors import (
    InvalidPaymentRequestError,
    PaymentConflictError,
    PaymentNotFoundError,
)


class RecordCollection:
    """Cashier registers a partial/full collection; prevents overpayment."""

    def __init__(
        self,
        orders: CollectionOrderReader,
        payments: CollectionRepository,
        handovers: CollectionHandoverReader,
    ) -> None:
        self._orders = orders
        self._payments = payments
        self._handovers = handovers
        self._authorize = AuthorizeRoles(RoleCode.CASHIER)

    async def __call__(
        self,
        *,
        actor: Principal,
        order_id: UUID,
        amount: Decimal,
        method_code: str,
        request_key: str,
        reference_code: str | None = None,
    ) -> PaymentSummary:
        self._authorize(actor)
        assert actor.user_id is not None

        if not 1 <= len(request_key) <= 128 or not request_key.strip():
            raise InvalidPaymentRequestError("Idempotency-Key must contain 1 to 128 characters")
        method, reference = validate_collection_method(method_code, reference_code)
        if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
            raise InvalidPaymentRequestError("amount must be a positive PEN amount")
        cents = amount.quantize(Decimal("0.01"))
        if amount != cents:
            raise InvalidPaymentRequestError("amount must have at most two decimal places")
        fingerprint = hashlib.sha256(
            f"{order_id}:{cents:.2f}:{method}:{reference or ''}".encode()
        ).hexdigest()

        replay_order_id = await self._payments.find_request(
            actor_id=actor.user_id, key=request_key, fingerprint=fingerprint
        )
        if replay_order_id is not None:
            return await self._build_summary(replay_order_id)

        order = await self._orders.get_order_for_collection(order_id, lock=True)
        if order is None:
            raise PaymentNotFoundError("Order not found")
        if order.status != "CONFIRMED":
            raise PaymentConflictError("Collections require a confirmed, open order")

        already_paid = await self._payments.sum_paid(order_id)
        remaining = order.total_amount - already_paid
        if remaining <= 0:
            raise PaymentConflictError("Order is already fully paid")
        if order.modality in {"PICKUP", "DELIVERY"}:
            handover_kind = "PICKED_UP" if order.modality == "PICKUP" else "DELIVERED"
            if not await self._handovers.has_handover(order_id, kind=handover_kind):
                raise PaymentConflictError(
                    "Pickup or delivery must be recorded before final payment"
                )
            if cents != remaining:
                raise PaymentConflictError("Pickup or delivery requires the full remaining balance")
        if cents > remaining:
            raise PaymentConflictError(f"Amount {cents} exceeds remaining balance {remaining}")

        await self._payments.record_collection(
            actor_id=actor.user_id,
            request_key=request_key,
            fingerprint=fingerprint,
            order_id=order_id,
            amount=cents,
            method_code=method,
            reference_code=reference,
        )
        return await self._build_summary(order_id)

    async def _build_summary(self, order_id: UUID) -> PaymentSummary:
        order = await self._orders.get_order_for_collection(order_id)
        if order is None:
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
