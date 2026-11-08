"""Framework-free M04 request snapshots and state."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class Modality(StrEnum):
    LOCAL = "LOCAL"
    PICKUP = "PICKUP"
    DELIVERY = "DELIVERY"


class Channel(StrEnum):
    APP = "APP"
    WAITER = "WAITER"
    PHONE = "PHONE"
    WHATSAPP = "WHATSAPP"


class OrderStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONFIRMED = "CONFIRMED"


@dataclass(frozen=True, slots=True)
class RequestedItem:
    product_id: UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class ProductQuote:
    id: UUID
    name: str
    price: Decimal
    is_available: bool


@dataclass(frozen=True, slots=True)
class TableAvailability:
    id: UUID
    is_occupied: bool
    occupancy_started_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class OrderLine:
    product_id: UUID
    product_name_snapshot: str
    quantity: int
    unit_price_snapshot: Decimal
    id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Order:
    id: UUID
    modality: Modality
    channel: Channel
    status: str
    customer_user_id: UUID | None
    guest_session_id: UUID | None
    created_by_user_id: UUID | None
    table_id: UUID | None
    delivery_address: str | None
    contact_name: str | None
    contact_phone: str | None
    total_amount: Decimal
    lines: tuple[OrderLine, ...]
    created_at: datetime
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    table_verified_at: datetime | None
    table_account_id: UUID | None = None
