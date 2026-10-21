"""SQLAlchemy mappings owned by M04 orders."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class OrderModel(Base):
    """Commercial order header."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("modality IN ('LOCAL', 'PICKUP', 'DELIVERY')", name="ck_orders_modality"),
        CheckConstraint(
            "channel IN ('APP', 'WAITER', 'PHONE', 'WHATSAPP')",
            name="ck_orders_channel",
        ),
        CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'CONFIRMED', 'CANCELLED', 'CLOSED')",
            name="ck_orders_status",
        ),
        CheckConstraint("total_amount > 0", name="ck_orders_total_positive"),
        CheckConstraint("version >= 0", name="ck_orders_version_nonnegative"),
        CheckConstraint(
            "(modality = 'LOCAL' AND table_id IS NOT NULL AND delivery_address IS NULL) "
            "OR (modality = 'PICKUP' AND table_id IS NULL AND delivery_address IS NULL) "
            "OR (modality = 'DELIVERY' AND table_id IS NULL "
            "AND NULLIF(btrim(delivery_address), '') IS NOT NULL)",
            name="ck_orders_modality_fields",
        ),
        CheckConstraint(
            "(channel = 'WAITER' AND modality = 'LOCAL') "
            "OR (channel IN ('PHONE','WHATSAPP') AND modality IN ('PICKUP','DELIVERY')) "
            "OR (channel = 'APP')",
            name="ck_orders_channel_modality",
        ),
        CheckConstraint(
            "(channel = 'APP' AND num_nonnulls(customer_user_id, guest_session_id) = 1) "
            "OR (channel <> 'APP' AND created_by_user_id IS NOT NULL)",
            name="ck_orders_requester",
        ),
        CheckConstraint(
            "(decided_by_user_id IS NULL) = (decided_at IS NULL)",
            name="ck_orders_decision_pair",
        ),
        CheckConstraint(
            "(confirmed_by_user_id IS NULL) = (confirmed_at IS NULL)",
            name="ck_orders_confirmed_pair",
        ),
        CheckConstraint(
            "(closed_by_user_id IS NULL) = (closed_at IS NULL)",
            name="ck_orders_closed_pair",
        ),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    modality: Mapped[str] = mapped_column(String(12), nullable=False)
    channel: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'REQUESTED'")
    )
    customer_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    guest_session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.auth_sessions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    table_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.restaurant_tables.id", ondelete="RESTRICT"),
        nullable=True,
    )
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    table_verified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


Index(
    "ix_orders_customer_created",
    OrderModel.customer_user_id,
    OrderModel.created_at.desc(),
    postgresql_where=text("customer_user_id IS NOT NULL"),
)
Index(
    "ix_orders_guest_created",
    OrderModel.guest_session_id,
    OrderModel.created_at.desc(),
    postgresql_where=text("guest_session_id IS NOT NULL"),
)
Index("ix_orders_status_created", OrderModel.status, OrderModel.created_at.desc())
Index(
    "ix_orders_table_id",
    OrderModel.table_id,
    postgresql_where=text("table_id IS NOT NULL"),
)


class OrderItemModel(Base):
    """Immutable snapshot line registered with an order header."""

    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("unit_price_snapshot >= 0", name="ck_order_items_price_nonnegative"),
        CheckConstraint(
            "btrim(product_name_snapshot) <> ''",
            name="ck_order_items_name_not_blank",
        ),
        Index("ix_order_items_product", "product_id"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
