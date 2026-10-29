"""Add profile columns (phone, avatar_url, saved_cards, saved_addresses) to users.

Revision ID: 20261029_0005
Revises: 20261022_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261029_0005"
down_revision: str | Sequence[str] | None = "20261022_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone", sa.String(length=30), nullable=True),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.Text(), nullable=True),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column(
            "saved_cards",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column(
            "saved_addresses",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("users", "saved_addresses", schema="public")
    op.drop_column("users", "saved_cards", schema="public")
    op.drop_column("users", "avatar_url", schema="public")
    op.drop_column("users", "phone", schema="public")

