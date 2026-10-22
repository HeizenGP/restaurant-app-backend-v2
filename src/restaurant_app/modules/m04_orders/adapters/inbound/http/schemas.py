"""Strict M04 request and immutable snapshot REST contracts."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from restaurant_app.modules.m04_orders.domain.entities import (
    Channel,
    Modality,
    Order,
    OrderLine,
    RequestedItem,
)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ItemRequest(StrictRequest):
    product_id: UUID
    quantity: int = Field(gt=0, le=2_147_483_647)

    def to_domain(self) -> RequestedItem:
        return RequestedItem(product_id=self.product_id, quantity=self.quantity)


class OrderCreateRequest(StrictRequest):
    modality: Modality
    items: list[ItemRequest] = Field(min_length=1, max_length=100)
    table_id: UUID | None = None
    delivery_address: str | None = Field(default=None, min_length=1, max_length=1000)
    contact_name: str | None = Field(default=None, min_length=1, max_length=120)
    contact_phone: str | None = Field(default=None, min_length=1, max_length=30)


class ManualOrderCreateRequest(OrderCreateRequest):
    channel: Literal[Channel.PHONE, Channel.WHATSAPP]


class DecisionRequest(StrictRequest):
    approved: bool
    table_verified: bool = False


class OrderLineResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID
    product_name_snapshot: str
    quantity: int
    unit_price_snapshot: Decimal

    @classmethod
    def from_domain(cls, line: OrderLine) -> Self:
        return cls(
            product_id=line.product_id,
            product_name_snapshot=line.product_name_snapshot,
            quantity=line.quantity,
            unit_price_snapshot=line.unit_price_snapshot,
        )


class OrderResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    modality: Modality
    channel: Channel
    status: str
    table_id: UUID | None
    delivery_address: str | None
    contact_name: str | None
    contact_phone: str | None
    total_amount: Decimal
    lines: list[OrderLineResponse]
    created_at: datetime
    decided_at: datetime | None
    table_verified_at: datetime | None

    @classmethod
    def from_domain(cls, order: Order) -> Self:
        return cls(
            id=order.id,
            modality=order.modality,
            channel=order.channel,
            status=order.status,
            table_id=order.table_id,
            delivery_address=order.delivery_address,
            contact_name=order.contact_name,
            contact_phone=order.contact_phone,
            total_amount=order.total_amount,
            lines=[OrderLineResponse.from_domain(line) for line in order.lines],
            created_at=order.created_at,
            decided_at=order.decided_at,
            table_verified_at=order.table_verified_at,
        )
