"""Pure kitchen-ticket state and audit snapshot."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class KitchenStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PREPARING = "PREPARING"
    READY = "READY"


@dataclass(frozen=True, slots=True)
class KitchenTicket:
    id: UUID
    order_id: UUID
    status: KitchenStatus
    created_at: datetime
    started_at: datetime | None
    ready_at: datetime | None
    started_by_user_id: UUID | None
    ready_by_user_id: UUID | None
