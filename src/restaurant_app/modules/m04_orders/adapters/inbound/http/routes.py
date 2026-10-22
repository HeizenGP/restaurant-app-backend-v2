"""M04 registration, review and ownership reads; no confirmation routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, status

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.public import CurrentPrincipal
from restaurant_app.modules.m04_orders.adapters.inbound.http.dependencies import (
    OrderAdmin,
    OrderReviewer,
    create_order_handler,
)
from restaurant_app.modules.m04_orders.adapters.inbound.http.schemas import (
    DecisionRequest,
    ManualOrderCreateRequest,
    OrderCreateRequest,
    OrderResponse,
)
from restaurant_app.modules.m04_orders.adapters.outbound import SqlAlchemyOrderRepository
from restaurant_app.modules.m04_orders.application.use_cases.decide_order import DecideOrder
from restaurant_app.modules.m04_orders.application.use_cases.get_order import GetOrder, ListOrders
from restaurant_app.modules.m04_orders.domain.entities import Channel

router = APIRouter(prefix="/orders", tags=["M04 requests"])
RequestKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_app_request(
    payload: OrderCreateRequest,
    request_key: RequestKey,
    actor: CurrentPrincipal,
    session: DatabaseSession,
) -> OrderResponse:
    order = await create_order_handler(session)(
        actor=actor,
        request_key=request_key,
        modality=payload.modality,
        channel=Channel.APP,
        items=tuple(item.to_domain() for item in payload.items),
        table_id=payload.table_id,
        delivery_address=payload.delivery_address,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
    )
    return OrderResponse.from_domain(order)


@router.post("/manual", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_request(
    payload: ManualOrderCreateRequest,
    request_key: RequestKey,
    actor: OrderAdmin,
    session: DatabaseSession,
) -> OrderResponse:
    order = await create_order_handler(session)(
        actor=actor,
        request_key=request_key,
        modality=payload.modality,
        channel=payload.channel,
        items=tuple(item.to_domain() for item in payload.items),
        table_id=payload.table_id,
        delivery_address=payload.delivery_address,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
    )
    return OrderResponse.from_domain(order)


@router.get("", response_model=list[OrderResponse])
async def list_requests(actor: CurrentPrincipal, session: DatabaseSession) -> list[OrderResponse]:
    orders = await ListOrders(SqlAlchemyOrderRepository(session))(actor=actor)
    return [OrderResponse.from_domain(order) for order in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_request(
    order_id: UUID, actor: CurrentPrincipal, session: DatabaseSession
) -> OrderResponse:
    order = await GetOrder(SqlAlchemyOrderRepository(session))(actor=actor, order_id=order_id)
    return OrderResponse.from_domain(order)


@router.post("/{order_id}/decision", response_model=OrderResponse)
async def decide_request(
    order_id: UUID,
    payload: DecisionRequest,
    actor: OrderReviewer,
    session: DatabaseSession,
) -> OrderResponse:
    order = await DecideOrder(SqlAlchemyOrderRepository(session))(
        actor=actor,
        order_id=order_id,
        approved=payload.approved,
        table_verified=payload.table_verified,
    )
    return OrderResponse.from_domain(order)
