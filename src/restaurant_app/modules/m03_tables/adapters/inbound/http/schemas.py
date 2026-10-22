"""REST contracts for the M03 distribution and occupancy slice."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from restaurant_app.modules.m03_tables.domain.entities import RestaurantTable


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TableCreateRequest(StrictRequest):
    code: str = Field(min_length=1, max_length=24)
    area_label: str | None = Field(default=None, min_length=1, max_length=80)


class TablePatchRequest(StrictRequest):
    code: str | None = Field(default=None, min_length=1, max_length=24)
    area_label: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set or (
            self.code is None and "area_label" not in self.model_fields_set
        ):
            raise ValueError("at least one table field is required")
        return self


class TableOccupancyRequest(StrictRequest):
    is_occupied: StrictBool


class PublicTableResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    code: str
    area_label: str | None
    is_occupied: bool

    @classmethod
    def from_domain(cls, table: RestaurantTable) -> Self:
        return cls(
            id=table.id,
            code=table.code,
            area_label=table.area_label,
            is_occupied=table.is_occupied,
        )


class StaffTableResponse(PublicTableResponse):
    updated_at: datetime
    updated_by_user_id: UUID | None

    @classmethod
    def from_domain(cls, table: RestaurantTable) -> Self:
        return cls(
            id=table.id,
            code=table.code,
            area_label=table.area_label,
            is_occupied=table.is_occupied,
            updated_at=table.updated_at,
            updated_by_user_id=table.updated_by_user_id,
        )
