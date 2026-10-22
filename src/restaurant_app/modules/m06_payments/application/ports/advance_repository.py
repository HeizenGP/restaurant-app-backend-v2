"""Ports for the advance slice; M04 is consumed only through its public contract."""

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m04_orders.public import OrderForAdvance
from restaurant_app.modules.m06_payments.domain.entities import AdvancePayment


class AdvanceOrderReader(Protocol):
    async def get_order(self, order_id: UUID, *, lock: bool = False) -> OrderForAdvance | None: ...


class AdvanceRepository(Protocol):
    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> UUID | None: ...

    async def get_advance(self, order_id: UUID) -> AdvancePayment | None: ...

    async def record_verification(
        self,
        *,
        actor_id: UUID,
        request_key: str,
        fingerprint: str,
        order_id: UUID,
        amount: Decimal,
        existing: AdvancePayment | None,
    ) -> AdvancePayment: ...
