"""Confirm a reviewed order with one caller-owned PostgreSQL transaction."""

import hashlib
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m02_catalog_stock.public import StockAllocation, StockConfirmationError
from restaurant_app.modules.m04_orders.application.ports.confirmation import (
    ConfirmationAdvance,
    ConfirmationOrders,
    ConfirmationStock,
    ConfirmationTables,
    ConfirmationTickets,
)
from restaurant_app.modules.m04_orders.domain.entities import Channel, Modality, Order, OrderStatus
from restaurant_app.modules.m04_orders.domain.errors import (
    InvalidOrderError,
    OrderConflictError,
    OrderNotFoundError,
    ProductUnavailableError,
)
from restaurant_app.modules.m05_kitchen.public import KitchenTicketConflict
from restaurant_app.modules.m06_payments.public import required_advance_amount


class ConfirmOrder:
    """Validate first, then debit, confirm, issue and log before one commit."""

    def __init__(
        self,
        orders: ConfirmationOrders,
        tables: ConfirmationTables,
        stock: ConfirmationStock,
        advances: ConfirmationAdvance,
        tickets: ConfirmationTickets,
    ) -> None:
        self._orders = orders
        self._tables = tables
        self._stock = stock
        self._advances = advances
        self._tickets = tickets

    async def __call__(self, *, actor: Principal, order_id: UUID, request_key: str) -> Order:
        AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)(actor)
        assert actor.user_id is not None
        if not 1 <= len(request_key) <= 128 or not request_key.strip():
            raise InvalidOrderError("Idempotency-Key must contain 1 to 128 characters")
        fingerprint = hashlib.sha256(str(order_id).encode()).hexdigest()
        replay_id = await self._orders.find_confirmation(
            actor_id=actor.user_id, key=request_key, fingerprint=fingerprint
        )
        candidate = await self._orders.get_order(order_id)
        if candidate is None:
            raise OrderNotFoundError
        self._authorize(actor, candidate)
        if replay_id is not None:
            if replay_id != order_id or candidate.status != OrderStatus.CONFIRMED:
                raise OrderConflictError("Stored confirmation result is unavailable")
            await self._require_ticket(order_id)
            return candidate
        if candidate.status == OrderStatus.CONFIRMED:
            await self._require_ticket(order_id)
            await self._orders.record_confirmation(
                actor_id=actor.user_id,
                key=request_key,
                fingerprint=fingerprint,
                order_id=order_id,
            )
            return candidate
        if candidate.status != OrderStatus.APPROVED:
            raise OrderConflictError("Only approved orders can be confirmed")
        table = None
        if candidate.modality is Modality.LOCAL:
            if candidate.table_id is None:
                raise OrderConflictError("Local order has no table")
            # Keep the M03 row stable before locking M04, matching approval's table→order order.
            table = await self._tables.get_table(candidate.table_id)
            if table is None or not table.is_occupied or table.occupancy_started_at is None:
                raise OrderConflictError("The local table is not occupied")
        order = await self._orders.get_order(order_id, lock=True)
        if order is None:
            raise OrderNotFoundError
        self._authorize(actor, order)
        if order.status == OrderStatus.CONFIRMED:
            await self._require_ticket(order_id)
            await self._orders.record_confirmation(
                actor_id=actor.user_id,
                key=request_key,
                fingerprint=fingerprint,
                order_id=order_id,
            )
            return order
        if order.status != OrderStatus.APPROVED:
            raise OrderConflictError("Only approved orders can be confirmed")
        if order.modality is Modality.LOCAL:
            assert table is not None
            assert table.occupancy_started_at is not None
            if order.table_id != table.id:
                raise OrderConflictError("The order table changed")
            if order.channel is Channel.APP and (
                order.table_verified_at is None
                or order.table_verified_at < table.occupancy_started_at
            ):
                raise OrderConflictError("Local APP order needs current in-person verification")
        else:
            advance = await self._advances.get_verified_advance(order_id)
            if advance is None or advance.amount != required_advance_amount(order.total_amount):
                raise OrderConflictError("The required 50% advance has not been verified")
        if not order.lines or any(line.id is None for line in order.lines):
            raise OrderConflictError("Order has no persisted lines")
        allocations = tuple(
            StockAllocation(line.id, line.product_id, line.quantity)
            for line in order.lines
            if line.id is not None
        )
        try:
            await self._stock.debit_order(allocations, actor_id=actor.user_id)
        except StockConfirmationError as error:
            raise ProductUnavailableError(str(error)) from error
        confirmed = await self._orders.mark_confirmed(order_id, actor_id=actor.user_id)
        try:
            await self._tickets.create_for_order(order_id)
        except KitchenTicketConflict as error:
            raise OrderConflictError(str(error)) from error
        await self._orders.record_confirmation(
            actor_id=actor.user_id, key=request_key, fingerprint=fingerprint, order_id=order_id
        )
        return confirmed

    @staticmethod
    def _authorize(actor: Principal, order: Order) -> None:
        if order.modality is Modality.LOCAL:
            if order.channel is Channel.WAITER:
                AuthorizeRoles(RoleCode.WAITER)(actor)
            elif order.channel is Channel.APP:
                AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)(actor)
            else:
                raise OrderConflictError("Unsupported local order channel")
        else:
            AuthorizeRoles(RoleCode.ADMIN)(actor)
            if order.channel not in {Channel.APP, Channel.PHONE, Channel.WHATSAPP}:
                raise OrderConflictError("Unsupported remote order channel")

    async def _require_ticket(self, order_id: UUID) -> None:
        if not await self._tickets.exists_for_order(order_id):
            raise OrderConflictError("Confirmed order has no kitchen ticket")
