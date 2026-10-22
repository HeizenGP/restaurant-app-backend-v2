"""Ports for the collection (cashier) slice; M04 consumed via public contract."""

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m04_orders.public import OrderForCollection
from restaurant_app.modules.m06_payments.domain.entities import (
    AdvancePayment,
    CollectionPayment,
)


class CollectionOrderReader(Protocol):
    """Read order header for cashier operations."""

    async def get_order_for_collection(
        self, order_id: UUID, *, lock: bool = False
    ) -> OrderForCollection | None: ...


class CollectionHandoverReader(Protocol):
    async def has_handover(self, order_id: UUID, *, kind: str) -> bool: ...


class CollectionRepository(Protocol):
    """Cashier payment persistence."""

    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> UUID | None: ...

    async def list_payments(self, order_id: UUID) -> list[AdvancePayment | CollectionPayment]: ...

    async def sum_paid(self, order_id: UUID) -> Decimal: ...

    async def record_collection(
        self,
        *,
        actor_id: UUID,
        request_key: str,
        fingerprint: str,
        order_id: UUID,
        amount: Decimal,
        method_code: str,
    ) -> CollectionPayment: ...
