"""Strict REST contracts for the M02 catalog slice."""

from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from restaurant_app.modules.m02_catalog_stock.domain.entities import Category, Product


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CategoryRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=100)


class ProductCreateRequest(StrictRequest):
    category_id: UUID
    name: str = Field(min_length=1, max_length=160)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=500)


class ProductPatchRequest(StrictRequest):
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if (
            self.category_id is None
            and self.name is None
            and self.price is None
            and self.image_url is None
            and self.description is None
        ):
            raise ValueError("at least one product field is required")
        return self


class StockSetRequest(StrictRequest):
    quantity: int = Field(ge=0, le=2_147_483_647)


class AvailabilityRequest(StrictRequest):
    is_available: bool


class CategoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str

    @classmethod
    def from_domain(cls, category: Category) -> Self:
        return cls(id=category.id, name=category.name)


class ProductResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    category_id: UUID
    name: str
    price: Decimal
    stock_qty: int
    is_available: bool
    image_url: str | None = None
    description: str | None = None

    @classmethod
    def from_domain(cls, product: Product) -> Self:
        return cls(
            id=product.id,
            category_id=product.category_id,
            name=product.name,
            price=product.price,
            stock_qty=product.stock_qty,
            is_available=product.is_available,
            image_url=product.image_url,
            description=product.description,
        )


class CatalogProductResponse(BaseModel):
    """Product response including sale availability and stock for staff."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    category_id: UUID
    name: str
    price: Decimal
    available_for_sale: bool
    stock_qty: int = 0
    is_available: bool = True
    image_url: str | None = None
    description: str | None = None

    @classmethod
    def from_domain(cls, product: Product) -> Self:
        return cls(
            id=product.id,
            category_id=product.category_id,
            name=product.name,
            price=product.price,
            available_for_sale=product.is_available and product.stock_qty > 0,
            stock_qty=product.stock_qty,
            is_available=product.is_available,
            image_url=product.image_url,
            description=product.description,
        )


class ImageUploadRequest(StrictRequest):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="image/jpeg", max_length=100)
    data_base64: str = Field(min_length=1)


class ImageUploadResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_url: str
    filename: str
    size_bytes: int

