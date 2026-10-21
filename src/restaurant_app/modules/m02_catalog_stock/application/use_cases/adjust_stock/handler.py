"""Set absolute stock and audit the actual delta (RF-M02-03, RNF-09)."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m02_catalog_stock.application.ports.catalog_repository import (
    CatalogRepository,
)
from restaurant_app.modules.m02_catalog_stock.domain.entities import Product
from restaurant_app.modules.m02_catalog_stock.domain.errors import InvalidCatalogValueError


class AdjustStock:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog
        self._authorize = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(self, *, actor: Principal, product_id: UUID, quantity: int) -> Product:
        self._authorize(actor)
        if quantity < 0 or quantity > 2_147_483_647:
            raise InvalidCatalogValueError("Stock must be a nonnegative 32-bit integer")
        assert actor.user_id is not None
        return await self._catalog.set_stock(product_id, quantity=quantity, actor_id=actor.user_id)
