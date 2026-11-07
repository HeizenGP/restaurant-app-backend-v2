"""Create or edit product details and price (RF-M02-02)."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m02_catalog_stock.application.ports.catalog_repository import (
    CatalogRepository,
)
from restaurant_app.modules.m02_catalog_stock.domain.entities import Product
from restaurant_app.modules.m02_catalog_stock.domain.errors import (
    CategoryNotFoundError,
    InvalidCatalogValueError,
)

MAX_PRICE = Decimal("10000000000")


class SaveProduct:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog
        self._authorize = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(
        self,
        *,
        actor: Principal,
        category_id: UUID | None,
        name: str | None,
        price: Decimal | None,
        product_id: UUID | None = None,
        image_url: str | None = None,
        description: str | None = None,
    ) -> Product:
        self._authorize(actor)
        if product_id is None and (category_id is None or name is None or price is None):
            raise InvalidCatalogValueError("Category, name and price are required")
        if (
            product_id is not None
            and category_id is None
            and name is None
            and price is None
            and image_url is None
            and description is None
        ):
            raise InvalidCatalogValueError("At least one product field is required")
        if category_id is not None and await self._catalog.get_category(category_id) is None:
            raise CategoryNotFoundError
        normalized_name = name.strip() if name is not None else None
        if normalized_name is not None and (not normalized_name or len(normalized_name) > 160):
            raise InvalidCatalogValueError("Product name must contain 1 to 160 characters")
        if price is not None and (
            not price.is_finite()
            or price < 0
            or price >= MAX_PRICE
            or price != price.quantize(Decimal("0.01"))
        ):
            raise InvalidCatalogValueError("Price must be nonnegative with at most two decimals")
        if product_id is None:
            assert category_id is not None and normalized_name is not None and price is not None
            create_kwargs: dict[str, Any] = {
                "category_id": category_id,
                "name": normalized_name,
                "price": price,
            }
            if image_url is not None:
                create_kwargs["image_url"] = image_url
            if description is not None:
                create_kwargs["description"] = description
            return await self._catalog.create_product(**create_kwargs)
        update_kwargs: dict[str, Any] = {
            "category_id": category_id,
            "name": normalized_name,
            "price": price,
        }
        if image_url is not None:
            update_kwargs["image_url"] = image_url
        if description is not None:
            update_kwargs["description"] = description
        return await self._catalog.update_product(product_id, **update_kwargs)
