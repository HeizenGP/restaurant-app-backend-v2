"""Compose M07 use cases on the request-owned PostgreSQL session."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m01_access.public import (
    AuthorizeRoles,
    CurrentPrincipal,
    Principal,
    RoleCode,
)
from restaurant_app.modules.m04_orders.public import SqlAlchemyFulfillmentOrderReader
from restaurant_app.modules.m05_kitchen.public import SqlAlchemyKitchenProgressReader
from restaurant_app.modules.m06_payments.public import SqlAlchemyPaymentBalanceReader
from restaurant_app.modules.m07_fulfillment.adapters.outbound.repositories import (
    SqlAlchemyFulfillmentRepository,
)
from restaurant_app.modules.m07_fulfillment.application.use_cases.close_order import CloseOrder
from restaurant_app.modules.m07_fulfillment.application.use_cases.get_tracking import GetTracking
from restaurant_app.modules.m07_fulfillment.application.use_cases.record_fulfillment import (
    RecordFulfillment,
)
from restaurant_app.modules.m07_fulfillment.domain.entities import FulfillmentKind


async def require_service_waiter(actor: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.WAITER)(actor)
    return actor


async def require_fulfillment_admin(actor: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.ADMIN)(actor)
    return actor


ServiceWaiter = Annotated[Principal, Depends(require_service_waiter)]
FulfillmentAdmin = Annotated[Principal, Depends(require_fulfillment_admin)]


def record_fulfillment_handler(
    session: AsyncSession, *, kind: FulfillmentKind
) -> RecordFulfillment:
    modality, role = {
        FulfillmentKind.SERVED: ("LOCAL", RoleCode.WAITER),
        FulfillmentKind.PICKED_UP: ("PICKUP", RoleCode.ADMIN),
        FulfillmentKind.DELIVERED: ("DELIVERY", RoleCode.ADMIN),
    }[kind]
    return RecordFulfillment(
        SqlAlchemyFulfillmentOrderReader(session),
        SqlAlchemyKitchenProgressReader(session),
        SqlAlchemyFulfillmentRepository(session),
        kind=kind,
        modality=modality,
        role=role,
    )


def close_order_handler(session: AsyncSession) -> CloseOrder:
    return CloseOrder(
        SqlAlchemyFulfillmentOrderReader(session),
        SqlAlchemyKitchenProgressReader(session),
        SqlAlchemyPaymentBalanceReader(session),
        SqlAlchemyFulfillmentRepository(session),
    )


def get_tracking_handler(session: AsyncSession) -> GetTracking:
    return GetTracking(
        SqlAlchemyFulfillmentOrderReader(session),
        SqlAlchemyKitchenProgressReader(session),
        SqlAlchemyPaymentBalanceReader(session),
        SqlAlchemyFulfillmentRepository(session),
    )
