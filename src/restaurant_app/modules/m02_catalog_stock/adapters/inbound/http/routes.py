"""REST endpoints for approved M02 RF-M02-01..04 only."""

import base64
from pathlib import Path
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
import requests

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m02_catalog_stock.adapters.inbound.http.dependencies import CatalogAdmin
from restaurant_app.modules.m02_catalog_stock.adapters.inbound.http.schemas import (
    AvailabilityRequest,
    CatalogProductResponse,
    CategoryRequest,
    CategoryResponse,
    ImageUploadRequest,
    ImageUploadResponse,
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


@router.post(
    "/upload-image",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir imagen de producto a almacenamiento del backend",
)
async def upload_catalog_image(
    payload: ImageUploadRequest,
    request: Request,
    actor: CatalogAdmin,
) -> ImageUploadResponse:
    raw_b64 = payload.data_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Los datos de imagen en base64 no son válidos.",
        )

    # Límite de tamaño: 10 MB
    max_size = 10 * 1024 * 1024
    if len(image_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"La imagen supera el límite permitido de 10 MB (pesa {len(image_bytes) / (1024 * 1024):.1f} MB).",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El archivo de imagen no contiene datos.",
        )

    original_name = Path(payload.filename).name
    ext = Path(original_name).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"

    clean_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", Path(original_name).stem)[:30]
    unique_filename = f"plato_{uuid4().hex[:8]}_{clean_stem}{ext}"

    uploads_dir = Path("uploads/products")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target_path = uploads_dir / unique_filename
    target_path.write_bytes(image_bytes)

    base_url = str(request.base_url).rstrip("/")
    fallback_url = f"{base_url}/uploads/products/{unique_filename}"
    final_url = fallback_url

    # Respaldo permanente en CDN en la nube (sin problemas de disco efímero en Render)
    try:
        resp = requests.post(
            "https://freeimage.host/api/1/upload",
            data={
                "key": "6d207e02198a847aa98d0a2a901485a5",
                "action": "upload",
            },
            files={"source": (unique_filename, image_bytes)},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            cloud_url = data.get("image", {}).get("url")
            if cloud_url and cloud_url.startswith("https://"):
                final_url = cloud_url
    except Exception:
        # Si falla el CDN externo, mantiene la URL estática local/servidor
        pass

    return ImageUploadResponse(
        image_url=final_url,
        filename=unique_filename,
        size_bytes=len(image_bytes),
    )

