"""Create the approved ETAPA 06 schema.

Revision ID: 20261021_0001
Revises:
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261021_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "public"
UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = postgresql.TIMESTAMP(timezone=True)


def _uuid_primary_key() -> sa.Column:
    return sa.Column(
        "id",
        UUID,
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _uuid_foreign_key(name: str, target: str, *, nullable: bool) -> sa.Column:
    return sa.Column(
        name,
        UUID,
        sa.ForeignKey(target, ondelete="RESTRICT"),
        nullable=nullable,
    )


def upgrade() -> None:
    """Create 14 tables, reference roles, 8 functions, 9 triggers, and one view."""

    op.create_table(
        "users",
        _uuid_primary_key(),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("btrim(display_name) <> ''", name="ck_users_display_name_not_blank"),
        sa.CheckConstraint("btrim(email) <> ''", name="ck_users_email_not_blank"),
        sa.CheckConstraint("btrim(password_hash) <> ''", name="ck_users_password_hash_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ux_users_email_ci",
        "users",
        [sa.text("lower(email)")],
        unique=True,
        schema=SCHEMA,
    )

    op.create_table(
        "roles",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "code IN ('CUSTOMER', 'WAITER', 'CASHIER', 'ADMIN', 'KITCHEN', 'SUPER_ADMIN')",
            name="ck_roles_code",
        ),
        sa.CheckConstraint("btrim(label) <> ''", name="ck_roles_label_not_blank"),
        sa.PrimaryKeyConstraint("code"),
        schema=SCHEMA,
    )
    op.execute(
        """
        INSERT INTO public.roles (code, label) VALUES
            ('CUSTOMER',    'Cliente'),
            ('WAITER',      'Mozo'),
            ('CASHIER',     'Cajero'),
            ('ADMIN',       'Administrador'),
            ('KITCHEN',     'Personal de cocina'),
            ('SUPER_ADMIN', 'Superadministrador')
        """
    )

    op.create_table(
        "user_roles",
        _uuid_foreign_key("user_id", "public.users.id", nullable=False),
        sa.Column(
            "role_code",
            sa.String(length=32),
            sa.ForeignKey("public.roles.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "role_code", name="pk_user_roles"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_user_roles_role_code_user_id",
        "user_roles",
        ["role_code", "user_id"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "auth_sessions",
        _uuid_primary_key(),
        sa.Column("kind", sa.String(length=12), nullable=False),
        _uuid_foreign_key("user_id", "public.users.id", nullable=True),
        sa.Column("renewal_token_hash", sa.Text(), nullable=True, unique=True),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=False),
        sa.Column("revoked_at", TIMESTAMPTZ, nullable=True),
        sa.CheckConstraint("kind IN ('USER', 'GUEST')", name="ck_sessions_kind"),
        sa.CheckConstraint(
            "(kind = 'USER' AND user_id IS NOT NULL) OR (kind = 'GUEST' AND user_id IS NULL)",
            name="ck_sessions_kind_user",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_sessions_expiry"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_sessions_user_expiry",
        "auth_sessions",
        ["user_id", "expires_at"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "categories",
        _uuid_primary_key(),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_categories_name_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    op.create_table(
        "products",
        _uuid_primary_key(),
        _uuid_foreign_key("category_id", "public.categories.id", nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock_qty", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "is_available",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_products_name_not_blank"),
        sa.CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
        sa.CheckConstraint("stock_qty >= 0", name="ck_products_stock_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_products_category_available",
        "products",
        ["category_id", "is_available"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "restaurant_tables",
        _uuid_primary_key(),
        sa.Column("code", sa.String(length=24), nullable=False, unique=True),
        sa.Column("area_label", sa.String(length=80), nullable=True),
        sa.Column(
            "is_occupied",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        _uuid_foreign_key("updated_by_user_id", "public.users.id", nullable=True),
        sa.CheckConstraint("btrim(code) <> ''", name="ck_restaurant_tables_code_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    op.create_table(
        "orders",
        _uuid_primary_key(),
        sa.Column("modality", sa.String(length=12), nullable=False),
        sa.Column("channel", sa.String(length=12), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'REQUESTED'"),
            nullable=False,
        ),
        _uuid_foreign_key("customer_user_id", "public.users.id", nullable=True),
        _uuid_foreign_key("guest_session_id", "public.auth_sessions.id", nullable=True),
        _uuid_foreign_key("created_by_user_id", "public.users.id", nullable=True),
        _uuid_foreign_key("table_id", "public.restaurant_tables.id", nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.String(length=120), nullable=True),
        sa.Column("contact_phone", sa.String(length=30), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        _uuid_foreign_key("decided_by_user_id", "public.users.id", nullable=True),
        sa.Column("decided_at", TIMESTAMPTZ, nullable=True),
        sa.Column("table_verified_at", TIMESTAMPTZ, nullable=True),
        _uuid_foreign_key("confirmed_by_user_id", "public.users.id", nullable=True),
        sa.Column("confirmed_at", TIMESTAMPTZ, nullable=True),
        _uuid_foreign_key("closed_by_user_id", "public.users.id", nullable=True),
        sa.Column("closed_at", TIMESTAMPTZ, nullable=True),
        sa.CheckConstraint(
            "modality IN ('LOCAL', 'PICKUP', 'DELIVERY')", name="ck_orders_modality"
        ),
        sa.CheckConstraint(
            "channel IN ('APP', 'WAITER', 'PHONE', 'WHATSAPP')",
            name="ck_orders_channel",
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'CONFIRMED', 'CANCELLED', 'CLOSED')",
            name="ck_orders_status",
        ),
        sa.CheckConstraint("total_amount > 0", name="ck_orders_total_positive"),
        sa.CheckConstraint("version >= 0", name="ck_orders_version_nonnegative"),
        sa.CheckConstraint(
            "(modality = 'LOCAL' AND table_id IS NOT NULL AND delivery_address IS NULL) "
            "OR (modality = 'PICKUP' AND table_id IS NULL AND delivery_address IS NULL) "
            "OR (modality = 'DELIVERY' AND table_id IS NULL "
            "AND NULLIF(btrim(delivery_address), '') IS NOT NULL)",
            name="ck_orders_modality_fields",
        ),
        sa.CheckConstraint(
            "(channel = 'WAITER' AND modality = 'LOCAL') "
            "OR (channel IN ('PHONE','WHATSAPP') "
            "AND modality IN ('PICKUP','DELIVERY')) OR (channel = 'APP')",
            name="ck_orders_channel_modality",
        ),
        sa.CheckConstraint(
            "(channel = 'APP' AND num_nonnulls(customer_user_id, guest_session_id) = 1) "
            "OR (channel <> 'APP' AND created_by_user_id IS NOT NULL)",
            name="ck_orders_requester",
        ),
        sa.CheckConstraint(
            "(decided_by_user_id IS NULL) = (decided_at IS NULL)",
            name="ck_orders_decision_pair",
        ),
        sa.CheckConstraint(
            "(confirmed_by_user_id IS NULL) = (confirmed_at IS NULL)",
            name="ck_orders_confirmed_pair",
        ),
        sa.CheckConstraint(
            "(closed_by_user_id IS NULL) = (closed_at IS NULL)",
            name="ck_orders_closed_pair",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_orders_customer_created",
        "orders",
        ["customer_user_id", sa.text("created_at DESC")],
        unique=False,
        schema=SCHEMA,
        postgresql_where=sa.text("customer_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_orders_guest_created",
        "orders",
        ["guest_session_id", sa.text("created_at DESC")],
        unique=False,
        schema=SCHEMA,
        postgresql_where=sa.text("guest_session_id IS NOT NULL"),
    )
    op.create_index(
        "ix_orders_status_created",
        "orders",
        ["status", sa.text("created_at DESC")],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_orders_table_id",
        "orders",
        ["table_id"],
        unique=False,
        schema=SCHEMA,
        postgresql_where=sa.text("table_id IS NOT NULL"),
    )

    op.create_table(
        "order_items",
        _uuid_primary_key(),
        _uuid_foreign_key("order_id", "public.orders.id", nullable=False),
        _uuid_foreign_key("product_id", "public.products.id", nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_snapshot", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.CheckConstraint("unit_price_snapshot >= 0", name="ck_order_items_price_nonnegative"),
        sa.CheckConstraint(
            "btrim(product_name_snapshot) <> ''",
            name="ck_order_items_name_not_blank",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_order_items_product",
        "order_items",
        ["product_id"],
        unique=False,
        schema=SCHEMA,
    )

    _create_order_integrity_routines()

    op.create_table(
        "stock_movements",
        _uuid_primary_key(),
        _uuid_foreign_key("product_id", "public.products.id", nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        _uuid_foreign_key("order_item_id", "public.order_items.id", nullable=True),
        _uuid_foreign_key("actor_user_id", "public.users.id", nullable=False),
        sa.Column(
            "recorded_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('MANUAL', 'ORDER')", name="ck_stock_movements_kind"),
        sa.CheckConstraint(
            "(kind = 'MANUAL' AND order_item_id IS NULL AND quantity_delta <> 0) "
            "OR (kind = 'ORDER' AND order_item_id IS NOT NULL AND quantity_delta < 0)",
            name="ck_stock_movements_shape",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ux_stock_movements_order_item",
        "stock_movements",
        ["order_item_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("kind = 'ORDER'"),
    )
    op.create_index(
        "ix_stock_movements_product_recorded",
        "stock_movements",
        ["product_id", sa.text("recorded_at DESC")],
        unique=False,
        schema=SCHEMA,
    )

    _create_stock_integrity_routines()

    op.create_table(
        "kitchen_tickets",
        _uuid_primary_key(),
        _uuid_foreign_key("order_id", "public.orders.id", nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'RECEIVED'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", TIMESTAMPTZ, nullable=True),
        sa.Column("ready_at", TIMESTAMPTZ, nullable=True),
        _uuid_foreign_key("started_by_user_id", "public.users.id", nullable=True),
        _uuid_foreign_key("ready_by_user_id", "public.users.id", nullable=True),
        sa.CheckConstraint(
            "status IN ('RECEIVED','PREPARING','READY')",
            name="ck_kitchen_tickets_status",
        ),
        sa.CheckConstraint(
            "(started_at IS NULL) = (started_by_user_id IS NULL)",
            name="ck_kitchen_tickets_started_pair",
        ),
        sa.CheckConstraint(
            "(ready_at IS NULL) = (ready_by_user_id IS NULL)",
            name="ck_kitchen_tickets_ready_pair",
        ),
        sa.CheckConstraint(
            "(status = 'RECEIVED' AND started_at IS NULL "
            "AND started_by_user_id IS NULL AND ready_at IS NULL "
            "AND ready_by_user_id IS NULL) "
            "OR (status = 'PREPARING' AND started_at IS NOT NULL "
            "AND started_by_user_id IS NOT NULL AND ready_at IS NULL "
            "AND ready_by_user_id IS NULL) "
            "OR (status = 'READY' AND started_at IS NOT NULL "
            "AND started_by_user_id IS NOT NULL AND ready_at IS NOT NULL "
            "AND ready_by_user_id IS NOT NULL)",
            name="ck_kitchen_tickets_state_fields",
        ),
        sa.CheckConstraint(
            "(started_at IS NULL OR started_at >= created_at) "
            "AND (ready_at IS NULL OR ready_at >= started_at)",
            name="ck_kitchen_tickets_timeline",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_kitchen_tickets_status_created",
        "kitchen_tickets",
        ["status", "created_at"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "idempotency_requests",
        _uuid_primary_key(),
        _uuid_foreign_key("actor_user_id", "public.users.id", nullable=True),
        _uuid_foreign_key("actor_guest_session_id", "public.auth_sessions.id", nullable=True),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.CHAR(length=64), nullable=False),
        _uuid_foreign_key("result_order_id", "public.orders.id", nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=False),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.CheckConstraint(
            "num_nonnulls(actor_user_id, actor_guest_session_id) = 1",
            name="ck_idempotency_actor",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_idempotency_expiry"),
        sa.CheckConstraint("btrim(operation) <> ''", name="ck_idempotency_operation_not_blank"),
        sa.CheckConstraint("btrim(request_key) <> ''", name="ck_idempotency_key_not_blank"),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-fA-F]{64}$'",
            name="ck_idempotency_hash_hex",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ux_idempotency_user_request",
        "idempotency_requests",
        ["actor_user_id", "operation", "request_key"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("actor_user_id IS NOT NULL"),
    )
    op.create_index(
        "ux_idempotency_guest_request",
        "idempotency_requests",
        ["actor_guest_session_id", "operation", "request_key"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("actor_guest_session_id IS NOT NULL"),
    )
    op.create_index(
        "ix_idempotency_expiry",
        "idempotency_requests",
        ["expires_at"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "payments",
        _uuid_primary_key(),
        _uuid_foreign_key("order_id", "public.orders.id", nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("method_code", sa.String(length=24), nullable=True),
        _uuid_foreign_key("recorded_by_user_id", "public.users.id", nullable=False),
        sa.Column(
            "recorded_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        _uuid_foreign_key("operation_request_id", "public.idempotency_requests.id", nullable=False),
        sa.Column("refund_decision", sa.String(length=12), nullable=True),
        _uuid_foreign_key("refund_decided_by_user_id", "public.users.id", nullable=True),
        sa.Column("refund_decided_at", TIMESTAMPTZ, nullable=True),
        sa.CheckConstraint("kind IN ('ADVANCE','COLLECTION')", name="ck_payments_kind"),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint(
            "refund_decision IS NULL OR refund_decision IN ('APPROVED','DENIED')",
            name="ck_payments_refund_decision",
        ),
        sa.CheckConstraint(
            "(refund_decision IS NULL AND refund_decided_by_user_id IS NULL "
            "AND refund_decided_at IS NULL) "
            "OR (kind = 'ADVANCE' AND refund_decision IS NOT NULL "
            "AND refund_decided_by_user_id IS NOT NULL "
            "AND refund_decided_at IS NOT NULL)",
            name="ck_payments_refund_fields",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_request_id"),
        schema=SCHEMA,
    )

    _create_payment_integrity_routines()

    op.create_index(
        "ux_payments_one_advance_per_order",
        "payments",
        ["order_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("kind = 'ADVANCE'"),
    )
    op.create_index(
        "ix_payments_order_recorded",
        "payments",
        ["order_id", "recorded_at"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "fulfillments",
        _uuid_primary_key(),
        _uuid_foreign_key("order_id", "public.orders.id", nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        _uuid_foreign_key("recorded_by_user_id", "public.users.id", nullable=False),
        sa.Column(
            "recorded_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('SERVED','PICKED_UP','DELIVERED')",
            name="ck_fulfillments_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
        schema=SCHEMA,
    )

    _create_payment_summary_view()


def _create_order_integrity_routines() -> None:
    op.execute(
        """
        CREATE FUNCTION public.reject_order_total_change()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.total_amount IS DISTINCT FROM OLD.total_amount THEN
                RAISE EXCEPTION 'El importe del pedido ya registrado es inmutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_orders_total_immutable
            BEFORE UPDATE OF total_amount ON public.orders
            FOR EACH ROW EXECUTE FUNCTION public.reject_order_total_change()
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.enforce_order_item_creation_transaction()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            v_creation_xid BIGINT;
            v_order_status VARCHAR(16);
            v_order_confirmed TIMESTAMPTZ;
        BEGIN
            SELECT (o.xmin::TEXT)::BIGINT, o.status, o.confirmed_at
              INTO v_creation_xid, v_order_status, v_order_confirmed
              FROM public.orders AS o
             WHERE o.id = NEW.order_id FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Pedido % inexistente', NEW.order_id
                    USING ERRCODE = '23503';
            END IF;

            IF v_creation_xid <> (txid_current() % 4294967296)
               OR v_order_status <> 'REQUESTED' OR v_order_confirmed IS NOT NULL THEN
                RAISE EXCEPTION 'Las líneas deben registrarse junto con la cabecera'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_order_items_same_transaction
            BEFORE INSERT ON public.order_items
            FOR EACH ROW EXECUTE FUNCTION public.enforce_order_item_creation_transaction()
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.reject_order_item_change()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'No se permite alterar ni eliminar líneas registradas'
                USING ERRCODE = '23514';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_order_items_immutable
            BEFORE UPDATE OR DELETE ON public.order_items
            FOR EACH ROW EXECUTE FUNCTION public.reject_order_item_change()
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.check_order_items_total()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            v_order_id UUID;
            v_total NUMERIC;
            v_lines_total NUMERIC;
        BEGIN
            IF TG_TABLE_NAME = 'orders' THEN
                v_order_id := NEW.id;
            ELSE
                v_order_id := NEW.order_id;
            END IF;

            SELECT o.total_amount INTO v_total
              FROM public.orders AS o
             WHERE o.id = v_order_id FOR UPDATE;

            IF NOT FOUND THEN
                RETURN NULL;
            END IF;

            SELECT COALESCE(SUM(oi.quantity * oi.unit_price_snapshot), 0)
              INTO v_lines_total
              FROM public.order_items AS oi
             WHERE oi.order_id = v_order_id;

            IF v_lines_total <= 0 OR v_total <> v_lines_total THEN
                RAISE EXCEPTION
                    'Total del pedido % (%) distinto de sus líneas (%)',
                    v_order_id, v_total, v_lines_total
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ctr_orders_items_total
            AFTER INSERT ON public.orders
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION public.check_order_items_total()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ctr_order_items_total
            AFTER INSERT ON public.order_items
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION public.check_order_items_total()
        """
    )


def _create_stock_integrity_routines() -> None:
    op.execute(
        """
        CREATE FUNCTION public.reject_stock_movement_change()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Los movimientos de stock históricos son inmutables'
                USING ERRCODE = '23514';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_stock_movements_immutable
            BEFORE UPDATE OR DELETE ON public.stock_movements
            FOR EACH ROW EXECUTE FUNCTION public.reject_stock_movement_change()
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.check_order_stock_movement()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            v_product UUID;
            v_quantity INTEGER;
            v_order_status VARCHAR(16);
            v_confirmed_at TIMESTAMPTZ;
        BEGIN
            IF NEW.kind <> 'ORDER' THEN
                RETURN NULL;
            END IF;

            SELECT oi.product_id, oi.quantity, o.status, o.confirmed_at
              INTO v_product, v_quantity, v_order_status, v_confirmed_at
              FROM public.order_items AS oi
              JOIN public.orders AS o ON o.id = oi.order_id
             WHERE oi.id = NEW.order_item_id;

            IF NOT FOUND OR NEW.product_id IS DISTINCT FROM v_product
               OR NEW.quantity_delta <> -v_quantity
               OR v_order_status NOT IN ('CONFIRMED', 'CLOSED')
               OR v_confirmed_at IS NULL THEN
                RAISE EXCEPTION 'Movimiento de stock incompatible con pedido confirmado'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ctr_stock_movement_confirmed
            AFTER INSERT ON public.stock_movements
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION public.check_order_stock_movement()
        """
    )


def _create_payment_integrity_routines() -> None:
    op.execute(
        """
        CREATE FUNCTION public.validate_payment_insert()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            v_total NUMERIC(12,2);
            v_modality VARCHAR(12);
            v_paid NUMERIC;
            v_required NUMERIC;
        BEGIN
            SELECT o.total_amount, o.modality INTO v_total, v_modality
              FROM public.orders AS o
             WHERE o.id = NEW.order_id FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Pedido % inexistente', NEW.order_id
                    USING ERRCODE = '23503';
            END IF;

            IF NEW.kind = 'ADVANCE' THEN
                IF v_modality NOT IN ('PICKUP', 'DELIVERY') THEN
                    RAISE EXCEPTION 'La modalidad LOCAL no admite anticipo'
                        USING ERRCODE = '23514';
                END IF;
                v_required := CEIL(v_total * 50) / 100;
                IF NEW.amount <> v_required THEN
                    RAISE EXCEPTION 'El anticipo debe ser % y se recibió %',
                        v_required, NEW.amount USING ERRCODE = '23514';
                END IF;
            END IF;

            SELECT COALESCE(SUM(p.amount), 0) INTO v_paid
              FROM public.payments AS p
             WHERE p.order_id = NEW.order_id;

            IF v_paid + NEW.amount > v_total THEN
                RAISE EXCEPTION 'El pago supera el saldo pendiente del pedido %',
                    NEW.order_id USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_payments_validate_insert
            BEFORE INSERT ON public.payments
            FOR EACH ROW EXECUTE FUNCTION public.validate_payment_insert()
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.protect_payment_history()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'No se permite eliminar un pago registrado'
                    USING ERRCODE = '23514';
            END IF;

            IF (NEW.id, NEW.order_id, NEW.kind, NEW.amount, NEW.method_code,
                NEW.recorded_by_user_id, NEW.recorded_at, NEW.operation_request_id)
               IS DISTINCT FROM
               (OLD.id, OLD.order_id, OLD.kind, OLD.amount, OLD.method_code,
                OLD.recorded_by_user_id, OLD.recorded_at, OLD.operation_request_id) THEN
                RAISE EXCEPTION 'Los datos financieros del pago son inmutables'
                    USING ERRCODE = '23514';
            END IF;

            IF (NEW.refund_decision, NEW.refund_decided_by_user_id,
                NEW.refund_decided_at)
               IS NOT DISTINCT FROM
               (OLD.refund_decision, OLD.refund_decided_by_user_id,
                OLD.refund_decided_at) THEN
                RETURN NEW;
            END IF;

            IF OLD.kind <> 'ADVANCE' OR OLD.refund_decision IS NOT NULL
               OR NEW.refund_decision IS NULL
               OR NEW.refund_decided_by_user_id IS NULL
               OR NEW.refund_decided_at IS NULL THEN
                RAISE EXCEPTION 'La decisión del anticipo solo se registra una vez'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_payments_protect_history
            BEFORE UPDATE OR DELETE ON public.payments
            FOR EACH ROW EXECUTE FUNCTION public.protect_payment_history()
        """
    )


def _create_payment_summary_view() -> None:
    op.execute(
        """
        CREATE VIEW public.order_payment_summary AS
        SELECT
            o.id AS order_id,
            o.modality,
            o.total_amount,
            CASE WHEN o.modality IN ('PICKUP','DELIVERY')
                THEN (CEIL(o.total_amount * 50) / 100)::NUMERIC(12,2)
                ELSE 0::NUMERIC(12,2)
            END AS required_advance,
            CASE WHEN o.modality IN ('PICKUP','DELIVERY')
                THEN (o.total_amount - CEIL(o.total_amount * 50) / 100)::NUMERIC(12,2)
                ELSE o.total_amount
            END AS remaining_after_required_advance,
            COALESCE(SUM(p.amount) FILTER (WHERE p.kind = 'ADVANCE'), 0)::NUMERIC(12,2)
                AS recorded_advance,
            COALESCE(SUM(p.amount), 0)::NUMERIC(12,2) AS paid_total,
            (o.total_amount - COALESCE(SUM(p.amount), 0))::NUMERIC(12,2)
                AS balance_due
        FROM public.orders o
        LEFT JOIN public.payments p ON p.order_id = o.id
        GROUP BY o.id, o.modality, o.total_amount
        """
    )


def downgrade() -> None:
    """Remove all objects created by the initial revision."""

    op.execute("DROP VIEW IF EXISTS public.order_payment_summary")

    op.drop_table("fulfillments", schema=SCHEMA)
    op.drop_table("payments", schema=SCHEMA)
    op.drop_table("idempotency_requests", schema=SCHEMA)
    op.drop_table("kitchen_tickets", schema=SCHEMA)
    op.drop_table("stock_movements", schema=SCHEMA)
    op.drop_table("order_items", schema=SCHEMA)
    op.drop_table("orders", schema=SCHEMA)
    op.drop_table("restaurant_tables", schema=SCHEMA)
    op.drop_table("products", schema=SCHEMA)
    op.drop_table("categories", schema=SCHEMA)
    op.drop_table("auth_sessions", schema=SCHEMA)
    op.drop_table("user_roles", schema=SCHEMA)
    op.drop_table("roles", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)

    op.execute("DROP FUNCTION IF EXISTS public.protect_payment_history()")
    op.execute("DROP FUNCTION IF EXISTS public.validate_payment_insert()")
    op.execute("DROP FUNCTION IF EXISTS public.check_order_stock_movement()")
    op.execute("DROP FUNCTION IF EXISTS public.reject_stock_movement_change()")
    op.execute("DROP FUNCTION IF EXISTS public.check_order_items_total()")
    op.execute("DROP FUNCTION IF EXISTS public.reject_order_item_change()")
    op.execute("DROP FUNCTION IF EXISTS public.enforce_order_item_creation_transaction()")
    op.execute("DROP FUNCTION IF EXISTS public.reject_order_total_change()")
