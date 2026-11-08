"""PostgreSQL persistence for one verified advance per order."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel
from restaurant_app.modules.m06_payments.domain.entities import AdvancePayment
from restaurant_app.modules.m06_payments.domain.errors import AdvanceConflictError
from restaurant_app.shared.adapters.outbound.models import IdempotencyRequestModel


class SqlAlchemyAdvanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _advance(model: PaymentModel) -> AdvancePayment:
        assert model.order_id is not None
        return AdvancePayment(
            id=model.id,
            order_id=model.order_id,
            amount=model.amount,
            recorded_by_user_id=model.recorded_by_user_id,
            recorded_at=model.recorded_at,
        )

    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> UUID | None:
        # Serialize same actor/key before looking for an already completed operation.
        lock_name = f"VERIFY_ADVANCE:{actor_id}:{key}"
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_name, 0)))
        )
        request = (
            await self._session.scalars(
                select(IdempotencyRequestModel).where(
                    IdempotencyRequestModel.actor_user_id == actor_id,
                    IdempotencyRequestModel.operation == "VERIFY_ADVANCE",
                    IdempotencyRequestModel.request_key == key,
                )
            )
        ).one_or_none()
        if request is None:
            return None
        if request.request_hash != fingerprint or request.result_order_id is None:
            raise AdvanceConflictError("Idempotency-Key was already used for another request")
        return request.result_order_id

    async def get_advance(self, order_id: UUID) -> AdvancePayment | None:
        model = (
            await self._session.scalars(
                select(PaymentModel).where(
                    PaymentModel.order_id == order_id,
                    PaymentModel.kind == "ADVANCE",
                )
            )
        ).one_or_none()
        return None if model is None else self._advance(model)

    async def record_verification(
        self,
        *,
        actor_id: UUID,
        request_key: str,
        fingerprint: str,
        order_id: UUID,
        amount: Decimal,
        existing: AdvancePayment | None,
    ) -> AdvancePayment:
        request = IdempotencyRequestModel(
            actor_user_id=actor_id,
            operation="VERIFY_ADVANCE",
            request_key=request_key,
            request_hash=fingerprint,
            expires_at=func.clock_timestamp() + timedelta(hours=24),
        )
        self._session.add(request)
        await self._session.flush()
        if existing is None:
            payment = PaymentModel(
                order_id=order_id,
                kind="ADVANCE",
                amount=amount,
                method_code=None,
                recorded_by_user_id=actor_id,
                operation_request_id=request.id,
            )
            self._session.add(payment)
            await self._session.flush()
            await self._session.refresh(payment)
            result = self._advance(payment)
        else:
            result = existing
        request.result_order_id = order_id
        request.completed_at = func.clock_timestamp()
        await self._session.flush()
        return result
