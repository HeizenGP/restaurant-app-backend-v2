"""Track the current manual occupation for verified additional APP orders.

Revision ID: 20261021_0003
Revises: 20261021_0002
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_0003"
down_revision: str | Sequence[str] | None = "20261021_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preserve 14 tables; fail closed for pre-existing occupied tables."""

    op.add_column(
        "restaurant_tables",
        sa.Column("occupancy_started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="public",
    )
    # Historical occupancies cannot prove which customer belongs to the current cycle.
    op.execute(
        "UPDATE public.restaurant_tables "
        "SET occupancy_started_at = clock_timestamp() WHERE is_occupied"
    )
    op.create_check_constraint(
        "ck_restaurant_tables_occupancy_started",
        "restaurant_tables",
        "(is_occupied AND occupancy_started_at IS NOT NULL) "
        "OR (NOT is_occupied AND occupancy_started_at IS NULL)",
        schema="public",
    )


def downgrade() -> None:
    """Remove only the additional occupation metadata."""

    op.drop_constraint(
        "ck_restaurant_tables_occupancy_started", "restaurant_tables", schema="public"
    )
    op.drop_column("restaurant_tables", "occupancy_started_at", schema="public")
