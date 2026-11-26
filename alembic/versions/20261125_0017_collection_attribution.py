"""Link split collections to the item allocation that they fund."""

from alembic import op
import sqlalchemy as sa

revision = "20261125_0017"
down_revision = "20261125_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("allocation_request_id", sa.Uuid()), schema="public")
    op.create_foreign_key(
        "payments_allocation_request_id_fkey", "payments", "idempotency_requests",
        ["allocation_request_id"], ["id"], source_schema="public", referent_schema="public",
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    raise RuntimeError("Downgrading collection attribution would lose the link to item payments")
