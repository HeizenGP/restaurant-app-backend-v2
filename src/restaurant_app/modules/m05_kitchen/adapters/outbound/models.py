"""SQLAlchemy mappings owned by M05 kitchen."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class KitchenTicketModel(Base):
    """Kitchen ticket created for one confirmed order."""

    __tablename__ = "kitchen_tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RECEIVED','PREPARING','READY')",
            name="ck_kitchen_tickets_status",
        ),
        CheckConstraint(
            "(started_at IS NULL) = (started_by_user_id IS NULL)",
            name="ck_kitchen_tickets_started_pair",
        ),
        CheckConstraint(
            "(ready_at IS NULL) = (ready_by_user_id IS NULL)",
            name="ck_kitchen_tickets_ready_pair",
        ),
        CheckConstraint(
            "(status = 'RECEIVED' AND started_at IS NULL "
            "AND started_by_user_id IS NULL AND ready_at IS NULL "
            "AND ready_by_user_id IS NULL) "
            "OR (status = 'PREPARING' AND started_at IS NOT NULL "
            "AND started_by_user_id IS NOT NULL AND ready_at IS NULL "
            "AND ready_by_user_id IS NULL) "
            "OR (status = 'READY' AND started_at IS NOT NULL "
            "AND started_by_user_id IS NOT NULL AND ready_at IS NOT NULL "
            "AND ready_by_user_id IS NOT NULL)",
            name="ck_kitchen_tickets_state_fields",
        ),
        CheckConstraint(
            "(started_at IS NULL OR started_at >= created_at) "
            "AND (ready_at IS NULL OR ready_at >= started_at)",
            name="ck_kitchen_tickets_timeline",
        ),
        Index("ix_kitchen_tickets_status_created", "status", "created_at"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'RECEIVED'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    started_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    ready_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
