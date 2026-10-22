"""List, inspect and transition already-created kitchen tickets."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m04_orders.public import KitchenOrderLine, KitchenOrderReader
from restaurant_app.modules.m05_kitchen.application.ports.kitchen_repository import (
    KitchenRepository,
)
from restaurant_app.modules.m05_kitchen.domain.entities import KitchenStatus, KitchenTicket
from restaurant_app.modules.m05_kitchen.domain.errors import (
    KitchenTicketNotFound,
    KitchenTransitionConflict,
)

KitchenModality = Literal["LOCAL", "PICKUP", "DELIVERY"]


@dataclass(frozen=True, slots=True)
class KitchenTicketView:
    ticket: KitchenTicket
    modality: str
    lines: tuple[KitchenOrderLine, ...]


class ManageKitchenTickets:
    def __init__(self, tickets: KitchenRepository, orders: KitchenOrderReader) -> None:
        self._tickets = tickets
        self._orders = orders
        self._authorize = AuthorizeRoles(RoleCode.KITCHEN)

    async def list_tickets(
        self, *, actor: Principal, modality: KitchenModality | None = None
    ) -> list[KitchenTicketView]:
        self._authorize(actor)
        tickets = await self._tickets.list_tickets()
        orders = await self._orders.get_confirmed_orders([ticket.order_id for ticket in tickets])
        return [
            KitchenTicketView(
                ticket, orders[ticket.order_id].modality, orders[ticket.order_id].lines
            )
            for ticket in tickets
            if ticket.order_id in orders
            and (modality is None or orders[ticket.order_id].modality == modality)
        ]

    async def get_ticket(self, *, actor: Principal, ticket_id: UUID) -> KitchenTicketView:
        self._authorize(actor)
        ticket = await self._tickets.get_ticket(ticket_id)
        if ticket is None:
            raise KitchenTicketNotFound
        return await self._visible(ticket)

    async def start(self, *, actor: Principal, ticket_id: UUID) -> KitchenTicketView:
        self._authorize(actor)
        assert actor.user_id is not None
        ticket = await self._tickets.get_ticket(ticket_id, lock=True)
        if ticket is None:
            raise KitchenTicketNotFound
        await self._visible(ticket)
        if ticket.status is KitchenStatus.READY:
            raise KitchenTransitionConflict("A ready ticket cannot return to preparation")
        if ticket.status is KitchenStatus.RECEIVED:
            ticket = await self._tickets.start(ticket_id, actor_id=actor.user_id)
        return await self._visible(ticket)

    async def mark_ready(
        self, *, actor: Principal, ticket_id: UUID, all_items_prepared: bool
    ) -> KitchenTicketView:
        self._authorize(actor)
        assert actor.user_id is not None
        ticket = await self._tickets.get_ticket(ticket_id, lock=True)
        if ticket is None:
            raise KitchenTicketNotFound
        await self._visible(ticket)
        if ticket.status is KitchenStatus.RECEIVED:
            raise KitchenTransitionConflict("Start preparation before marking ready")
        if not all_items_prepared:
            raise KitchenTransitionConflict("Every product must be declared prepared")
        if ticket.status is KitchenStatus.PREPARING:
            ticket = await self._tickets.mark_ready(ticket_id, actor_id=actor.user_id)
        return await self._visible(ticket)

    async def _visible(self, ticket: KitchenTicket) -> KitchenTicketView:
        orders = await self._orders.get_confirmed_orders([ticket.order_id])
        order = orders.get(ticket.order_id)
        if order is None or not order.lines:
            raise KitchenTicketNotFound
        return KitchenTicketView(ticket, order.modality, order.lines)
