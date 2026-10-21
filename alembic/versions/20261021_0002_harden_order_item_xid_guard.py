"""Use the typed PostgreSQL transaction ID API in the order-item guard.

Revision ID: 20261021_0002
Revises: 20261021_0001
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261021_0002"
down_revision: str | Sequence[str] | None = "20261021_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace the legacy txid arithmetic without changing the approved tables."""

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.enforce_order_item_creation_transaction()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            v_creation_xid xid;
            v_order_status VARCHAR(16);
            v_order_confirmed TIMESTAMPTZ;
        BEGIN
            SELECT o.xmin, o.status, o.confirmed_at
              INTO v_creation_xid, v_order_status, v_order_confirmed
              FROM public.orders AS o
             WHERE o.id = NEW.order_id FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Pedido % inexistente', NEW.order_id
                    USING ERRCODE = '23503';
            END IF;

            -- Bounded physical guard: CreateOrder must use one top-level transaction,
            -- without nested SAVEPOINTs or header UPDATEs before all line INSERTs.
            IF v_creation_xid <> pg_current_xact_id()::xid
               OR v_order_status <> 'REQUESTED' OR v_order_confirmed IS NOT NULL THEN
                RAISE EXCEPTION 'Las líneas deben registrarse junto con la cabecera'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    """Restore the function definition from the initial revision."""

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.enforce_order_item_creation_transaction()
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
