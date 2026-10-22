"""Read-only quote and verification result; no general cashier API."""

from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from restaurant_app.modules.m06_payments.domain.entities import AdvanceSummary


class AdvanceSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: UUID
    order_status: str
    total_amount: Decimal
    required_amount: Decimal
    verified_amount: Decimal
    remaining_amount: Decimal
    verified_at: datetime | None

    @classmethod
    def from_domain(cls, summary: AdvanceSummary) -> Self:
        return cls(
            order_id=summary.order_id,
            order_status=summary.order_status,
            total_amount=summary.total_amount,
            required_amount=summary.required_amount,
            verified_amount=summary.verified_amount,
            remaining_amount=summary.remaining_amount,
            verified_at=summary.verified_at,
        )
