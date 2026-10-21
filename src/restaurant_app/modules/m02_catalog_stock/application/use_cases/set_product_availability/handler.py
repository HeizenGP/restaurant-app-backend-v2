"""Enable or disable product sales independently of stock (RF-M02-04)."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m02_catalog_stock.application.ports.catalog_repository import (
    CatalogRepository,
)
from restaurant_app.modules.m02_catalog_stock.domain.entities import Product


class SetProductAvailability:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog
        self._authorize = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(self, *, actor: Principal, product_id: UUID, is_available: bool) -> Product:
        self._authorize(actor)
        return await self._catalog.set_availability(product_id, is_available=is_available)
