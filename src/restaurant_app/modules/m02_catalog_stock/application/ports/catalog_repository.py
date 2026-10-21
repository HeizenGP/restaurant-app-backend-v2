"""Persistence operations consumed by M02 use cases."""

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m02_catalog_stock.domain.entities import Category, Product


class CatalogRepository(Protocol):
    async def list_categories(self) -> list[Category]: ...

    async def get_category(self, category_id: UUID) -> Category | None: ...

    async def create_category(self, name: str) -> Category: ...

    async def rename_category(self, category_id: UUID, name: str) -> Category: ...

    async def list_products(self, category_id: UUID) -> list[Product]: ...

    async def get_product(self, product_id: UUID) -> Product | None: ...

    async def create_product(self, *, category_id: UUID, name: str, price: Decimal) -> Product: ...

    async def update_product(
        self,
        product_id: UUID,
        *,
        category_id: UUID | None,
        name: str | None,
        price: Decimal | None,
    ) -> Product: ...

    async def set_stock(self, product_id: UUID, *, quantity: int, actor_id: UUID) -> Product: ...

    async def set_availability(self, product_id: UUID, *, is_available: bool) -> Product: ...
