"""Kitchen HTTP request and response models."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from restaurant_app.modules.m05_kitchen.application.use_cases.manage_tickets import (
    KitchenTicketView,
)
from restaurant_app.modules.m05_kitchen.domain.entities import KitchenStatus


class ReadyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    all_items_prepared: bool


class KitchenLineResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID
    product_name_snapshot: str
    quantity: int


class KitchenTicketResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    order_id: UUID
    modality: str
    status: KitchenStatus
    lines: list[KitchenLineResponse]
    created_at: datetime
    started_at: datetime | None
    ready_at: datetime | None
    started_by_user_id: UUID | None
    ready_by_user_id: UUID | None

    @classmethod
    def from_view(cls, view: KitchenTicketView) -> Self:
        ticket = view.ticket
        return cls(
            id=ticket.id,
            order_id=ticket.order_id,
            modality=view.modality,
            status=ticket.status,
            lines=[
                KitchenLineResponse(
                    product_id=line.product_id,
                    product_name_snapshot=line.product_name_snapshot,
                    quantity=line.quantity,
                )
                for line in view.lines
            ],
            created_at=ticket.created_at,
            started_at=ticket.started_at,
            ready_at=ticket.ready_at,
            started_by_user_id=ticket.started_by_user_id,
            ready_by_user_id=ticket.ready_by_user_id,
        )
