"""Read-only product quotes exported to order-registration slices."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m02_catalog_stock.adapters.outbound.models import ProductModel
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
