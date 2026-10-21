"""Stable HTTP mapping for expected M02 errors."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from restaurant_app.modules.m02_catalog_stock.domain.errors import (
    CatalogError,
    CategoryNameConflictError,
    CategoryNotFoundError,
    InvalidCatalogValueError,
    ProductNotFoundError,
)


def install_catalog_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(CatalogError)
    async def catalog_error_handler(request: Request, error: CatalogError) -> JSONResponse:
        del request
        if isinstance(error, (CategoryNotFoundError, ProductNotFoundError)):
            code = status.HTTP_404_NOT_FOUND
            detail = (
                "Category not found"
                if isinstance(error, CategoryNotFoundError)
                else "Product not found"
            )
        elif isinstance(error, CategoryNameConflictError):
            code = status.HTTP_409_CONFLICT
            detail = "Category name already exists"
        elif isinstance(error, InvalidCatalogValueError):
            code = status.HTTP_422_UNPROCESSABLE_CONTENT
            detail = str(error)
        else:  # pragma: no cover - new CatalogError subclasses default safely
            code = status.HTTP_400_BAD_REQUEST
            detail = "Catalog request could not be processed"
        return JSONResponse(status_code=code, content={"detail": detail})
