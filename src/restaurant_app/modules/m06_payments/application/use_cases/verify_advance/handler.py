"""Record exactly one manually verified simulated advance."""

import hashlib
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m06_payments.application.ports.advance_repository import (
    AdvanceOrderReader,
    AdvanceRepository,
)
from restaurant_app.modules.m06_payments.application.summary import advance_summary
from restaurant_app.modules.m06_payments.domain.entities import AdvanceSummary, required_advance
from restaurant_app.modules.m06_payments.domain.errors import (
    AdvanceConflictError,
    AdvanceNotFoundError,
    InvalidAdvanceRequestError,
)


class VerifyAdvance:
    def __init__(self, orders: AdvanceOrderReader, advances: AdvanceRepository) -> None:
        self._orders = orders
        self._advances = advances
        self._authorize = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(
        self, *, actor: Principal, order_id: UUID, request_key: str
    ) -> AdvanceSummary:
        self._authorize(actor)
        assert actor.user_id is not None
        if not 1 <= len(request_key) <= 128 or not request_key.strip():
            raise InvalidAdvanceRequestError("Idempotency-Key must contain 1 to 128 characters")
        fingerprint = hashlib.sha256(str(order_id).encode()).hexdigest()
        replay_order_id = await self._advances.find_request(
            actor_id=actor.user_id, key=request_key, fingerprint=fingerprint
        )
        if replay_order_id is not None:
            order = await self._orders.get_order(replay_order_id)
            payment = await self._advances.get_advance(replay_order_id)
            if order is None or payment is None:
                raise AdvanceConflictError("Stored verification result is unavailable")
            return advance_summary(order, payment)
        order = await self._orders.get_order(order_id, lock=True)
        if order is None:
            raise AdvanceNotFoundError
        if order.modality not in {"PICKUP", "DELIVERY"}:
            raise AdvanceConflictError("Local orders do not require an advance")
        if order.status != "APPROVED":
            raise AdvanceConflictError("Only approved requests can receive an advance")
        required = required_advance(order.total_amount)
        existing = await self._advances.get_advance(order_id)
        if existing is not None and existing.amount != required:
            raise AdvanceConflictError("Recorded advance does not match the required amount")
        payment = await self._advances.record_verification(
            actor_id=actor.user_id,
            request_key=request_key,
            fingerprint=fingerprint,
            order_id=order_id,
            amount=required,
            existing=existing,
        )
        return advance_summary(order, payment)
