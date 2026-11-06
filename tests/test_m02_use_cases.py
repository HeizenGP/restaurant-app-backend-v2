"""Isolated handler coverage for RF-M02-01..04 and admin authorization."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError
from restaurant_app.modules.m02_catalog_stock.application.use_cases.adjust_stock import AdjustStock
from restaurant_app.modules.m02_catalog_stock.application.use_cases.list_catalog import (
    ListCategories,
    ListProducts,
)
from restaurant_app.modules.m02_catalog_stock.application.use_cases.save_category import (
    SaveCategory,
)
from restaurant_app.modules.m02_catalog_stock.application.use_cases.save_product import SaveProduct
from restaurant_app.modules.m02_catalog_stock.application.use_cases.set_product_availability import (
    SetProductAvailability,
)
from restaurant_app.modules.m02_catalog_stock.domain.entities import Category, Product
from restaurant_app.modules.m02_catalog_stock.domain.errors import (
    CategoryNotFoundError,
    InvalidCatalogValueError,
)


def principal(*roles: RoleCode) -> Principal:
    return Principal(
        user_id=uuid4(),
        session_id=uuid4(),
        roles=frozenset(roles),
        kind=SessionKind.USER,
    )


def catalog() -> SimpleNamespace:
    return SimpleNamespace(
        list_categories=AsyncMock(),
        get_category=AsyncMock(),
        create_category=AsyncMock(),
        rename_category=AsyncMock(),
        list_products=AsyncMock(),
        get_product=AsyncMock(),
        create_product=AsyncMock(),
        update_product=AsyncMock(),
        set_stock=AsyncMock(),
        set_availability=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_public_catalog_reads_category_products_and_missing_category() -> None:
    repository = catalog()
    category = Category(id=uuid4(), name="Arroces")
    product = Product(
        id=uuid4(),
        category_id=category.id,
        name="Arroz chaufa",
        price=Decimal("22.50"),
        stock_qty=8,
        is_available=True,
    )
    repository.list_categories.return_value = [category]
    repository.get_category.return_value = category
    repository.list_products.return_value = [product]

    assert await ListCategories(repository)() == [category]
    assert await ListProducts(repository)(category.id) == [product]
    repository.get_category.return_value = None
    with pytest.raises(CategoryNotFoundError):
        await ListProducts(repository)(uuid4())


@pytest.mark.asyncio
async def test_category_writes_require_admin_and_validate_name() -> None:
    repository = catalog()
    actor = principal(RoleCode.ADMIN)
    repository.create_category.return_value = Category(id=uuid4(), name="Bebidas")
    handler = SaveCategory(repository)

    with pytest.raises(AuthorizationError):
        await handler(actor=principal(RoleCode.CUSTOMER), name="Bebidas")
    repository.create_category.assert_not_awaited()
    with pytest.raises(InvalidCatalogValueError):
        await handler(actor=actor, name="  ")
    created = await handler(actor=actor, name=" Bebidas ")
    assert created.name == "Bebidas"
    repository.create_category.assert_awaited_once_with("Bebidas")
    await handler(actor=actor, name="Refrescos", category_id=created.id)
    repository.rename_category.assert_awaited_once_with(created.id, "Refrescos")


@pytest.mark.asyncio
async def test_product_write_rules_and_super_admin_bypass() -> None:
    repository = catalog()
    category = Category(id=uuid4(), name="Platos")
    repository.get_category.return_value = category
    repository.create_product.return_value = Product(
        id=uuid4(),
        category_id=category.id,
        name="Chaufa",
        price=Decimal("18.50"),
        stock_qty=0,
        is_available=True,
    )
    handler = SaveProduct(repository)
    with pytest.raises(AuthorizationError):
        await handler(
            actor=principal(RoleCode.CASHIER),
            category_id=category.id,
            name="Chaufa",
            price=Decimal("18.50"),
        )
    with pytest.raises(InvalidCatalogValueError):
        await handler(
            actor=principal(RoleCode.ADMIN),
            category_id=category.id,
            name="Chaufa",
            price=Decimal("18.501"),
        )
    repository.get_category.return_value = None
    with pytest.raises(CategoryNotFoundError):
        await handler(
            actor=principal(RoleCode.ADMIN),
            category_id=category.id,
            name="Chaufa",
            price=Decimal("18.50"),
        )
    repository.get_category.return_value = category
    result = await handler(
        actor=principal(RoleCode.SUPER_ADMIN),
        category_id=category.id,
        name=" Chaufa ",
        price=Decimal("18.50"),
    )
    assert result.name == "Chaufa"
    repository.create_product.assert_awaited_once_with(
        category_id=category.id, name="Chaufa", price=Decimal("18.50")
    )
    await handler(
        actor=principal(RoleCode.ADMIN),
        product_id=result.id,
        category_id=None,
        name=None,
        price=Decimal("20.00"),
    )
    repository.update_product.assert_awaited_once_with(
        result.id, category_id=None, name=None, price=Decimal("20.00")
    )


@pytest.mark.asyncio
async def test_stock_and_availability_require_admin_and_preserve_actor() -> None:
    repository = catalog()
    product_id = uuid4()
    admin = principal(RoleCode.ADMIN)
    with pytest.raises(AuthorizationError):
        await AdjustStock(repository)(
            actor=principal(RoleCode.CUSTOMER), product_id=product_id, quantity=12
        )
    with pytest.raises(InvalidCatalogValueError):
        await AdjustStock(repository)(actor=admin, product_id=product_id, quantity=-1)
    await AdjustStock(repository)(actor=admin, product_id=product_id, quantity=12)
    repository.set_stock.assert_awaited_once_with(product_id, quantity=12, actor_id=admin.user_id)
    with pytest.raises(AuthorizationError):
        await SetProductAvailability(repository)(
            actor=principal(RoleCode.CASHIER), product_id=product_id, is_available=False
        )
    await SetProductAvailability(repository)(actor=admin, product_id=product_id, is_available=False)
    repository.set_availability.assert_awaited_once_with(product_id, is_available=False)


@pytest.mark.asyncio
async def test_seed_initial_catalog_executes_idempotent_queries() -> None:
    from unittest.mock import MagicMock

    from restaurant_app.modules.m02_catalog_stock.seed import seed_initial_catalog

    mock_session = AsyncMock()
    mock_session.begin = MagicMock()
    mock_session.begin.return_value.__aenter__ = AsyncMock()
    mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_factory = MagicMock(return_value=mock_session)
    await seed_initial_catalog(mock_factory)

    assert mock_session.execute.await_count == 2
