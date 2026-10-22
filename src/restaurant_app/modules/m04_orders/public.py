"""Read-only M04 contracts for consumers of order snapshots.

Consumers depend on this snapshot, never on M04 persistence or domain internals.
The caller supplies its shared transaction and decides whether to lock the order.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderItemModel, OrderModel
from restaurant_app.modules.m04_orders.adapters.outbound.repositories import (
    SqlAlchemyOrderRepository,
)


@dataclass(frozen=True, slots=True)
class OrderForAdvance:
    id: UUID
    modality: str
    status: str
    total_amount: Decimal
    customer_user_id: UUID | None
    guest_session_id: UUID | None


class AdvanceOrderReader(Protocol):
    async def get_order(self, order_id: UUID, *, lock: bool = False) -> OrderForAdvance | None: ...


class SqlAlchemyAdvanceOrderReader:
    def __init__(self, session: AsyncSession) -> None:
        self._orders = SqlAlchemyOrderRepository(session)

    async def get_order(self, order_id: UUID, *, lock: bool = False) -> OrderForAdvance | None:
        order = await self._orders.get_order(order_id, lock=lock)
        if order is None:
            return None
        return OrderForAdvance(
            id=order.id,
            modality=order.modality.value,
            status=order.status,
            total_amount=order.total_amount,
            customer_user_id=order.customer_user_id,
            guest_session_id=order.guest_session_id,
        )


@dataclass(frozen=True, slots=True)
class KitchenOrderLine:
    product_id: UUID
    product_name_snapshot: str
    quantity: int


@dataclass(frozen=True, slots=True)
class OrderForKitchen:
    id: UUID
    modality: str
    lines: tuple[KitchenOrderLine, ...]


class KitchenOrderReader(Protocol):
    async def get_confirmed_orders(
        self, order_ids: Sequence[UUID]
    ) -> dict[UUID, OrderForKitchen]: ...


class SqlAlchemyKitchenOrderReader:
    """M04-owned batch snapshot; M05 never accesses M04 persistence directly."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_confirmed_orders(self, order_ids: Sequence[UUID]) -> dict[UUID, OrderForKitchen]:
        if not order_ids:
            return {}
        orders = (
            await self._session.scalars(
                select(OrderModel).where(
                    OrderModel.id.in_(order_ids), OrderModel.status == "CONFIRMED"
                )
            )
        ).all()
        if not orders:
            return {}
        lines = (
            await self._session.scalars(
                select(OrderItemModel)
                .where(OrderItemModel.order_id.in_([order.id for order in orders]))
                .order_by(OrderItemModel.order_id, OrderItemModel.id)
            )
        ).all()
        by_order: dict[UUID, list[KitchenOrderLine]] = {order.id: [] for order in orders}
        for line in lines:
            by_order[line.order_id].append(
                KitchenOrderLine(line.product_id, line.product_name_snapshot, line.quantity)
            )
        return {
            order.id: OrderForKitchen(order.id, order.modality, tuple(by_order[order.id]))
            for order in orders
        }


# ---------------------------------------------------------------------------
# Collection contract (08.08 — cashier reads the confirmed/closed order)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OrderForCollection:
    id: UUID
    modality: str
    status: str
    total_amount: Decimal
    customer_user_id: UUID | None
    guest_session_id: UUID | None


class CollectionOrderReader(Protocol):
    async def get_order_for_collection(
        self, order_id: UUID, *, lock: bool = False
    ) -> OrderForCollection | None: ...


class SqlAlchemyCollectionOrderReader:
    """Read-only order snapshot for cashier; uses caller's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._orders = SqlAlchemyOrderRepository(session)

    async def get_order_for_collection(
        self, order_id: UUID, *, lock: bool = False
    ) -> OrderForCollection | None:
        order = await self._orders.get_order(order_id, lock=lock)
        if order is None:
            return None
        return OrderForCollection(
            id=order.id,
            modality=order.modality.value,
            status=order.status,
            total_amount=order.total_amount,
            customer_user_id=order.customer_user_id,
            guest_session_id=order.guest_session_id,
        )
