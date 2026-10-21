"""Create or rename a category (RF-M02-02)."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m02_catalog_stock.application.ports.catalog_repository import (
    CatalogRepository,
)
from restaurant_app.modules.m02_catalog_stock.domain.entities import Category
from restaurant_app.modules.m02_catalog_stock.domain.errors import InvalidCatalogValueError


class SaveCategory:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog
        self._authorize = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(
        self, *, actor: Principal, name: str, category_id: UUID | None = None
    ) -> Category:
        self._authorize(actor)
        normalized_name = name.strip()
        if not normalized_name or len(normalized_name) > 100:
            raise InvalidCatalogValueError("Category name must contain 1 to 100 characters")
        if category_id is None:
            return await self._catalog.create_category(normalized_name)
        return await self._catalog.rename_category(category_id, normalized_name)
