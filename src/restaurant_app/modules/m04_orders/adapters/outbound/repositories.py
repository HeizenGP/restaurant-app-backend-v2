"""One-transaction PostgreSQL persistence for M04 requests and decisions."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderItemModel, OrderModel
from restaurant_app.modules.m04_orders.domain.entities import (
    Channel,
    Modality,
    Order,
    OrderLine,
    OrderStatus,
)
from restaurant_app.modules.m04_orders.domain.errors import OrderConflictError
from restaurant_app.shared.adapters.outbound.models import IdempotencyRequestModel


class SqlAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _order(self, model: OrderModel) -> Order:
        rows = (
            await self._session.scalars(
                select(OrderItemModel)
                .where(OrderItemModel.order_id == model.id)
                .order_by(OrderItemModel.id)
            )
        ).all()
        return Order(
            id=model.id,
            modality=Modality(model.modality),
            channel=Channel(model.channel),
            status=model.status,
            customer_user_id=model.customer_user_id,
            guest_session_id=model.guest_session_id,
            created_by_user_id=model.created_by_user_id,
            table_id=model.table_id,
            table_account_id=model.table_account_id,
            delivery_address=model.delivery_address,
            contact_name=model.contact_name,
            contact_phone=model.contact_phone,
            total_amount=model.total_amount,
            lines=tuple(
                OrderLine(
                    product_id=row.product_id,
                    product_name_snapshot=row.product_name_snapshot,
                    quantity=row.quantity,
                    unit_price_snapshot=row.unit_price_snapshot,
                    id=row.id,
                )
                for row in rows
            ),
            created_at=model.created_at,
            decided_by_user_id=model.decided_by_user_id,
            decided_at=model.decided_at,
            table_verified_at=model.table_verified_at,
        )

    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> Order | None:
        # Serialize same-actor/same-key submissions before looking for the unique row.
        lock_name = f"CREATE_ORDER:{actor_id}:{key}"
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_name, 0)))
        )
        request = (
            await self._session.scalars(
                select(IdempotencyRequestModel).where(
                    IdempotencyRequestModel.operation == "CREATE_ORDER",
                    IdempotencyRequestModel.request_key == key,
                    or_(
                        IdempotencyRequestModel.actor_user_id == actor_id,
                        IdempotencyRequestModel.actor_guest_session_id == actor_id,
                    ),
                )
            )
        ).one_or_none()
        if request is None:
            return None
        if request.request_hash != fingerprint or request.result_order_id is None:
            raise OrderConflictError("Idempotency-Key was already used for another request")
        model = await self._session.get(OrderModel, request.result_order_id)
        if model is None:  # pragma: no cover - FK prevents this in a healthy database
            raise OrderConflictError("Stored request result is unavailable")
        return await self._order(model)

    async def has_verified_active_table_order(
        self,
        *,
        table_id: UUID,
        occupied_since: datetime,
        customer_user_id: UUID | None,
        guest_session_id: UUID | None,
    ) -> bool:
        if (customer_user_id is None) == (guest_session_id is None):
            return False
        owner = (
            OrderModel.customer_user_id == customer_user_id
            if customer_user_id is not None
            else OrderModel.guest_session_id == guest_session_id
        )
        # Only an earlier, in-person-verified APP order establishes table membership.
        # CONFIRMED exists in the approved schema; its transition belongs to 08.07.
        statement = (
            select(OrderModel.id)
            .where(
                OrderModel.table_id == table_id,
                OrderModel.modality == Modality.LOCAL.value,
                OrderModel.channel == Channel.APP.value,
                OrderModel.table_verified_at.is_not(None),
                OrderModel.table_verified_at >= occupied_since,
                OrderModel.status.in_((OrderStatus.APPROVED.value, "CONFIRMED")),
                owner,
            )
            .limit(1)
            .with_for_update(read=True)
        )
        return (await self._session.scalar(statement)) is not None

    async def has_conflicting_verified_table_owner(
        self,
        *,
        table_id: UUID,
        occupied_since: datetime,
        customer_user_id: UUID | None,
        guest_session_id: UUID | None,
    ) -> bool:
        statement = (
            select(OrderModel.customer_user_id, OrderModel.guest_session_id)
            .where(
                OrderModel.table_id == table_id,
                OrderModel.modality == Modality.LOCAL.value,
                OrderModel.channel == Channel.APP.value,
                OrderModel.table_verified_at >= occupied_since,
                OrderModel.status.in_((OrderStatus.APPROVED.value, "CONFIRMED")),
            )
            .with_for_update(read=True)
        )
        owners = (await self._session.execute(statement)).all()
        return any(
            user_id != customer_user_id or session_id != guest_session_id
            for user_id, session_id in owners
        )

    async def create_order(
        self,
        *,
        actor_id: UUID,
        request_key: str,
        fingerprint: str,
        modality: Modality,
        channel: Channel,
        customer_user_id: UUID | None,
        guest_session_id: UUID | None,
        created_by_user_id: UUID | None,
        table_id: UUID | None,
        table_account_id: UUID | None,
        delivery_address: str | None,
        contact_name: str | None,
        contact_phone: str | None,
        lines: tuple[OrderLine, ...],
    ) -> Order:
        request = IdempotencyRequestModel(
            actor_user_id=actor_id if guest_session_id is None else None,
            actor_guest_session_id=guest_session_id,
            operation="CREATE_ORDER",
            request_key=request_key,
            request_hash=fingerprint,
            expires_at=func.clock_timestamp() + timedelta(hours=24),
        )
        self._session.add(request)
        await self._session.flush()
        total = sum((line.unit_price_snapshot * line.quantity for line in lines), Decimal("0.00"))
        model = OrderModel(
            modality=modality.value,
            channel=channel.value,
            status=OrderStatus.REQUESTED.value,
            customer_user_id=customer_user_id,
            guest_session_id=guest_session_id,
            created_by_user_id=created_by_user_id,
            table_id=table_id,
            table_account_id=table_account_id,
            delivery_address=delivery_address,
            contact_name=contact_name,
            contact_phone=contact_phone,
            total_amount=total,
        )
        self._session.add(model)
        await self._session.flush()
        self._session.add_all(
            OrderItemModel(
                order_id=model.id,
                product_id=line.product_id,
                product_name_snapshot=line.product_name_snapshot,
                quantity=line.quantity,
                unit_price_snapshot=line.unit_price_snapshot,
            )
            for line in lines
        )
        await self._session.flush()
        if channel is not Channel.APP:
            # Header UPDATE happens only after all immutable lines were inserted.
            model.status = OrderStatus.APPROVED.value
            model.decided_by_user_id = actor_id
            model.decided_at = func.clock_timestamp()
            await self._session.flush()
        request.result_order_id = model.id
        request.completed_at = func.clock_timestamp()
        await self._session.flush()
        await self._session.refresh(model)
        return await self._order(model)

    async def get_order(self, order_id: UUID, *, lock: bool = False) -> Order | None:
        statement = select(OrderModel).where(OrderModel.id == order_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        model = (await self._session.scalars(statement)).one_or_none()
        return None if model is None else await self._order(model)

    async def list_orders(
        self,
        *,
        customer_user_id: UUID | None,
        guest_session_id: UUID | None,
        staff_local: bool,
        staff_all: bool,
    ) -> list[Order]:
        statement = select(OrderModel)
        if not staff_all:
            predicates = []
            if customer_user_id is not None:
                predicates.append(OrderModel.customer_user_id == customer_user_id)
            if guest_session_id is not None:
                predicates.append(OrderModel.guest_session_id == guest_session_id)
            if staff_local:
                predicates.append(and_(OrderModel.modality == Modality.LOCAL.value))
            if not predicates:
                return []
            statement = statement.where(or_(*predicates))
        models = (
            await self._session.scalars(statement.order_by(OrderModel.created_at.desc()))
        ).all()
        return [await self._order(model) for model in models]

    async def decide_order(
        self, order_id: UUID, *, approved: bool, actor_id: UUID, table_verified: bool
    ) -> Order:
        model = await self._session.get(OrderModel, order_id)
        assert model is not None
        model.status = OrderStatus.APPROVED.value if approved else OrderStatus.REJECTED.value
        model.decided_by_user_id = actor_id
        model.decided_at = func.clock_timestamp()
        if table_verified:
            model.table_verified_at = func.clock_timestamp()
        await self._session.flush()
        await self._session.refresh(model)
        return await self._order(model)

    async def find_confirmation(self, *, actor_id: UUID, key: str, fingerprint: str) -> UUID | None:
        # The operation/key lock precedes row locks for every confirmation path.
        lock_name = f"CONFIRM_ORDER:{actor_id}:{key}"
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_name, 0)))
        )
        request = (
            await self._session.scalars(
                select(IdempotencyRequestModel).where(
                    IdempotencyRequestModel.actor_user_id == actor_id,
                    IdempotencyRequestModel.operation == "CONFIRM_ORDER",
                    IdempotencyRequestModel.request_key == key,
                )
            )
        ).one_or_none()
        if request is None:
            return None
        if request.request_hash != fingerprint or request.result_order_id is None:
            raise OrderConflictError("Idempotency-Key was already used for another confirmation")
        return request.result_order_id

    async def mark_confirmed(self, order_id: UUID, *, actor_id: UUID) -> Order:
        model = await self._session.get(OrderModel, order_id)
        assert model is not None
        model.status = OrderStatus.CONFIRMED.value
        model.confirmed_by_user_id = actor_id
        model.confirmed_at = func.clock_timestamp()
        model.version += 1
        await self._session.flush()
        await self._session.refresh(model)
        return await self._order(model)

    async def record_confirmation(
        self, *, actor_id: UUID, key: str, fingerprint: str, order_id: UUID
    ) -> None:
        self._session.add(
            IdempotencyRequestModel(
                actor_user_id=actor_id,
                operation="CONFIRM_ORDER",
                request_key=key,
                request_hash=fingerprint,
                result_order_id=order_id,
                completed_at=func.clock_timestamp(),
                expires_at=func.clock_timestamp() + timedelta(hours=24),
            )
        )
        await self._session.flush()
