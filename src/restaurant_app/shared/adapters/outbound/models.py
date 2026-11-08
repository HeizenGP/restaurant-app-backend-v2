"""SQLAlchemy mappings for genuinely shared technical persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class IdempotencyRequestModel(Base):
    """Cross-module request deduplication record."""

    __tablename__ = "idempotency_requests"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(actor_user_id, actor_guest_session_id) = 1",
            name="ck_idempotency_actor",
        ),
        CheckConstraint("expires_at > created_at", name="ck_idempotency_expiry"),
        CheckConstraint("btrim(operation) <> ''", name="ck_idempotency_operation_not_blank"),
        CheckConstraint("btrim(request_key) <> ''", name="ck_idempotency_key_not_blank"),
        CheckConstraint(
            "request_hash ~ '^[0-9a-fA-F]{64}$'",
            name="ck_idempotency_hash_hex",
        ),
        Index("ix_idempotency_expiry", "expires_at"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_guest_session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.auth_sessions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    result_order_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.orders.id", ondelete="RESTRICT"),
        nullable=True,
    )
    result_table_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.table_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


Index(
    "ux_idempotency_user_request",
    IdempotencyRequestModel.actor_user_id,
    IdempotencyRequestModel.operation,
    IdempotencyRequestModel.request_key,
    unique=True,
    postgresql_where=text("actor_user_id IS NOT NULL"),
)
Index(
    "ux_idempotency_guest_request",
    IdempotencyRequestModel.actor_guest_session_id,
    IdempotencyRequestModel.operation,
    IdempotencyRequestModel.request_key,
    unique=True,
    postgresql_where=text("actor_guest_session_id IS NOT NULL"),
)
