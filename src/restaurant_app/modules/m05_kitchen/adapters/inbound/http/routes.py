"""M05 endpoints for existing confirmed-order kitchen tickets."""

from uuid import UUID

from fastapi import APIRouter

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m05_kitchen.adapters.inbound.http.dependencies import (
    KitchenPrincipal,
    kitchen_handler,
)
from restaurant_app.modules.m05_kitchen.adapters.inbound.http.schemas import (
    KitchenTicketResponse,
    ReadyRequest,
)
from restaurant_app.modules.m05_kitchen.application.use_cases.manage_tickets import KitchenModality

router = APIRouter(prefix="/kitchen/tickets", tags=["M05 kitchen"])


@router.get("", response_model=list[KitchenTicketResponse])
async def list_kitchen_tickets(
    actor: KitchenPrincipal, session: DatabaseSession, modality: KitchenModality | None = None
) -> list[KitchenTicketResponse]:
    views = await kitchen_handler(session).list_tickets(actor=actor, modality=modality)
    return [KitchenTicketResponse.from_view(view) for view in views]


@router.get("/{ticket_id}", response_model=KitchenTicketResponse)
async def get_kitchen_ticket(
    ticket_id: UUID, actor: KitchenPrincipal, session: DatabaseSession
) -> KitchenTicketResponse:
    view = await kitchen_handler(session).get_ticket(actor=actor, ticket_id=ticket_id)
    return KitchenTicketResponse.from_view(view)


@router.post("/{ticket_id}/start", response_model=KitchenTicketResponse)
async def start_kitchen_ticket(
    ticket_id: UUID, actor: KitchenPrincipal, session: DatabaseSession
) -> KitchenTicketResponse:
    view = await kitchen_handler(session).start(actor=actor, ticket_id=ticket_id)
    return KitchenTicketResponse.from_view(view)


@router.post("/{ticket_id}/ready", response_model=KitchenTicketResponse)
async def mark_kitchen_ticket_ready(
    ticket_id: UUID, body: ReadyRequest, actor: KitchenPrincipal, session: DatabaseSession
) -> KitchenTicketResponse:
    view = await kitchen_handler(session).mark_ready(
        actor=actor, ticket_id=ticket_id, all_items_prepared=body.all_items_prepared
    )
    return KitchenTicketResponse.from_view(view)
