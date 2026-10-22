"""M07 PostgreSQL adapter for fulfillment and idempotent closure requests."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m07_fulfillment.adapters.outbound.models import FulfillmentModel
from restaurant_app.modules.m07_fulfillment.domain.entities import Fulfillment, FulfillmentKind
from restaurant_app.modules.m07_fulfillment.domain.errors import FulfillmentConflictError
from restaurant_app.shared.adapters.outbound.models import IdempotencyRequestModel


class SqlAlchemyFulfillmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _snapshot(model: FulfillmentModel) -> Fulfillment:
        return Fulfillment(
            id=model.id,
            order_id=model.order_id,
            kind=FulfillmentKind(model.kind),
            recorded_by_user_id=model.recorded_by_user_id,
            recorded_at=model.recorded_at,
        )

    async def find_request(
        self, *, operation: str, actor_id: UUID, key: str, fingerprint: str
    ) -> UUID | None:
        lock_name = f"{operation}:{actor_id}:{key}"
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_name, 0)))
        )
        request = (
            await self._session.scalars(
                select(IdempotencyRequestModel).where(
                    IdempotencyRequestModel.actor_user_id == actor_id,
                    IdempotencyRequestModel.operation == operation,
                    IdempotencyRequestModel.request_key == key,
                )
            )
        ).one_or_none()
        if request is None:
            return None
        if (
            request.request_hash != fingerprint
            or request.result_order_id is None
            or request.completed_at is None
        ):
            raise FulfillmentConflictError("Idempotency-Key was already used for another request")
        return request.result_order_id

    async def get(self, order_id: UUID) -> Fulfillment | None:
        model = (
            await self._session.scalars(
                select(FulfillmentModel).where(FulfillmentModel.order_id == order_id)
            )
        ).one_or_none()
        return None if model is None else self._snapshot(model)

    @staticmethod
    def _request(
        *, operation: str, actor_id: UUID, order_id: UUID, key: str, fingerprint: str
    ) -> IdempotencyRequestModel:
        return IdempotencyRequestModel(
            actor_user_id=actor_id,
            operation=operation,
            request_key=key,
            request_hash=fingerprint,
            result_order_id=order_id,
            completed_at=func.clock_timestamp(),
            expires_at=func.clock_timestamp() + timedelta(hours=24),
        )

    async def record(
        self,
        *,
        actor_id: UUID,
        order_id: UUID,
        kind: FulfillmentKind,
        key: str,
        fingerprint: str,
    ) -> Fulfillment:
        self._session.add(
            self._request(
                operation="RECORD_FULFILLMENT",
                actor_id=actor_id,
                order_id=order_id,
                key=key,
                fingerprint=fingerprint,
            )
        )
        model = FulfillmentModel(order_id=order_id, kind=kind.value, recorded_by_user_id=actor_id)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise FulfillmentConflictError("Order fulfillment already exists") from error
        await self._session.refresh(model)
        return self._snapshot(model)

    async def record_close(
        self, *, actor_id: UUID, order_id: UUID, key: str, fingerprint: str
    ) -> None:
        self._session.add(
            self._request(
                operation="CLOSE_ORDER",
                actor_id=actor_id,
                order_id=order_id,
                key=key,
                fingerprint=fingerprint,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise FulfillmentConflictError("Closure request already exists") from error
