"""Ports consumed by M07 use cases; other modules are reached via public contracts."""

from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m07_fulfillment.domain.entities import Fulfillment, FulfillmentKind


class FulfillmentRepository(Protocol):
    async def find_request(
        self, *, operation: str, actor_id: UUID, key: str, fingerprint: str
    ) -> UUID | None: ...

    async def get(self, order_id: UUID) -> Fulfillment | None: ...

    async def record(
        self,
        *,
        actor_id: UUID,
        order_id: UUID,
        kind: FulfillmentKind,
        key: str,
        fingerprint: str,
    ) -> Fulfillment: ...

    async def record_close(
        self, *, actor_id: UUID, order_id: UUID, key: str, fingerprint: str
    ) -> None: ...
