"""List categories and their products for customers and guests (RF-M02-01)."""

from uuid import UUID

from restaurant_app.modules.m02_catalog_stock.application.ports.catalog_repository import (
    CatalogRepository,
)
from restaurant_app.modules.m02_catalog_stock.domain.entities import Category, Product
from restaurant_app.modules.m02_catalog_stock.domain.errors import CategoryNotFoundError


class ListCategories:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    async def __call__(self) -> list[Category]:
        return await self._catalog.list_categories()


class ListProducts:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    async def __call__(self, category_id: UUID) -> list[Product]:
        if await self._catalog.get_category(category_id) is None:
            raise CategoryNotFoundError
        return await self._catalog.list_products(category_id)
