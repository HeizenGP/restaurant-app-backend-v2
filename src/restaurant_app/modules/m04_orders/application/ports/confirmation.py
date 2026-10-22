"""Consumer-owned ports for the cross-module confirmation transaction."""

from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m02_catalog_stock.public import StockAllocation
from restaurant_app.modules.m04_orders.domain.entities import Order, TableAvailability
from restaurant_app.modules.m06_payments.public import VerifiedAdvance


class ConfirmationOrders(Protocol):
    async def find_confirmation(
        self, *, actor_id: UUID, key: str, fingerprint: str
    ) -> UUID | None: ...

    async def get_order(self, order_id: UUID, *, lock: bool = False) -> Order | None: ...

    async def mark_confirmed(self, order_id: UUID, *, actor_id: UUID) -> Order: ...

    async def record_confirmation(
        self, *, actor_id: UUID, key: str, fingerprint: str, order_id: UUID
    ) -> None: ...


class ConfirmationTables(Protocol):
    async def get_table(self, table_id: UUID) -> TableAvailability | None: ...


class ConfirmationStock(Protocol):
    async def debit_order(
        self, allocations: tuple[StockAllocation, ...], *, actor_id: UUID
    ) -> None: ...


class ConfirmationAdvance(Protocol):
    async def get_verified_advance(self, order_id: UUID) -> VerifiedAdvance | None: ...


class ConfirmationTickets(Protocol):
    async def create_for_order(self, order_id: UUID) -> UUID: ...

    async def exists_for_order(self, order_id: UUID) -> bool: ...
