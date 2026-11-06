"""SQLAlchemy mappings owned by M01 access."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class UserModel(Base):
    """Registered customer or staff account."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("btrim(display_name) <> ''", name="ck_users_display_name_not_blank"),
        CheckConstraint("btrim(email) <> ''", name="ck_users_email_not_blank"),
        CheckConstraint("btrim(password_hash) <> ''", name="ck_users_password_hash_not_blank"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_cards: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    saved_addresses: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )


Index("ux_users_email_ci", func.lower(UserModel.email), unique=True)


class RoleModel(Base):
    """One of the six approved reference roles."""

    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint(
            "code IN ('CUSTOMER', 'WAITER', 'CASHIER', 'ADMIN', 'KITCHEN', 'SUPER_ADMIN')",
            name="ck_roles_code",
        ),
        CheckConstraint("btrim(label) <> ''", name="ck_roles_label_not_blank"),
        {"schema": "public"},
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)


class UserRoleModel(Base):
    """Many-to-many assignment between users and reference roles."""

    __tablename__ = "user_roles"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "role_code", name="pk_user_roles"),
        Index("ix_user_roles_role_code_user_id", "role_code", "user_id"),
        {"schema": "public"},
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("public.roles.code", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class AuthSessionModel(Base):
    """Registered-user or limited guest session."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("kind IN ('USER', 'GUEST')", name="ck_sessions_kind"),
        CheckConstraint(
            "(kind = 'USER' AND user_id IS NOT NULL) OR (kind = 'GUEST' AND user_id IS NULL)",
            name="ck_sessions_kind_user",
        ),
        CheckConstraint("expires_at > created_at", name="ck_sessions_expiry"),
        Index("ix_sessions_user_expiry", "user_id", "expires_at"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    renewal_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
