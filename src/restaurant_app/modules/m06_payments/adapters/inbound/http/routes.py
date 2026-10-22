"""Quote and administratively verify a simulated 50% advance."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.public import CurrentPrincipal
from restaurant_app.modules.m06_payments.adapters.inbound.http.dependencies import (
    AdvanceAdmin,
    get_advance_handler,
    verify_advance_handler,
)
from restaurant_app.modules.m06_payments.adapters.inbound.http.schemas import (
    AdvanceSummaryResponse,
)

router = APIRouter(prefix="/orders", tags=["M06 advances"])
RequestKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


@router.get("/{order_id}/advance", response_model=AdvanceSummaryResponse)
async def get_order_advance(
    order_id: UUID, actor: CurrentPrincipal, session: DatabaseSession
) -> AdvanceSummaryResponse:
    summary = await get_advance_handler(session)(actor=actor, order_id=order_id)
    return AdvanceSummaryResponse.from_domain(summary)


@router.post("/{order_id}/advance/verify", response_model=AdvanceSummaryResponse)
async def verify_order_advance(
    order_id: UUID,
    request_key: RequestKey,
    actor: AdvanceAdmin,
    session: DatabaseSession,
) -> AdvanceSummaryResponse:
    summary = await verify_advance_handler(session)(
        actor=actor, order_id=order_id, request_key=request_key
    )
    return AdvanceSummaryResponse.from_domain(summary)
