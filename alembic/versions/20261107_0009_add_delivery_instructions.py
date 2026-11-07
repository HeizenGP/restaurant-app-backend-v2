"""Add delivery_instructions column to user_addresses.

Revision ID: 20261107_0009
Revises: 20261107_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261107_0009"
down_revision: str | Sequence[str] | None = "20261107_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_addresses",
        sa.Column("delivery_instructions", sa.String(length=500), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("user_addresses", "delivery_instructions", schema="public")
