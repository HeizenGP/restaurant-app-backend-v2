"""Public product quotes and atomic stock debit for order confirmation."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m02_catalog_stock.adapters.outbound.models import (
    ProductModel,
    StockMovementModel,
)
from restaurant_app.modules.m02_catalog_stock.domain.entities import Product


class ProductQuoteReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_product(self, product_id: UUID) -> Product | None:
        model = (
            await self._session.scalars(
                select(ProductModel).where(ProductModel.id == product_id).with_for_update(read=True)
            )
        ).one_or_none()
        return (
            None
            if model is None
            else Product(
                id=model.id,
                category_id=model.category_id,
                name=model.name,
                price=model.price,
                stock_qty=model.stock_qty,
                is_available=model.is_available,
            )
        )


@dataclass(frozen=True, slots=True)
class StockAllocation:
    order_item_id: UUID
    product_id: UUID
    quantity: int


class StockConfirmationError(Exception):
    """A current product state cannot satisfy the immutable order lines."""


class StockConfirmer(Protocol):
    async def debit_order(
        self, allocations: tuple[StockAllocation, ...], *, actor_id: UUID
    ) -> None: ...


class SqlAlchemyStockConfirmer:
    """Lock all product rows in stable order, then debit and audit each line."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def debit_order(
        self, allocations: tuple[StockAllocation, ...], *, actor_id: UUID
    ) -> None:
        if not allocations or len({line.product_id for line in allocations}) != len(allocations):
            raise StockConfirmationError("Order lines must be unique and nonempty")
        ordered = sorted(allocations, key=lambda line: line.product_id)
        products: list[ProductModel] = []
        for line in ordered:
            if line.quantity <= 0:
                raise StockConfirmationError("Order quantity must be positive")
            model = (
                await self._session.scalars(
                    select(ProductModel)
                    .where(ProductModel.id == line.product_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).one_or_none()
            if model is None or not model.is_available or model.stock_qty < line.quantity:
                raise StockConfirmationError("Product is unavailable or has insufficient stock")
            products.append(model)
        for line, model in zip(ordered, products, strict=True):
            model.stock_qty -= line.quantity
            self._session.add(
                StockMovementModel(
                    product_id=line.product_id,
                    kind="ORDER",
                    quantity_delta=-line.quantity,
                    order_item_id=line.order_item_id,
                    actor_user_id=actor_id,
                )
            )
        await self._session.flush()
