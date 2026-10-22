"""REST responses for M07 service, handover, closure, and tracking."""

from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from restaurant_app.modules.m07_fulfillment.domain.entities import Fulfillment, OrderTracking


class FulfillmentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    order_id: UUID
    kind: str
    recorded_by_user_id: UUID
    recorded_at: datetime

    @classmethod
    def from_domain(cls, fulfillment: Fulfillment) -> Self:
        return cls(
            id=fulfillment.id,
            order_id=fulfillment.order_id,
            kind=fulfillment.kind.value,
            recorded_by_user_id=fulfillment.recorded_by_user_id,
            recorded_at=fulfillment.recorded_at,
        )


class TrackingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: UUID
    modality: str
    order_status: str
    stage: str
    kitchen_status: str | None
    fulfillment_kind: str | None
    total_amount: Decimal
    paid_amount: Decimal
    balance: Decimal
    payment_status: str
    created_at: datetime
    kitchen_started_at: datetime | None
    kitchen_ready_at: datetime | None
    fulfilled_at: datetime | None
    closed_at: datetime | None

    @classmethod
    def from_domain(cls, tracking: OrderTracking) -> Self:
        return cls(**{field: getattr(tracking, field) for field in cls.model_fields})
