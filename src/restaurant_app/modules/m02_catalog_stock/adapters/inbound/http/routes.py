"""REST endpoints for approved M02 RF-M02-01..04 only."""

from uuid import UUID

from fastapi import APIRouter, status

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m02_catalog_stock.adapters.inbound.http.dependencies import CatalogAdmin
from restaurant_app.modules.m02_catalog_stock.adapters.inbound.http.schemas import (
    AvailabilityRequest,
    CatalogProductResponse,
    CategoryRequest,
    CategoryResponse,
    ProductCreateRequest,
    ProductPatchRequest,
    ProductResponse,
    StockSetRequest,
)
from restaurant_app.modules.m02_catalog_stock.adapters.outbound import (
    SqlAlchemyCatalogRepository,
)
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

router = APIRouter(prefix="/catalog", tags=["M02 catalog"])


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(session: DatabaseSession) -> list[CategoryResponse]:
    categories = await ListCategories(SqlAlchemyCatalogRepository(session))()
    return [CategoryResponse.from_domain(category) for category in categories]


@router.get("/categories/{category_id}/products", response_model=list[CatalogProductResponse])
async def list_products(
    category_id: UUID, session: DatabaseSession
) -> list[CatalogProductResponse]:
    products = await ListProducts(SqlAlchemyCatalogRepository(session))(category_id)
    return [CatalogProductResponse.from_domain(product) for product in products]


@router.get("/products", response_model=list[CatalogProductResponse])
async def list_all_products(
    session: DatabaseSession, category_id: UUID | None = None
) -> list[CatalogProductResponse]:
    repo = SqlAlchemyCatalogRepository(session)
    if category_id is not None:
        products = await repo.list_products(category_id)
    else:
        products = await repo.list_all_products()
    return [CatalogProductResponse.from_domain(product) for product in products]


@router.get("/stock/movements")
async def list_stock_movements(
    actor: CatalogAdmin, session: DatabaseSession, limit: int = 100
) -> list[dict[str, object]]:
    return await SqlAlchemyCatalogRepository(session).list_stock_movements(limit=limit)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryRequest, actor: CatalogAdmin, session: DatabaseSession
) -> CategoryResponse:
    category = await SaveCategory(SqlAlchemyCatalogRepository(session))(
        actor=actor, name=payload.name
    )
    return CategoryResponse.from_domain(category)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
async def rename_category(
    category_id: UUID, payload: CategoryRequest, actor: CatalogAdmin, session: DatabaseSession
) -> CategoryResponse:
    category = await SaveCategory(SqlAlchemyCatalogRepository(session))(
        actor=actor, name=payload.name, category_id=category_id
    )
    return CategoryResponse.from_domain(category)


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest, actor: CatalogAdmin, session: DatabaseSession
) -> ProductResponse:
    product = await SaveProduct(SqlAlchemyCatalogRepository(session))(
        actor=actor,
        category_id=payload.category_id,
        name=payload.name,
        price=payload.price,
        image_url=payload.image_url,
        description=payload.description,
    )
    return ProductResponse.from_domain(product)


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID, payload: ProductPatchRequest, actor: CatalogAdmin, session: DatabaseSession
) -> ProductResponse:
    product = await SaveProduct(SqlAlchemyCatalogRepository(session))(
        actor=actor,
        product_id=product_id,
        category_id=payload.category_id,
        name=payload.name,
        price=payload.price,
        image_url=payload.image_url,
        description=payload.description,
    )
    return ProductResponse.from_domain(product)


@router.put("/products/{product_id}/stock", response_model=ProductResponse)
async def set_stock(
    product_id: UUID, payload: StockSetRequest, actor: CatalogAdmin, session: DatabaseSession
) -> ProductResponse:
    product = await AdjustStock(SqlAlchemyCatalogRepository(session))(
        actor=actor, product_id=product_id, quantity=payload.quantity
    )
    return ProductResponse.from_domain(product)


@router.patch("/products/{product_id}/availability", response_model=ProductResponse)
async def set_availability(
    product_id: UUID, payload: AvailabilityRequest, actor: CatalogAdmin, session: DatabaseSession
) -> ProductResponse:
    product = await SetProductAvailability(SqlAlchemyCatalogRepository(session))(
        actor=actor, product_id=product_id, is_available=payload.is_available
    )
    return ProductResponse.from_domain(product)
