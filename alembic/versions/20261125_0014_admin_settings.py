"""Store business settings, work schedules, and inventory administration data."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261125_0014"
down_revision = "20261125_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    settings = op.create_table(
        "restaurant_settings",
        sa.Column("section", sa.String(32), primary_key=True),
        sa.Column("configuration", JSONB(), nullable=False),
        schema="public",
    )
    op.bulk_insert(settings, [
        {"section": "restaurant", "configuration": {}},
        {"section": "payment-methods", "configuration": {"enabled": ["EFECTIVO", "YAPE", "PLIN", "TARJETA"]}},
        {"section": "modalities", "configuration": {"enabled": ["LOCAL", "PICKUP", "DELIVERY"]}},
    ], multiinsert=False)
    op.create_table(
        "staff_work_shifts",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("public.users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_work_shift_period"),
        schema="public",
    )
    op.create_index("ix_work_shift_user_start", "staff_work_shifts", ["user_id", "starts_at"], schema="public")
    op.add_column("categories", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), schema="public")
    op.add_column("categories", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), schema="public")
    op.add_column("products", sa.Column("minimum_stock", sa.Integer(), nullable=False, server_default="10"), schema="public")
    op.create_check_constraint("ck_products_minimum_stock", "products", "minimum_stock >= 0", schema="public")
    op.add_column("stock_movements", sa.Column("reason", sa.String(300)), schema="public")


def downgrade() -> None:
    raise RuntimeError("Downgrading administrative settings would discard configuration and work history")
