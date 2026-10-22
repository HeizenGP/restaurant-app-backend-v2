"""Static correspondence checks for ORM metadata and the initial revision."""

import re
from pathlib import Path

import restaurant_app.db_models  # noqa: F401  # register mappings
from restaurant_app.core.database import Base

EXPECTED_COLUMNS = {
    "public.users": {
        "id",
        "display_name",
        "email",
        "password_hash",
        "is_active",
        "created_at",
    },
    "public.roles": {"code", "label"},
    "public.user_roles": {"user_id", "role_code", "assigned_at"},
    "public.auth_sessions": {
        "id",
        "kind",
        "user_id",
        "renewal_token_hash",
        "created_at",
        "expires_at",
        "revoked_at",
    },
    "public.categories": {"id", "name"},
    "public.products": {
        "id",
        "category_id",
        "name",
        "price",
        "stock_qty",
        "is_available",
    },
    "public.restaurant_tables": {
        "id",
        "code",
        "area_label",
        "is_occupied",
        "occupancy_started_at",
        "updated_at",
        "updated_by_user_id",
    },
    "public.orders": {
        "id",
        "modality",
        "channel",
        "status",
        "customer_user_id",
        "guest_session_id",
        "created_by_user_id",
        "table_id",
        "delivery_address",
        "contact_name",
        "contact_phone",
        "total_amount",
        "version",
        "created_at",
        "decided_by_user_id",
        "decided_at",
        "table_verified_at",
        "confirmed_by_user_id",
        "confirmed_at",
        "closed_by_user_id",
        "closed_at",
    },
    "public.order_items": {
        "id",
        "order_id",
        "product_id",
        "product_name_snapshot",
        "quantity",
        "unit_price_snapshot",
    },
    "public.stock_movements": {
        "id",
        "product_id",
        "kind",
        "quantity_delta",
        "order_item_id",
        "actor_user_id",
        "recorded_at",
    },
    "public.kitchen_tickets": {
        "id",
        "order_id",
        "status",
        "created_at",
        "started_at",
        "ready_at",
        "started_by_user_id",
        "ready_by_user_id",
    },
    "public.idempotency_requests": {
        "id",
        "actor_user_id",
        "actor_guest_session_id",
        "operation",
        "request_key",
        "request_hash",
        "result_order_id",
        "created_at",
        "expires_at",
        "completed_at",
    },
    "public.payments": {
        "id",
        "order_id",
        "kind",
        "amount",
        "method_code",
        "reference_code",
        "recorded_by_user_id",
        "recorded_at",
        "operation_request_id",
        "refund_decision",
        "refund_decided_by_user_id",
        "refund_decided_at",
    },
    "public.fulfillments": {
        "id",
        "order_id",
        "kind",
        "recorded_by_user_id",
        "recorded_at",
    },
}

EXPECTED_INDEXES = {
    "ux_users_email_ci",
    "ix_user_roles_role_code_user_id",
    "ix_sessions_user_expiry",
    "ix_products_category_available",
    "ix_orders_customer_created",
    "ix_orders_guest_created",
    "ix_orders_status_created",
    "ix_orders_table_id",
    "ix_order_items_product",
    "ux_stock_movements_order_item",
    "ix_stock_movements_product_recorded",
    "ix_kitchen_tickets_status_created",
    "ux_idempotency_user_request",
    "ux_idempotency_guest_request",
    "ix_idempotency_expiry",
    "ux_payments_one_advance_per_order",
    "ix_payments_order_recorded",
}

EXPECTED_FUNCTIONS = {
    "reject_order_total_change",
    "enforce_order_item_creation_transaction",
    "reject_order_item_change",
    "check_order_items_total",
    "reject_stock_movement_change",
    "check_order_stock_movement",
    "validate_payment_insert",
    "protect_payment_history",
}

EXPECTED_TRIGGERS = {
    "trg_orders_total_immutable",
    "trg_order_items_same_transaction",
    "trg_order_items_immutable",
    "ctr_orders_items_total",
    "ctr_order_items_total",
    "trg_stock_movements_immutable",
    "ctr_stock_movement_confirmed",
    "trg_payments_validate_insert",
    "trg_payments_protect_history",
}


def test_metadata_has_exact_approved_tables_and_columns() -> None:
    assert set(Base.metadata.tables) == set(EXPECTED_COLUMNS)

    for table_key, expected_columns in EXPECTED_COLUMNS.items():
        assert set(Base.metadata.tables[table_key].columns.keys()) == expected_columns


def test_metadata_has_all_named_indexes_and_restrictive_foreign_keys() -> None:
    indexes = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if index.name is not None
    }
    assert indexes == EXPECTED_INDEXES

    foreign_keys = [
        foreign_key for table in Base.metadata.tables.values() for foreign_key in table.foreign_keys
    ]
    assert foreign_keys
    assert all(foreign_key.ondelete == "RESTRICT" for foreign_key in foreign_keys)


def test_initial_revision_contains_all_postgresql_only_objects() -> None:
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "20261021_0001_initial_schema.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    functions = set(re.findall(r"CREATE FUNCTION public\.([a-z_]+)", migration))
    triggers = set(re.findall(r"CREATE (?:CONSTRAINT )?TRIGGER ([a-z_]+)", migration))

    assert functions == EXPECTED_FUNCTIONS
    assert triggers == EXPECTED_TRIGGERS
    assert "CREATE VIEW public.order_payment_summary AS" in migration
    assert "LEFT JOIN public.payments" in migration
    assert "GROUP BY o.id, o.modality, o.total_amount" in migration
    assert "CEIL(o.total_amount * 50) / 100" in migration


def test_order_item_transaction_guard_preserves_postgresql_xid_logic() -> None:
    repository_root = Path(__file__).parents[1]
    schema = (repository_root / "database" / "schema.sql").read_text(encoding="utf-8")
    correction = (
        repository_root / "alembic" / "versions" / "20261021_0002_harden_order_item_xid_guard.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | Sequence[str] | None = "20261021_0001"' in correction
    assert "CREATE OR REPLACE FUNCTION" in correction
    for definition in (schema, correction.split("def downgrade() -> None:", maxsplit=1)[0]):
        assert "v_creation_xid xid" in definition
        assert "SELECT o.xmin" in definition
        assert "pg_current_xact_id()::xid" in definition
        assert "txid_current()" not in definition
        assert "v_order_status <> 'REQUESTED'" in definition
        assert "v_order_confirmed IS NOT NULL" in definition
