"""Persist cash shifts and link new collections without backfilling history."""

from alembic import op
import sqlalchemy as sa

revision = "20261125_0013"
down_revision = "20261107_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_shifts",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_by_id", sa.Uuid(), sa.ForeignKey("public.users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("initial_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("opening_notes", sa.String(500)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_by_id", sa.Uuid(), sa.ForeignKey("public.users.id", ondelete="RESTRICT")),
        sa.Column("counted_cash", sa.Numeric(12, 2)),
        sa.Column("closing_notes", sa.String(500)),
        sa.CheckConstraint("initial_amount >= 0 AND counted_cash >= 0", name="ck_cash_shift_amount"),
        sa.CheckConstraint(
            "(closed_at IS NULL AND closed_by_id IS NULL AND counted_cash IS NULL) OR "
            "(closed_at IS NOT NULL AND closed_by_id IS NOT NULL AND counted_cash IS NOT NULL)",
            name="ck_cash_shift_closure",
        ),
        schema="public",
    )
    op.create_index(
        "ux_cash_shifts_open", "cash_shifts", [sa.text("(1)")], unique=True,
        postgresql_where=sa.text("closed_at IS NULL"), schema="public",
    )
    op.add_column("payments", sa.Column("cash_shift_id", sa.Uuid()), schema="public")
    op.create_foreign_key(
        "payments_cash_shift_id_fkey", "payments", "cash_shifts", ["cash_shift_id"], ["id"],
        source_schema="public", referent_schema="public",
        ondelete="RESTRICT",
    )
    op.create_index("ix_payments_cash_shift", "payments", ["cash_shift_id"], schema="public")


def downgrade() -> None:
    raise RuntimeError("Downgrading cash shifts would discard recorded cash history")
