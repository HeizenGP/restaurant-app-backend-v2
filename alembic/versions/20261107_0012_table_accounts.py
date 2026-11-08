"""Add persistent table accounts and consolidated payments.

Revision ID: 20261107_0012
Revises: 20261107_0011

The migration is additive. Existing local orders remain intact; active orders are
attached to one open account per occupied table so a deployment does not lose an
in-progress service session.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261107_0012"
down_revision: str | Sequence[str] | None = "20261107_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "public"
TIMESTAMPTZ = postgresql.TIMESTAMP(timezone=True)
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "table_accounts",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("table_id", UUID, nullable=False),
        sa.Column("customer_user_id", UUID, nullable=True),
        sa.Column("guest_session_id", UUID, nullable=True),
        sa.Column("opened_by_user_id", UUID, nullable=True),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column(
            "opened_at", TIMESTAMPTZ, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("closed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("closed_by_user_id", UUID, nullable=True),
        sa.CheckConstraint("status IN ('OPEN', 'PAID')", name="ck_table_accounts_status"),
        sa.CheckConstraint(
            "num_nonnulls(customer_user_id, guest_session_id) <= 1",
            name="ck_table_accounts_single_customer",
        ),
        sa.CheckConstraint(
            "(status = 'OPEN' AND closed_at IS NULL) OR "
            "(status = 'PAID' AND closed_at IS NOT NULL)",
            name="ck_table_accounts_closed_state",
        ),
        sa.ForeignKeyConstraint(["table_id"], ["public.restaurant_tables.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_user_id"], ["public.users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["guest_session_id"], ["public.auth_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["opened_by_user_id"], ["public.users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["public.users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ux_table_accounts_one_open_per_table",
        "table_accounts",
        ["table_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'OPEN'"),
    )
    op.create_index(
        "ix_table_accounts_table_opened",
        "table_accounts",
        ["table_id", sa.text("opened_at DESC")],
        schema=SCHEMA,
    )

    op.add_column("orders", sa.Column("table_account_id", UUID, nullable=True), schema=SCHEMA)
    op.create_foreign_key(
        "orders_table_account_id_fkey",
        "orders",
        "table_accounts",
        ["table_account_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_orders_table_account_id",
        "orders",
        ["table_account_id"],
        schema=SCHEMA,
        postgresql_where=sa.text("table_account_id IS NOT NULL"),
    )

    op.add_column(
        "idempotency_requests",
        sa.Column("result_table_account_id", UUID, nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "idempotency_requests_result_table_account_id_fkey",
        "idempotency_requests",
        "table_accounts",
        ["result_table_account_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )

    # Preserve every active visit already in production without touching closed history.
    op.execute(
        """
        INSERT INTO public.table_accounts
            (table_id, customer_user_id, guest_session_id, opened_by_user_id, opened_at)
        SELECT DISTINCT ON (o.table_id)
            o.table_id, o.customer_user_id, o.guest_session_id, o.created_by_user_id,
            COALESCE(t.occupancy_started_at, o.created_at)
        FROM public.orders AS o
        JOIN public.restaurant_tables AS t ON t.id = o.table_id
        WHERE o.modality = 'LOCAL'
          AND o.status IN ('REQUESTED', 'APPROVED', 'CONFIRMED')
        ORDER BY o.table_id, o.created_at
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE public.orders AS o
           SET table_account_id = a.id
          FROM public.table_accounts AS a
         WHERE a.table_id = o.table_id
           AND a.status = 'OPEN'
           AND o.modality = 'LOCAL'
           AND o.status IN ('REQUESTED', 'APPROVED', 'CONFIRMED')
        """
    )

    op.add_column("payments", sa.Column("table_account_id", UUID, nullable=True), schema=SCHEMA)
    op.create_foreign_key(
        "payments_table_account_id_fkey",
        "payments",
        "table_accounts",
        ["table_account_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
    op.alter_column("payments", "order_id", existing_type=UUID, nullable=True, schema=SCHEMA)
    op.create_check_constraint(
        "ck_payments_single_target",
        "payments",
        "num_nonnulls(order_id, table_account_id) = 1",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_payments_table_account_recorded",
        "payments",
        ["table_account_id", "recorded_at"],
        schema=SCHEMA,
        postgresql_where=sa.text("table_account_id IS NOT NULL"),
    )

    _replace_payment_integrity_functions()
    _normalize_existing_foreign_key_names()


def _normalize_existing_foreign_key_names() -> None:
    """Align the pre-existing address FK with the metadata naming convention."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                 WHERE conname = 'fk_user_addresses_user_id'
                   AND conrelid = 'public.user_addresses'::regclass
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_constraint
                 WHERE conname = 'user_addresses_user_id_fkey'
                   AND conrelid = 'public.user_addresses'::regclass
            ) THEN
                ALTER TABLE public.user_addresses
                    RENAME CONSTRAINT fk_user_addresses_user_id
                    TO user_addresses_user_id_fkey;
            END IF;
        END $$
        """
    )


def _restore_existing_foreign_key_names() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                 WHERE conname = 'user_addresses_user_id_fkey'
                   AND conrelid = 'public.user_addresses'::regclass
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_constraint
                 WHERE conname = 'fk_user_addresses_user_id'
                   AND conrelid = 'public.user_addresses'::regclass
            ) THEN
                ALTER TABLE public.user_addresses
                    RENAME CONSTRAINT user_addresses_user_id_fkey
                    TO fk_user_addresses_user_id;
            END IF;
        END $$
        """
    )


def _normalize_table_account_foreign_key_names() -> None:
    """Allow a safe rollback of local databases created by an earlier draft."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_orders_table_account_id_table_accounts')
               AND NOT EXISTS (SELECT 1 FROM pg_constraint
                               WHERE conname = 'orders_table_account_id_fkey') THEN
                ALTER TABLE public.orders
                    RENAME CONSTRAINT fk_orders_table_account_id_table_accounts
                    TO orders_table_account_id_fkey;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_payments_table_account_id_table_accounts')
               AND NOT EXISTS (SELECT 1 FROM pg_constraint
                               WHERE conname = 'payments_table_account_id_fkey') THEN
                ALTER TABLE public.payments
                    RENAME CONSTRAINT fk_payments_table_account_id_table_accounts
                    TO payments_table_account_id_fkey;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_constraint
                        WHERE conname =
                            'fk_idempotency_requests_result_table_account_id_table_accounts')
               AND NOT EXISTS (SELECT 1 FROM pg_constraint
                               WHERE conname =
                                   'idempotency_requests_result_table_account_id_fkey') THEN
                ALTER TABLE public.idempotency_requests
                    RENAME CONSTRAINT
                        fk_idempotency_requests_result_table_account_id_table_accounts
                    TO idempotency_requests_result_table_account_id_fkey;
            END IF;
        END $$
        """
    )


def _replace_payment_integrity_functions() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.validate_payment_insert()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            v_total NUMERIC(12,2);
            v_paid NUMERIC(12,2);
            v_modality VARCHAR(12);
            v_required NUMERIC(12,2);
            v_account_status VARCHAR(12);
        BEGIN
            IF NEW.order_id IS NOT NULL THEN
                SELECT o.total_amount, o.modality INTO v_total, v_modality
                  FROM public.orders AS o
                 WHERE o.id = NEW.order_id FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Pedido % inexistente', NEW.order_id USING ERRCODE = '23503';
                END IF;
                IF NEW.kind = 'ADVANCE' THEN
                    IF v_modality NOT IN ('PICKUP', 'DELIVERY') THEN
                        RAISE EXCEPTION 'La modalidad LOCAL no admite anticipo' USING ERRCODE = '23514';
                    END IF;
                    v_required := CEIL(v_total * 50) / 100;
                    IF NEW.amount <> v_required THEN
                        RAISE EXCEPTION 'El anticipo debe ser % y se recibió %', v_required, NEW.amount
                            USING ERRCODE = '23514';
                    END IF;
                END IF;
                SELECT COALESCE(SUM(p.amount), 0) INTO v_paid
                  FROM public.payments AS p WHERE p.order_id = NEW.order_id;
            ELSE
                SELECT a.status INTO v_account_status
                  FROM public.table_accounts AS a
                 WHERE a.id = NEW.table_account_id
                 FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Cuenta de mesa % inexistente', NEW.table_account_id
                        USING ERRCODE = '23503';
                END IF;
                IF v_account_status <> 'OPEN' OR NEW.kind <> 'COLLECTION' THEN
                    RAISE EXCEPTION 'La cuenta no admite el pago solicitado' USING ERRCODE = '23514';
                END IF;
                SELECT COALESCE(SUM(o.total_amount), 0) INTO v_total
                  FROM public.orders AS o
                 WHERE o.table_account_id = NEW.table_account_id;
                SELECT COALESCE(SUM(p.amount), 0) INTO v_paid
                  FROM public.payments AS p
                 WHERE p.table_account_id = NEW.table_account_id;
                SELECT v_paid + COALESCE(SUM(p.amount), 0) INTO v_paid
                  FROM public.payments AS p
                  JOIN public.orders AS o ON o.id = p.order_id
                 WHERE o.table_account_id = NEW.table_account_id;
            END IF;
            IF v_paid + NEW.amount > v_total THEN
                RAISE EXCEPTION 'El pago supera el saldo pendiente' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.protect_payment_history()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'No se permite eliminar un pago registrado' USING ERRCODE = '23514';
            END IF;
            IF (NEW.id, NEW.order_id, NEW.table_account_id, NEW.kind, NEW.amount,
                NEW.method_code, NEW.reference_code, NEW.recorded_by_user_id,
                NEW.recorded_at, NEW.operation_request_id)
               IS DISTINCT FROM
               (OLD.id, OLD.order_id, OLD.table_account_id, OLD.kind, OLD.amount,
                OLD.method_code, OLD.reference_code, OLD.recorded_by_user_id,
                OLD.recorded_at, OLD.operation_request_id) THEN
                RAISE EXCEPTION 'Los datos financieros del pago son inmutables' USING ERRCODE = '23514';
            END IF;
            IF (NEW.refund_decision, NEW.refund_decided_by_user_id, NEW.refund_decided_at)
               IS NOT DISTINCT FROM
               (OLD.refund_decision, OLD.refund_decided_by_user_id, OLD.refund_decided_at) THEN
                RETURN NEW;
            END IF;
            IF OLD.kind <> 'ADVANCE' OR OLD.refund_decision IS NOT NULL
               OR NEW.refund_decision IS NULL OR NEW.refund_decided_by_user_id IS NULL
               OR NEW.refund_decided_at IS NULL THEN
                RAISE EXCEPTION 'La decisión del anticipo solo se registra una vez'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    # Downgrade is intentionally guarded: consolidated payments cannot be represented
    # by the previous schema without data loss.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.payments WHERE table_account_id IS NOT NULL) THEN
                RAISE EXCEPTION 'No se puede revertir: existen cobros consolidados de mesa';
            END IF;
        END $$
        """
    )
    _normalize_table_account_foreign_key_names()
    _restore_existing_foreign_key_names()
    _restore_legacy_payment_integrity_functions()
    op.drop_index("ix_payments_table_account_recorded", table_name="payments", schema=SCHEMA)
    op.drop_constraint("ck_payments_single_target", "payments", schema=SCHEMA, type_="check")
    op.drop_constraint(
        "payments_table_account_id_fkey", "payments", schema=SCHEMA, type_="foreignkey"
    )
    op.drop_column("payments", "table_account_id", schema=SCHEMA)
    op.alter_column("payments", "order_id", existing_type=UUID, nullable=False, schema=SCHEMA)
    op.drop_index("ix_orders_table_account_id", table_name="orders", schema=SCHEMA)
    op.drop_constraint(
        "idempotency_requests_result_table_account_id_fkey",
        "idempotency_requests",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_column("idempotency_requests", "result_table_account_id", schema=SCHEMA)
    op.drop_constraint("orders_table_account_id_fkey", "orders", schema=SCHEMA, type_="foreignkey")
    op.drop_column("orders", "table_account_id", schema=SCHEMA)
    op.drop_index("ix_table_accounts_table_opened", table_name="table_accounts", schema=SCHEMA)
    op.drop_index(
        "ux_table_accounts_one_open_per_table", table_name="table_accounts", schema=SCHEMA
    )
    op.drop_table("table_accounts", schema=SCHEMA)


def _restore_legacy_payment_integrity_functions() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.validate_payment_insert()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            v_total NUMERIC(12,2);
            v_modality VARCHAR(12);
            v_paid NUMERIC;
            v_required NUMERIC;
        BEGIN
            SELECT o.total_amount, o.modality INTO v_total, v_modality
              FROM public.orders AS o WHERE o.id = NEW.order_id FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Pedido % inexistente', NEW.order_id USING ERRCODE = '23503';
            END IF;
            IF NEW.kind = 'ADVANCE' THEN
                IF v_modality NOT IN ('PICKUP', 'DELIVERY') THEN
                    RAISE EXCEPTION 'La modalidad LOCAL no admite anticipo' USING ERRCODE = '23514';
                END IF;
                v_required := CEIL(v_total * 50) / 100;
                IF NEW.amount <> v_required THEN
                    RAISE EXCEPTION 'El anticipo debe ser % y se recibió %', v_required, NEW.amount
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            SELECT COALESCE(SUM(p.amount), 0) INTO v_paid
              FROM public.payments AS p WHERE p.order_id = NEW.order_id;
            IF v_paid + NEW.amount > v_total THEN
                RAISE EXCEPTION 'El pago supera el saldo pendiente del pedido %', NEW.order_id
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.protect_payment_history()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'No se permite eliminar un pago registrado' USING ERRCODE = '23514';
            END IF;
            IF (NEW.id, NEW.order_id, NEW.kind, NEW.amount, NEW.method_code,
                NEW.recorded_by_user_id, NEW.recorded_at, NEW.operation_request_id)
               IS DISTINCT FROM
               (OLD.id, OLD.order_id, OLD.kind, OLD.amount, OLD.method_code,
                OLD.recorded_by_user_id, OLD.recorded_at, OLD.operation_request_id) THEN
                RAISE EXCEPTION 'Los datos financieros del pago son inmutables' USING ERRCODE = '23514';
            END IF;
            IF (NEW.refund_decision, NEW.refund_decided_by_user_id, NEW.refund_decided_at)
               IS NOT DISTINCT FROM
               (OLD.refund_decision, OLD.refund_decided_by_user_id, OLD.refund_decided_at) THEN
                RETURN NEW;
            END IF;
            IF OLD.kind <> 'ADVANCE' OR OLD.refund_decision IS NOT NULL
               OR NEW.refund_decision IS NULL OR NEW.refund_decided_by_user_id IS NULL
               OR NEW.refund_decided_at IS NULL THEN
                RAISE EXCEPTION 'La decisión del anticipo solo se registra una vez'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
