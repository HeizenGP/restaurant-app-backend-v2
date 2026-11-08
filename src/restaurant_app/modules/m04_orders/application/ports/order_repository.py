"""Ports consumed by request registration and decision handlers."""

from datetime import datetime
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


class TableOccupancy(Protocol):
    async def lock_table(self, table_id: UUID) -> TableAvailability | None: ...

    async def occupy(self, table_id: UUID, *, actor_id: UUID | None = None) -> TableAvailability: ...


class OrderRepository(Protocol):
    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> Order | None: ...

    async def has_verified_active_table_order(
        self,
        *,
        table_id: UUID,
        occupied_since: datetime,
        customer_user_id: UUID | None,
        guest_session_id: UUID | None,
    ) -> bool: ...

    async def has_conflicting_verified_table_owner(
        self,
        *,
        table_id: UUID,
        occupied_since: datetime,
        customer_user_id: UUID | None,
        guest_session_id: UUID | None,
    ) -> bool: ...

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
