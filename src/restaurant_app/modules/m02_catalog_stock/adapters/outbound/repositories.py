"""SQLAlchemy Async implementation of M02 catalog and stock persistence."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m02_catalog_stock.adapters.outbound.models import (
    CategoryModel,
    ProductModel,
    StockMovementModel,
)
from restaurant_app.modules.m02_catalog_stock.domain.entities import Category, Product
from restaurant_app.modules.m02_catalog_stock.domain.errors import (
    CategoryNameConflictError,
    CategoryNotFoundError,
    ProductNotFoundError,
)


class SqlAlchemyCatalogRepository:
    """Use the request-owned transaction for all writes, including stock audit rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _category(model: CategoryModel) -> Category:
        return Category(id=model.id, name=model.name)

    @staticmethod
    def _product(model: ProductModel) -> Product:
        return Product(
            id=model.id,
            category_id=model.category_id,
            name=model.name,
            price=model.price,
            stock_qty=model.stock_qty,
            is_available=model.is_available,
            image_url=model.image_url,
            description=model.description,
        )

    async def list_categories(self) -> list[Category]:
        statement = select(CategoryModel).order_by(CategoryModel.name, CategoryModel.id)
        return [self._category(row) for row in (await self._session.scalars(statement)).all()]

    async def get_category(self, category_id: UUID) -> Category | None:
        model = await self._session.get(CategoryModel, category_id)
        return None if model is None else self._category(model)

    async def create_category(self, name: str) -> Category:
        model = CategoryModel(name=name)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise CategoryNameConflictError from error
        return self._category(model)

    async def rename_category(self, category_id: UUID, name: str) -> Category:
        model = await self._session.get(CategoryModel, category_id)
        if model is None:
            raise CategoryNotFoundError
        model.name = name
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise CategoryNameConflictError from error
        return self._category(model)

    async def list_products(self, category_id: UUID) -> list[Product]:
        statement = (
            select(ProductModel)
            .where(ProductModel.category_id == category_id)
            .order_by(ProductModel.name, ProductModel.id)
        )
        return [self._product(row) for row in (await self._session.scalars(statement)).all()]

    async def get_product(self, product_id: UUID) -> Product | None:
        model = await self._session.get(ProductModel, product_id)
        return None if model is None else self._product(model)

    async def create_product(
        self,
        *,
        category_id: UUID,
        name: str,
        price: Decimal,
        image_url: str | None = None,
        description: str | None = None,
    ) -> Product:
        model = ProductModel(
            category_id=category_id,
            name=name,
            price=price,
            image_url=image_url,
            description=description,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._product(model)

    async def update_product(
        self,
        product_id: UUID,
        *,
        category_id: UUID | None = None,
        name: str | None = None,
        price: Decimal | None = None,
        image_url: str | None = None,
        description: str | None = None,
    ) -> Product:
        model = await self._session.get(ProductModel, product_id)
        if model is None:
            raise ProductNotFoundError
        if category_id is not None:
            model.category_id = category_id
        if name is not None:
            model.name = name
        if price is not None:
            model.price = price
        if image_url is not None:
            model.image_url = image_url
        if description is not None:
            model.description = description
        await self._session.flush()
        return self._product(model)

    async def set_stock(self, product_id: UUID, *, quantity: int, actor_id: UUID) -> Product:
        statement = select(ProductModel).where(ProductModel.id == product_id).with_for_update()
        model = (await self._session.scalars(statement)).one_or_none()
        if model is None:
            raise ProductNotFoundError
        delta = quantity - model.stock_qty
        if delta:
            model.stock_qty = quantity
            self._session.add(
                StockMovementModel(
                    product_id=product_id,
                    kind="MANUAL",
                    quantity_delta=delta,
                    order_item_id=None,
                    actor_user_id=actor_id,
                )
            )
            await self._session.flush()
        return self._product(model)

    async def set_availability(self, product_id: UUID, *, is_available: bool) -> Product:
        model = await self._session.get(ProductModel, product_id)
        if model is None:
            raise ProductNotFoundError
        model.is_available = is_available
        await self._session.flush()
        return self._product(model)
