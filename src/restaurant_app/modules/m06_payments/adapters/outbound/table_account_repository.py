"""Transactional persistence for consolidated table accounts."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m03_tables.adapters.outbound.models import (
    RestaurantTableModel,
    TableAccountModel,
)
from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderItemModel, OrderModel
from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel
from restaurant_app.modules.m06_payments.domain.entities import (
    TableAccountChargeState,
    TableAccountLine,
    TableAccountOrder,
    TableAccountPayment,
    TableAccountSummary,
)
from restaurant_app.modules.m06_payments.domain.errors import (
    PaymentConflictError,
    PaymentNotFoundError,
)
from restaurant_app.shared.adapters.outbound.models import IdempotencyRequestModel


class SqlAlchemyTableAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> UUID | None:
        lock_name = f"RECORD_TABLE_ACCOUNT_COLLECTION:{actor_id}:{key}"
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_name, 0)))
        )
        request = (
            await self._session.scalars(
                select(IdempotencyRequestModel).where(
                    IdempotencyRequestModel.actor_user_id == actor_id,
                    IdempotencyRequestModel.operation == "RECORD_TABLE_ACCOUNT_COLLECTION",
                    IdempotencyRequestModel.request_key == key,
                )
            )
        ).one_or_none()
        if request is None:
            return None
        if request.request_hash != fingerprint or request.result_table_account_id is None:
            raise PaymentConflictError("Idempotency-Key was already used for another request")
        payment_id = await self._session.scalar(
            select(PaymentModel.id).where(
                PaymentModel.operation_request_id == request.id,
                PaymentModel.table_account_id == request.result_table_account_id,
            )
        )
        if request.completed_at is None or payment_id is None:
            raise PaymentConflictError("Stored table collection result is unavailable")
        return request.result_table_account_id

    async def get_account_for_table(
        self, table_id: UUID, *, open_only: bool = False, lock: bool = False
    ) -> TableAccountModel | None:
        statement = select(TableAccountModel).where(TableAccountModel.table_id == table_id)
        if open_only:
            statement = statement.where(TableAccountModel.status == "OPEN")
        else:
            statement = statement.order_by(
                case((TableAccountModel.status == "OPEN", 0), else_=1),
                TableAccountModel.opened_at.desc(),
            )
        statement = statement.limit(1)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return (await self._session.scalars(statement)).one_or_none()

    async def get_summary_by_table(self, table_id: UUID) -> TableAccountSummary:
        account = await self.get_account_for_table(table_id)
        if account is None:
            raise PaymentNotFoundError("Table account not found")
        return await self._summary(account)

    async def get_summary(self, account_id: UUID) -> TableAccountSummary:
        account = await self._session.get(TableAccountModel, account_id)
        if account is None:
            raise PaymentNotFoundError("Table account not found")
        return await self._summary(account)

    async def open_account_state(self, table_id: UUID) -> TableAccountChargeState:
        account = await self.get_account_for_table(table_id, open_only=True, lock=True)
        if account is None:
            raise PaymentNotFoundError("Open table account not found")
        orders = list(
            (
                await self._session.scalars(
                    select(OrderModel)
                    .where(OrderModel.table_account_id == account.id)
                    .order_by(OrderModel.created_at, OrderModel.id)
                    .with_for_update()
                )
            ).all()
        )
        if not orders:
            raise PaymentConflictError("The table account has no orders")
        total = sum((order.total_amount for order in orders), Decimal("0.00"))
        paid = Decimal(
            str(
                await self._session.scalar(
                    select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
                        or_(
                            PaymentModel.table_account_id == account.id,
                            PaymentModel.order_id.in_([order.id for order in orders]),
                        )
                    )
                )
            )
        )
        return TableAccountChargeState(
            id=account.id,
            table_id=account.table_id,
            order_ids=tuple(order.id for order in orders),
            order_statuses=tuple(order.status for order in orders),
            total_amount=total,
            paid_amount=paid,
        )

    async def record_payment(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        request_key: str,
        fingerprint: str,
        amount: Decimal,
        method_code: str,
        reference_code: str | None,
    ) -> None:
        request = IdempotencyRequestModel(
            actor_user_id=actor_id,
            operation="RECORD_TABLE_ACCOUNT_COLLECTION",
            request_key=request_key,
            request_hash=fingerprint,
            result_table_account_id=account_id,
            expires_at=func.clock_timestamp() + timedelta(hours=24),
        )
        self._session.add(request)
        await self._session.flush()
        self._session.add(
            PaymentModel(
                table_account_id=account_id,
                kind="COLLECTION",
                amount=amount,
                method_code=method_code,
                reference_code=reference_code,
                recorded_by_user_id=actor_id,
                operation_request_id=request.id,
            )
        )
        await self._session.flush()
        request.completed_at = func.clock_timestamp()
        await self._session.flush()

    async def settle(
        self,
        *,
        account_id: UUID,
        order_ids: tuple[UUID, ...],
        actor_id: UUID,
    ) -> None:
        account = await self._session.get(TableAccountModel, account_id)
        if account is None or account.status != "OPEN":
            raise PaymentConflictError("The table account is no longer open")
        orders = list(
            (
                await self._session.scalars(
                    select(OrderModel)
                    .where(OrderModel.id.in_(order_ids), OrderModel.table_account_id == account.id)
                    .with_for_update()
                )
            ).all()
        )
        if len(orders) != len(order_ids):
            raise PaymentConflictError("The table account changed during collection")
        other_active = await self._session.scalar(
            select(func.count())
            .select_from(OrderModel)
            .where(
                OrderModel.table_id == account.table_id,
                OrderModel.status.in_(["REQUESTED", "APPROVED", "CONFIRMED"]),
                or_(
                    OrderModel.table_account_id.is_(None),
                    OrderModel.table_account_id != account.id,
                ),
            )
        )
        if other_active:
            raise PaymentConflictError("The table has consumptions outside its open account")
        now = func.clock_timestamp()
        for order in orders:
            order.status = "CLOSED"
            order.closed_by_user_id = actor_id
            order.closed_at = now
            order.version += 1
        account.status = "PAID"
        account.closed_at = now
        account.closed_by_user_id = actor_id
        table = await self._session.get(RestaurantTableModel, account.table_id)
        if table is None:
            raise PaymentNotFoundError("Table not found")
        table.is_occupied = False
        table.occupancy_started_at = None
        table.updated_at = now
        table.updated_by_user_id = actor_id
        await self._session.flush()

    async def _summary(self, account: TableAccountModel) -> TableAccountSummary:
        table = await self._session.get(RestaurantTableModel, account.table_id)
        if table is None:
            raise PaymentNotFoundError("Table not found")
        orders = list(
            (
                await self._session.scalars(
                    select(OrderModel)
                    .where(OrderModel.table_account_id == account.id)
                    .order_by(OrderModel.created_at, OrderModel.id)
                )
            ).all()
        )
        order_ids = [order.id for order in orders]
        line_models = (
            list(
                (
                    await self._session.scalars(
                        select(OrderItemModel)
                        .where(OrderItemModel.order_id.in_(order_ids))
                        .order_by(OrderItemModel.id)
                    )
                ).all()
            )
            if order_ids
            else []
        )
        lines_by_order: dict[UUID, list[TableAccountLine]] = defaultdict(list)
        for line in line_models:
            lines_by_order[line.order_id].append(
                TableAccountLine(
                    product_id=line.product_id,
                    product_name=line.product_name_snapshot,
                    quantity=line.quantity,
                    unit_price=line.unit_price_snapshot,
                )
            )

        payment_predicate = PaymentModel.table_account_id == account.id
        if order_ids:
            payment_predicate = or_(payment_predicate, PaymentModel.order_id.in_(order_ids))
        payment_models = list(
            (
                await self._session.scalars(
                    select(PaymentModel)
                    .where(payment_predicate)
                    .order_by(PaymentModel.recorded_at, PaymentModel.id)
                )
            ).all()
        )
        paid_by_order: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for payment in payment_models:
            if payment.order_id is not None:
                paid_by_order[payment.order_id] += payment.amount
        # Consolidated collections are allocated oldest-order-first for the legacy
        # per-order payment views. The account payment itself remains immutable.
        for payment in payment_models:
            if payment.table_account_id is None:
                continue
            remaining = payment.amount
            for order in orders:
                capacity = max(order.total_amount - paid_by_order[order.id], Decimal("0.00"))
                allocation = min(capacity, remaining)
                paid_by_order[order.id] += allocation
                remaining -= allocation
                if remaining <= 0:
                    break

        order_views = tuple(
            TableAccountOrder(
                id=order.id,
                status=order.status,
                total_amount=order.total_amount,
                paid_amount=paid_by_order[order.id],
                created_at=order.created_at,
                lines=tuple(lines_by_order[order.id]),
            )
            for order in orders
        )
        payments = tuple(
            TableAccountPayment(
                id=payment.id,
                order_id=payment.order_id,
                amount=payment.amount,
                kind=payment.kind,
                method_code=payment.method_code,
                reference_code=payment.reference_code,
                recorded_by_user_id=payment.recorded_by_user_id,
                recorded_at=payment.recorded_at,
            )
            for payment in payment_models
        )
        total = sum((order.total_amount for order in orders), Decimal("0.00"))
        paid = sum((payment.amount for payment in payment_models), Decimal("0.00"))
        advances = sum(
            (payment.amount for payment in payment_models if payment.kind == "ADVANCE"),
            Decimal("0.00"),
        )
        return TableAccountSummary(
            id=account.id,
            table_id=account.table_id,
            table_code=table.code,
            status=account.status,
            customer_user_id=account.customer_user_id,
            guest_session_id=account.guest_session_id,
            opened_at=account.opened_at,
            closed_at=account.closed_at,
            total_amount=total,
            advance_amount=advances,
            paid_amount=paid,
            balance=total - paid,
            orders=order_views,
            payments=payments,
        )
