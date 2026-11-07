"""Add user_addresses table with GPS coordinates and delivery metadata.

Revision ID: 20261107_0008
Revises: 20261106_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261107_0008"
down_revision: str | Sequence[str] | None = "20261106_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_addresses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("department", sa.String(length=50), nullable=True),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("recipient_phone", sa.String(length=30), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("btrim(label) <> ''", name="ck_user_addresses_label_not_blank"),
        sa.CheckConstraint("btrim(address) <> ''", name="ck_user_addresses_address_not_blank"),
        sa.CheckConstraint(
            "latitude >= -90.0 AND latitude <= 90.0",
            name="ck_user_addresses_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude >= -180.0 AND longitude <= 180.0",
            name="ck_user_addresses_longitude_range",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["public.users.id"],
            name="fk_user_addresses_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_addresses"),
        schema="public",
    )
    op.create_index(
        "ix_user_addresses_user_id",
        "user_addresses",
        ["user_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_user_addresses_user_default",
        "user_addresses",
        ["user_id", "is_default"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index("ix_user_addresses_user_default", table_name="user_addresses", schema="public")
    op.drop_index("ix_user_addresses_user_id", table_name="user_addresses", schema="public")
    op.drop_table("user_addresses", schema="public")
