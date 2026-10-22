"""Persistence operations required by the M05 application."""

from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m05_kitchen.domain.entities import KitchenTicket


class KitchenRepository(Protocol):
    async def list_tickets(self) -> list[KitchenTicket]: ...

    async def get_ticket(self, ticket_id: UUID, *, lock: bool = False) -> KitchenTicket | None: ...

    async def start(self, ticket_id: UUID, *, actor_id: UUID) -> KitchenTicket: ...

    async def mark_ready(self, ticket_id: UUID, *, actor_id: UUID) -> KitchenTicket: ...
