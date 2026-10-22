"""Framework-free M07 fulfillment and composed tracking snapshots."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class FulfillmentKind(StrEnum):
    SERVED = "SERVED"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"


@dataclass(frozen=True, slots=True)
class Fulfillment:
    id: UUID
    order_id: UUID
    kind: FulfillmentKind
    recorded_by_user_id: UUID
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class OrderTracking:
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
