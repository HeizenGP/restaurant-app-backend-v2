"""SQLAlchemy mappings owned by M03 tables."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class RestaurantTableModel(Base):
    """Physical table in the single approved restaurant."""

    __tablename__ = "restaurant_tables"
    __table_args__ = (
        CheckConstraint("btrim(code) <> ''", name="ck_restaurant_tables_code_not_blank"),
        CheckConstraint(
            "(is_occupied AND occupancy_started_at IS NOT NULL) "
            "OR (NOT is_occupied AND occupancy_started_at IS NULL)",
            name="ck_restaurant_tables_occupancy_started",
        ),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    area_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_occupied: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    occupancy_started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )


class TableAccountModel(Base):
    """Persistent service session that groups every order for one table visit."""

    __tablename__ = "table_accounts"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'PAID')", name="ck_table_accounts_status"),
        CheckConstraint(
            "num_nonnulls(customer_user_id, guest_session_id) <= 1",
            name="ck_table_accounts_single_customer",
        ),
        CheckConstraint(
            "(status = 'OPEN' AND closed_at IS NULL) "
            "OR (status = 'PAID' AND closed_at IS NOT NULL)",
            name="ck_table_accounts_closed_state",
        ),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    table_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.restaurant_tables.id", ondelete="RESTRICT"),
        nullable=False,
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
    opened_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default=text("'OPEN'"))
    opened_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )


Index(
    "ux_table_accounts_one_open_per_table",
    TableAccountModel.table_id,
    unique=True,
    postgresql_where=text("status = 'OPEN'"),
)
Index(
    "ix_table_accounts_table_opened", TableAccountModel.table_id, TableAccountModel.opened_at.desc()
)
