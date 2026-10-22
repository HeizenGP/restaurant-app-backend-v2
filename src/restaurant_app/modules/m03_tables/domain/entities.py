"""Framework-independent table state for the single restaurant."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RestaurantTable:
    id: UUID
    code: str
    area_label: str | None
    is_occupied: bool
    updated_at: datetime
    updated_by_user_id: UUID | None
