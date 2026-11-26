"""Preserve item and quantity allocations for new table checkouts."""

from alembic import op
import sqlalchemy as sa

revision = "20261125_0016"
down_revision = "20261125_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "table_payment_allocations",
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("public.idempotency_requests.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("public.order_items.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_table_payment_allocation_quantity"),
        schema="public",
    )
    op.create_index("ix_payment_allocation_item", "table_payment_allocations", ["item_id"], schema="public")


def downgrade() -> None:
    raise RuntimeError("Downgrading table checkout would discard item collection history")
