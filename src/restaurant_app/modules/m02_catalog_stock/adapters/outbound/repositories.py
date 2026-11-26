"""SQLAlchemy Async implementation of M02 catalog and stock persistence."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
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
    StaleStockQuantityError,
)


class SqlAlchemyCatalogRepository:
    """Use the request-owned transaction for all writes, including stock audit rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _category(model: CategoryModel) -> Category:
        return Category(id=model.id, name=model.name, is_active=model.is_active, sort_order=model.sort_order)

    @staticmethod
    def _product(model: ProductModel) -> Product:
        return Product(
            id=model.id,
            category_id=model.category_id,
            name=model.name,
            price=model.price,
            stock_qty=model.stock_qty,
            minimum_stock=model.minimum_stock,
            is_available=model.is_available,
            image_url=model.image_url,
            description=model.description,
        )

    async def list_categories(self, *, active_only: bool = True) -> list[Category]:
        statement = select(CategoryModel).order_by(CategoryModel.sort_order, CategoryModel.name, CategoryModel.id)
        if active_only:
            statement = statement.where(CategoryModel.is_active.is_(True))
        return [self._category(row) for row in (await self._session.scalars(statement)).all()]

    async def get_category(self, category_id: UUID) -> Category | None:
        model = await self._session.get(CategoryModel, category_id)
        return None if model is None else self._category(model)

    async def _check_category_name(self, name: str, *, omit_id: UUID | None = None) -> None:
        await self._session.execute(text("SELECT pg_advisory_xact_lock(202, 1)"))
        duplicate = select(CategoryModel.id).where(func.lower(CategoryModel.name) == func.lower(name))
        if omit_id is not None:
            duplicate = duplicate.where(CategoryModel.id != omit_id)
        if await self._session.scalar(duplicate.limit(1)) is not None:
            raise CategoryNameConflictError

    async def update_category_settings(self, category_id: UUID, *, is_active: bool, sort_order: int) -> Category:
        model = await self._session.get(CategoryModel, category_id)
        if model is None:
            raise CategoryNotFoundError
        model.is_active = is_active
        model.sort_order = sort_order
        await self._session.flush()
        return self._category(model)

    async def create_category(self, name: str) -> Category:
        await self._check_category_name(name)
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
        await self._check_category_name(name, omit_id=category_id)
        model.name = name
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise CategoryNameConflictError from error
        return self._category(model)

    async def list_products(self, category_id: UUID) -> list[Product]:
        statement = (
            select(ProductModel)
            .join(CategoryModel, CategoryModel.id == ProductModel.category_id)
            .where(ProductModel.category_id == category_id, CategoryModel.is_active.is_(True))
            .order_by(ProductModel.name, ProductModel.id)
        )
        return [self._product(row) for row in (await self._session.scalars(statement)).all()]

    async def list_all_products(self, *, active_only: bool = True) -> list[Product]:
        statement = select(ProductModel).order_by(ProductModel.name, ProductModel.id)
        if active_only:
            statement = statement.join(CategoryModel, CategoryModel.id == ProductModel.category_id).where(CategoryModel.is_active.is_(True))
        return [self._product(row) for row in (await self._session.scalars(statement)).all()]

    async def list_stock_movements(self, limit: int = 100, *, offset: int = 0, product_id: UUID | None = None, kind: str | None = None) -> list[dict[str, object]]:
        statement = (
            select(StockMovementModel, ProductModel.name)
            .join(ProductModel, ProductModel.id == StockMovementModel.product_id)
            .order_by(StockMovementModel.recorded_at.desc(), StockMovementModel.id.desc())
            .limit(limit).offset(offset)
        )
        if product_id is not None:
            statement = statement.where(StockMovementModel.product_id == product_id)
        if kind is not None:
            statement = statement.where(StockMovementModel.kind == kind)
        rows = (await self._session.execute(statement)).all()
        return [
            {
                "id": str(m.id),
                "product_id": str(m.product_id),
                "product_name": name,
                "kind": m.kind,
                "quantity_delta": m.quantity_delta,
                "reason": m.reason,
                "recorded_at": m.recorded_at.isoformat(),
                "actor_user_id": str(m.actor_user_id) if m.actor_user_id else None,
            }
            for m, name in rows
        ]

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

    async def set_stock(self, product_id: UUID, *, quantity: int, actor_id: UUID, reason: str | None = None, minimum_stock: int | None = None, expected_quantity: int | None = None) -> Product:
        statement = select(ProductModel).where(ProductModel.id == product_id).with_for_update()
        model = (await self._session.scalars(statement)).one_or_none()
        if model is None:
            raise ProductNotFoundError
        if expected_quantity is not None and model.stock_qty != expected_quantity:
            raise StaleStockQuantityError("El stock cambió. Actualiza las existencias y vuelve a ajustar")
        if minimum_stock is not None:
            model.minimum_stock = minimum_stock
        delta = quantity - model.stock_qty
        if delta:
            model.stock_qty = quantity
            self._session.add(
                StockMovementModel(
                    product_id=product_id,
                    kind="MANUAL",
                    reason=reason,
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
