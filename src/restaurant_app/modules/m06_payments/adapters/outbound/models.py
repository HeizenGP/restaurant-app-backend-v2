"""SQLAlchemy mappings owned by M06 payments."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class PaymentModel(Base):
    """Immutable simulated advance or collection record."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("kind IN ('ADVANCE','COLLECTION')", name="ck_payments_kind"),
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint(
            "(kind = 'ADVANCE' AND reference_code IS NULL) OR "
            "(kind = 'COLLECTION' AND method_code IS NOT NULL AND ("
            "(method_code = 'EFECTIVO' AND reference_code IS NULL) OR "
            "(method_code IN ('YAPE','PLIN') AND reference_code IS NOT NULL "
            "AND reference_code ~ '^9[0-9]{8}$') OR "
            "(method_code = 'TARJETA' AND reference_code IS NOT NULL "
            "AND reference_code ~ '^[0-9]{9}$'))",
            name="ck_payments_method_reference",
        ),
        CheckConstraint(
            "refund_decision IS NULL OR refund_decision IN ('APPROVED','DENIED')",
            name="ck_payments_refund_decision",
        ),
        CheckConstraint(
            "(refund_decision IS NULL AND refund_decided_by_user_id IS NULL "
            "AND refund_decided_at IS NULL) "
            "OR (kind = 'ADVANCE' AND refund_decision IS NOT NULL "
            "AND refund_decided_by_user_id IS NOT NULL "
            "AND refund_decided_at IS NOT NULL)",
            name="ck_payments_refund_fields",
        ),
        Index("ix_payments_order_recorded", "order_id", "recorded_at"),
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
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method_code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reference_code: Mapped[str | None] = mapped_column(String(9), nullable=True)
    recorded_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    operation_request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.idempotency_requests.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    refund_decision: Mapped[str | None] = mapped_column(String(12), nullable=True)
    refund_decided_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    refund_decided_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


Index(
    "ux_payments_one_advance_per_order",
    PaymentModel.order_id,
    unique=True,
    postgresql_where=text("kind = 'ADVANCE'"),
)
