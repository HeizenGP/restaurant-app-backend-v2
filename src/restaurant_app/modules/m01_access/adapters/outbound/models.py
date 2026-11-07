"""SQLAlchemy mappings owned by M01 access."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
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
        CheckConstraint(
            "password_hash IS NULL OR btrim(password_hash) <> ''",
            name="ck_users_password_hash_not_blank",
        ),
        CheckConstraint(
            "password_hash IS NOT NULL OR google_subject IS NOT NULL",
            name="ck_users_has_authentication_method",
        ),
        UniqueConstraint("google_subject", name="uq_users_google_subject"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
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


class PasswordResetTokenModel(Base):
    """One-time, short-lived password recovery token digest."""

    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="ck_password_reset_tokens_expiry"),
        UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        Index("ix_password_reset_tokens_user_created", "user_id", "created_at"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


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


class UserAddressModel(Base):
    """User delivery address with GPS coordinates and delivery metadata."""

    __tablename__ = "user_addresses"
    __table_args__ = (
        CheckConstraint("btrim(label) <> ''", name="ck_user_addresses_label_not_blank"),
        CheckConstraint("btrim(address) <> ''", name="ck_user_addresses_address_not_blank"),
        CheckConstraint(
            "latitude >= -90.0 AND latitude <= 90.0",
            name="ck_user_addresses_latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180.0 AND longitude <= 180.0",
            name="ck_user_addresses_longitude_range",
        ),
        Index("ix_user_addresses_user_id", "user_id"),
        Index("ix_user_addresses_user_default", "user_id", "is_default"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    department: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recipient_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
