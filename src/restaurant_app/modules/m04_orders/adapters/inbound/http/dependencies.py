"""M04 HTTP composition and cross-module public read contracts."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m01_access.public import (
    AuthorizeRoles,
    CurrentPrincipal,
    Principal,
    RoleCode,
)
from restaurant_app.modules.m02_catalog_stock.public import (
    ProductQuoteReader,
    SqlAlchemyStockConfirmer,
)
from restaurant_app.modules.m03_tables.public import TableLookup, TableOccupancy
from restaurant_app.modules.m04_orders.adapters.outbound import SqlAlchemyOrderRepository
from restaurant_app.modules.m04_orders.application.use_cases.confirm_order import ConfirmOrder
from restaurant_app.modules.m04_orders.application.use_cases.create_order import CreateOrder
from restaurant_app.modules.m04_orders.application.use_cases.create_waiter_order import (
    CreateWaiterOrder,
)
from restaurant_app.modules.m04_orders.domain.entities import ProductQuote, TableAvailability
from restaurant_app.modules.m05_kitchen.public import SqlAlchemyTicketIssuer
from restaurant_app.modules.m06_payments.public import SqlAlchemyAdvanceReader


class OrderProductReader:
    def __init__(self, session: AsyncSession) -> None:
        self._products = ProductQuoteReader(session)

    async def get_product(self, product_id: UUID) -> ProductQuote | None:
        product = await self._products.get_product(product_id)
        return (
            None
            if product is None
            else ProductQuote(
                id=product.id,
                name=product.name,
                price=product.price,
                is_available=product.is_available,
            )
        )


class OrderTableReader:
    def __init__(self, session: AsyncSession) -> None:
        self._tables = TableLookup(session)

    async def get_table(self, table_id: UUID) -> TableAvailability | None:
        # Share-lock the selection through request commit, coordinating with M03 occupancy writes.
        table = await self._tables.get_table(table_id, lock=True)
        return (
            None
            if table is None
            else TableAvailability(table.id, table.is_occupied, table.occupancy_started_at)
        )


class OrderTableOccupancy:
    def __init__(self, session: AsyncSession) -> None:
        self._tables = TableOccupancy(session)

    async def lock_table(self, table_id: UUID) -> TableAvailability | None:
        table = await self._tables.lock_table(table_id)
        return (
            None
            if table is None
            else TableAvailability(table.id, table.is_occupied, table.occupancy_started_at)
        )

    async def occupy(self, table_id: UUID, *, actor_id: UUID) -> TableAvailability:
        table = await self._tables.occupy(table_id, actor_id=actor_id)
        return TableAvailability(table.id, table.is_occupied, table.occupancy_started_at)


def create_order_handler(session: AsyncSession) -> CreateOrder:
    return CreateOrder(
        SqlAlchemyOrderRepository(session),
        OrderProductReader(session),
        OrderTableReader(session),
        OrderTableOccupancy(session),
    )


def confirm_order_handler(session: AsyncSession) -> ConfirmOrder:
    return ConfirmOrder(
        SqlAlchemyOrderRepository(session),
        OrderTableReader(session),
        SqlAlchemyStockConfirmer(session),
        SqlAlchemyAdvanceReader(session),
        SqlAlchemyTicketIssuer(session),
    )


def create_waiter_order_handler(session: AsyncSession) -> CreateWaiterOrder:
    return CreateWaiterOrder(create_order_handler(session), confirm_order_handler(session))


async def require_order_admin(principal: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.ADMIN)(principal)
    return principal


OrderAdmin = Annotated[Principal, Depends(require_order_admin)]


async def require_order_reviewer(principal: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)(principal)
    return principal


OrderReviewer = Annotated[Principal, Depends(require_order_reviewer)]


async def require_order_waiter(principal: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.WAITER)(principal)
    return principal


OrderWaiter = Annotated[Principal, Depends(require_order_waiter)]
