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

    async def __call__(self, *, actor: Principal, product_id: UUID, quantity: int, reason: str | None = None, minimum_stock: int | None = None, expected_quantity: int | None = None) -> Product:
        self._authorize(actor)
        if quantity < 0 or quantity > 2_147_483_647:
            raise InvalidCatalogValueError("Stock must be a nonnegative 32-bit integer")
        assert actor.user_id is not None
        if reason is None and minimum_stock is None and expected_quantity is None:
            return await self._catalog.set_stock(product_id, quantity=quantity, actor_id=actor.user_id)
        if reason is None or not reason.strip() or len(reason) > 300:
            raise InvalidCatalogValueError("Ingresa un motivo de ajuste válido")
        if minimum_stock is not None and not 0 <= minimum_stock <= 2_147_483_647:
            raise InvalidCatalogValueError("El mínimo debe ser un entero no negativo")
        return await self._catalog.set_stock(
            product_id, quantity=quantity, actor_id=actor.user_id, reason=reason.strip(), minimum_stock=minimum_stock, expected_quantity=expected_quantity,
        )
