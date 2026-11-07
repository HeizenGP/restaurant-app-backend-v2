"""SQLAlchemy mappings owned by M02 catalog and stock."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class CategoryModel(Base):
    """Product category."""

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_categories_name_not_blank"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class ProductModel(Base):
    """Sellable finished product and its current stock."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_products_name_not_blank"),
        CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
        CheckConstraint("stock_qty >= 0", name="ck_products_stock_nonnegative"),
        Index("ix_products_category_available", "category_id", "is_available"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    category_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class StockMovementModel(Base):
    """Immutable audit movement for finished-product stock."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("kind IN ('MANUAL', 'ORDER')", name="ck_stock_movements_kind"),
        CheckConstraint(
            "(kind = 'MANUAL' AND order_item_id IS NULL AND quantity_delta <> 0) "
            "OR (kind = 'ORDER' AND order_item_id IS NOT NULL AND quantity_delta < 0)",
            name="ck_stock_movements_shape",
        ),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    order_item_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.order_items.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


Index(
    "ux_stock_movements_order_item",
    StockMovementModel.order_item_id,
    unique=True,
    postgresql_where=text("kind = 'ORDER'"),
)
Index(
    "ix_stock_movements_product_recorded",
    StockMovementModel.product_id,
    StockMovementModel.recorded_at.desc(),
)
