"""M07 service, handover, closure, and composed order-tracking routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.public import CurrentPrincipal
from restaurant_app.modules.m07_fulfillment.adapters.inbound.http.dependencies import (
    FulfillmentAdmin,
    ServiceWaiter,
    close_order_handler,
    get_tracking_handler,
    record_fulfillment_handler,
)
from restaurant_app.modules.m07_fulfillment.adapters.inbound.http.schemas import (
    FulfillmentResponse,
    TrackingResponse,
)
from restaurant_app.modules.m07_fulfillment.domain.entities import FulfillmentKind

router = APIRouter(prefix="/orders", tags=["M07 fulfillment"])
RequestKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


@router.post("/{order_id}/serve", response_model=FulfillmentResponse)
async def serve_order(
    order_id: UUID, request_key: RequestKey, actor: ServiceWaiter, session: DatabaseSession
) -> FulfillmentResponse:
    fulfillment = await record_fulfillment_handler(session, kind=FulfillmentKind.SERVED)(
        actor=actor, order_id=order_id, request_key=request_key
    )
    return FulfillmentResponse.from_domain(fulfillment)


@router.post("/{order_id}/pickup", response_model=FulfillmentResponse)
async def record_pickup(
    order_id: UUID, request_key: RequestKey, actor: FulfillmentAdmin, session: DatabaseSession
) -> FulfillmentResponse:
    fulfillment = await record_fulfillment_handler(session, kind=FulfillmentKind.PICKED_UP)(
        actor=actor, order_id=order_id, request_key=request_key
    )
    return FulfillmentResponse.from_domain(fulfillment)


@router.post("/{order_id}/deliver", response_model=FulfillmentResponse)
async def record_delivery(
    order_id: UUID, request_key: RequestKey, actor: FulfillmentAdmin, session: DatabaseSession
) -> FulfillmentResponse:
    fulfillment = await record_fulfillment_handler(session, kind=FulfillmentKind.DELIVERED)(
        actor=actor, order_id=order_id, request_key=request_key
    )
    return FulfillmentResponse.from_domain(fulfillment)


@router.post("/{order_id}/close", response_model=TrackingResponse)
async def close_order(
    order_id: UUID, request_key: RequestKey, actor: FulfillmentAdmin, session: DatabaseSession
) -> TrackingResponse:
    await close_order_handler(session)(actor=actor, order_id=order_id, request_key=request_key)
    tracking = await get_tracking_handler(session)(actor=actor, order_id=order_id)
    return TrackingResponse.from_domain(tracking)


@router.get("/{order_id}/tracking", response_model=TrackingResponse)
async def get_tracking(
    order_id: UUID, actor: CurrentPrincipal, session: DatabaseSession
) -> TrackingResponse:
    tracking = await get_tracking_handler(session)(actor=actor, order_id=order_id)
    return TrackingResponse.from_domain(tracking)
