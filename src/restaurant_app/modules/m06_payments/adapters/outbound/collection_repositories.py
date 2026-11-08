"""PostgreSQL persistence for cashier collections (COLLECTION kind)."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderModel
from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel
from restaurant_app.modules.m06_payments.domain.entities import (
    AdvancePayment,
    CollectionPayment,
)
from restaurant_app.modules.m06_payments.domain.errors import PaymentConflictError
from restaurant_app.shared.adapters.outbound.models import IdempotencyRequestModel


class SqlAlchemyCollectionRepository:
    """Cashier payment persistence using the caller's session/UoW."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> UUID | None:
        """Serialize same actor/key before looking for an already completed op."""
        lock_name = f"RECORD_COLLECTION:{actor_id}:{key}"
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_name, 0)))
        )
        request = (
            await self._session.scalars(
                select(IdempotencyRequestModel).where(
                    IdempotencyRequestModel.actor_user_id == actor_id,
                    IdempotencyRequestModel.operation == "RECORD_COLLECTION",
                    IdempotencyRequestModel.request_key == key,
                )
            )
        ).one_or_none()
        if request is None:
            return None
        if request.request_hash != fingerprint or request.result_order_id is None:
            raise PaymentConflictError("Idempotency-Key was already used for another request")
        payment_id = await self._session.scalar(
            select(PaymentModel.id).where(
                PaymentModel.operation_request_id == request.id,
                PaymentModel.order_id == request.result_order_id,
                PaymentModel.kind == "COLLECTION",
            )
        )
        if request.completed_at is None or payment_id is None:
            raise PaymentConflictError("Stored collection result is unavailable")
        return request.result_order_id

    async def list_payments(self, order_id: UUID) -> list[AdvancePayment | CollectionPayment]:
        """All payments (advance + collections) for the order, chronologically."""
        models = list(
            (
                await self._session.scalars(
                    select(PaymentModel)
                    .where(PaymentModel.order_id == order_id)
                    .order_by(PaymentModel.recorded_at)
                )
            ).all()
        )
        result: list[AdvancePayment | CollectionPayment] = []
        for m in models:
            assert m.order_id is not None
            if m.kind == "ADVANCE":
                result.append(
                    AdvancePayment(
                        id=m.id,
                        order_id=m.order_id,
                        amount=m.amount,
                        recorded_by_user_id=m.recorded_by_user_id,
                        recorded_at=m.recorded_at,
                    )
                )
            else:
                result.append(
                    CollectionPayment(
                        id=m.id,
                        order_id=m.order_id,
                        amount=m.amount,
                        method_code=m.method_code,
                        reference_code=m.reference_code,
                        recorded_by_user_id=m.recorded_by_user_id,
                        recorded_at=m.recorded_at,
                    )
                )
        result.extend(await self._allocated_account_payments(order_id))
        return sorted(result, key=lambda payment: payment.recorded_at)

    async def sum_paid(self, order_id: UUID) -> Decimal:
        """Total amount already paid (advance + collections)."""
        payments = await self.list_payments(order_id)
        return sum((payment.amount for payment in payments), Decimal("0.00"))

    async def _allocated_account_payments(self, order_id: UUID) -> list[CollectionPayment]:
        """Project consolidated payments onto orders, oldest outstanding order first."""
        target = await self._session.get(OrderModel, order_id)
        if target is None or target.table_account_id is None:
            return []
        orders = list(
            (
                await self._session.scalars(
                    select(OrderModel)
                    .where(OrderModel.table_account_id == target.table_account_id)
                    .order_by(OrderModel.created_at, OrderModel.id)
                )
            ).all()
        )
        order_ids = [order.id for order in orders]
        direct_rows = (
            await self._session.execute(
                select(PaymentModel.order_id, func.coalesce(func.sum(PaymentModel.amount), 0))
                .where(PaymentModel.order_id.in_(order_ids))
                .group_by(PaymentModel.order_id)
            )
        ).all()
        paid_by_order = {row[0]: Decimal(str(row[1])) for row in direct_rows}
        account_payments = list(
            (
                await self._session.scalars(
                    select(PaymentModel)
                    .where(PaymentModel.table_account_id == target.table_account_id)
                    .order_by(PaymentModel.recorded_at, PaymentModel.id)
                )
            ).all()
        )
        allocations: list[CollectionPayment] = []
        for payment in account_payments:
            remaining = payment.amount
            for order in orders:
                already = paid_by_order.get(order.id, Decimal("0.00"))
                allocation = min(max(order.total_amount - already, Decimal("0.00")), remaining)
                if allocation > 0:
                    paid_by_order[order.id] = already + allocation
                    if order.id == order_id:
                        allocations.append(
                            CollectionPayment(
                                id=payment.id,
                                order_id=order_id,
                                amount=allocation,
                                method_code=payment.method_code,
                                reference_code=payment.reference_code,
                                recorded_by_user_id=payment.recorded_by_user_id,
                                recorded_at=payment.recorded_at,
                            )
                        )
                    remaining -= allocation
                if remaining <= 0:
                    break
        return allocations

    async def record_collection(
        self,
        *,
        actor_id: UUID,
        request_key: str,
        fingerprint: str,
        order_id: UUID,
        amount: Decimal,
        method_code: str,
        reference_code: str | None,
    ) -> CollectionPayment:
        """Insert a new COLLECTION payment and its idempotency record."""
        request = IdempotencyRequestModel(
            actor_user_id=actor_id,
            operation="RECORD_COLLECTION",
            request_key=request_key,
            request_hash=fingerprint,
            expires_at=func.clock_timestamp() + timedelta(hours=24),
        )
        self._session.add(request)
        await self._session.flush()

        payment = PaymentModel(
            order_id=order_id,
            kind="COLLECTION",
            amount=amount,
            method_code=method_code,
            reference_code=reference_code,
            recorded_by_user_id=actor_id,
            operation_request_id=request.id,
        )
        self._session.add(payment)
        await self._session.flush()
        await self._session.refresh(payment)
        assert payment.order_id is not None

        request.result_order_id = order_id
        request.completed_at = func.clock_timestamp()
        await self._session.flush()

        return CollectionPayment(
            id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            method_code=payment.method_code or method_code,
            reference_code=payment.reference_code,
            recorded_by_user_id=payment.recorded_by_user_id,
            recorded_at=payment.recorded_at,
        )
