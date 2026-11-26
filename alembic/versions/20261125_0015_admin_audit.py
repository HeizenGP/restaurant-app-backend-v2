"""Add append-only audit records with explicitly selected fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261125_0015"
down_revision = "20261125_0014"
branch_labels = None
depends_on = None

# The tracked fields deliberately omit contact details, references, and credentials.
TRACKED = {
    "products": ("id", "name", "category_id", "price", "is_available", "minimum_stock"),
    "categories": ("id", "name", "sort_order", "is_active"),
    "stock_movements": ("id", "product_id", "kind", "quantity_delta", "reason"),
    "orders": ("id", "status"),
    "payments": ("id", "order_id", "table_account_id", "cash_shift_id", "kind", "method_code", "amount"),
    "cash_shifts": ("id", "opened_at", "opened_by_id", "initial_amount", "closed_at", "closed_by_id", "counted_cash"),
    "user_roles": ("user_id", "role_code"),
    "restaurant_settings": ("section",),
    "staff_work_shifts": ("id", "user_id", "starts_at", "ends_at"),
}


def upgrade() -> None:
    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("resource", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(80)),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(12), nullable=False),
        sa.Column("before", JSONB()),
        sa.Column("after", JSONB()),
        schema="public",
    )
    op.create_index("ix_admin_audit_resource_id", "admin_audit_events", ["resource", "id"], schema="public")
    op.execute("""
        CREATE FUNCTION public.kairo_audit_track() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE
            previous jsonb;
            next jsonb;
            field text;
            source jsonb;
            user_id uuid := NULLIF(current_setting('kairo.actor_id', true), '')::uuid;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                source := to_jsonb(OLD);
                previous := '{}'::jsonb;
                FOREACH field IN ARRAY TG_ARGV LOOP
                    previous := previous || jsonb_build_object(field, source -> field);
                END LOOP;
            END IF;
            IF TG_OP <> 'DELETE' THEN
                source := to_jsonb(NEW);
                next := '{}'::jsonb;
                FOREACH field IN ARRAY TG_ARGV LOOP
                    next := next || jsonb_build_object(field, source -> field);
                END LOOP;
            END IF;
            IF previous IS NOT DISTINCT FROM next AND TG_TABLE_NAME <> 'restaurant_settings' THEN
                RETURN NULL;
            END IF;
            INSERT INTO public.admin_audit_events(actor_id, resource, resource_id, action, outcome, before, after)
            VALUES (user_id, TG_TABLE_NAME, COALESCE(next, previous) ->> TG_ARGV[0], TG_OP, 'SUCCESS', previous, next);
            RETURN NULL;
        END;
        $$
    """)
    for table, columns in TRACKED.items():
        arguments = ", ".join(f"'{name}'" for name in columns)
        trigger_events = "UPDATE" if table in {"orders", "restaurant_settings"} else "INSERT OR UPDATE OR DELETE"
        op.execute(
            f"CREATE TRIGGER kairo_audit_change AFTER {trigger_events} ON public.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION public.kairo_audit_track({arguments})"
        )
    op.execute("""
        CREATE FUNCTION public.kairo_audit_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Audit events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER kairo_audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
        ON public.admin_audit_events FOR EACH STATEMENT EXECUTE FUNCTION public.kairo_audit_immutable()
    """)


def downgrade() -> None:
    raise RuntimeError("Downgrading auditing would discard traceability history")
