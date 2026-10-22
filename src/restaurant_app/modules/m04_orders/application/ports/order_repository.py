"""Ports consumed by request registration and decision handlers."""

from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m04_orders.domain.entities import (
    Channel,
    Modality,
    Order,
    OrderLine,
    ProductQuote,
    TableAvailability,
)


class ProductReader(Protocol):
    async def get_product(self, product_id: UUID) -> ProductQuote | None: ...


class TableReader(Protocol):
    async def get_table(self, table_id: UUID) -> TableAvailability | None: ...


class OrderRepository(Protocol):
    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> Order | None: ...

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
        delivery_address: str | None,
        contact_name: str | None,
        contact_phone: str | None,
        lines: tuple[OrderLine, ...],
    ) -> Order: ...

    async def get_order(self, order_id: UUID, *, lock: bool = False) -> Order | None: ...

    async def list_orders(
        self,
        *,
        customer_user_id: UUID | None,
        guest_session_id: UUID | None,
        staff_local: bool,
        staff_all: bool,
    ) -> list[Order]: ...

    async def decide_order(
        self, order_id: UUID, *, approved: bool, actor_id: UUID, table_verified: bool
    ) -> Order: ...
