"""Validate simulated collection methods; add a non-sensitive payment reference.

Revision ID: 20261022_0004
Revises: 20261021_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0004"
down_revision: str | Sequence[str] | None = "20261021_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAYMENT_METHOD_CHECK = (
    "(kind = 'ADVANCE' AND reference_code IS NULL) OR "
    "(kind = 'COLLECTION' AND method_code IS NOT NULL AND ("
    "(method_code = 'EFECTIVO' AND reference_code IS NULL) OR "
    "(method_code IN ('YAPE','PLIN') AND reference_code IS NOT NULL "
    "AND reference_code ~ '^9[0-9]{8}$') OR "
    "(method_code = 'TARJETA' AND reference_code IS NOT NULL "
    "AND reference_code ~ '^[0-9]{9}$'))"
)


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("reference_code", sa.String(length=9), nullable=True),
        schema="public",
    )
    # Retain older collections that used unrestricted method codes.
    # New rows and updates must satisfy the constraint.
    op.execute(
        "ALTER TABLE public.payments ADD CONSTRAINT "
        "ck_payments_method_reference CHECK (" + PAYMENT_METHOD_CHECK + ") NOT VALID"
    )


def downgrade() -> None:
    op.drop_constraint("ck_payments_method_reference", "payments", schema="public")
    op.drop_column("payments", "reference_code", schema="public")
