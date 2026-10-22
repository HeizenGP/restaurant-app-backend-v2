"""Compose M05 from public M04 reads and M05-owned persistence."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m01_access.public import (
    AuthorizeRoles,
    CurrentPrincipal,
    Principal,
    RoleCode,
)
from restaurant_app.modules.m04_orders.public import SqlAlchemyKitchenOrderReader
from restaurant_app.modules.m05_kitchen.adapters.outbound.repositories import (
    SqlAlchemyKitchenRepository,
)
from restaurant_app.modules.m05_kitchen.application.use_cases.manage_tickets import (
    ManageKitchenTickets,
)


def kitchen_handler(session: AsyncSession) -> ManageKitchenTickets:
    return ManageKitchenTickets(
        SqlAlchemyKitchenRepository(session), SqlAlchemyKitchenOrderReader(session)
    )


async def require_kitchen(actor: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.KITCHEN)(actor)
    return actor


KitchenPrincipal = Annotated[Principal, Depends(require_kitchen)]
