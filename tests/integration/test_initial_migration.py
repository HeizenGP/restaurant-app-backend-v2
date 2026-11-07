"""PostgreSQL integration tests for the ETAPA 07 initial migration.

Run these tests against a disposable database after ``alembic upgrade head`` by
setting ``TEST_DATABASE_DSN``. The database name must end in ``_test`` or
``_stage07``, and ``ALLOW_DESTRUCTIVE_TEST_DATABASE`` must equal that exact name.
The module is skipped when the DSN is not defined so the default unit-test suite
remains self-contained.
"""

import os
import re
from collections.abc import AsyncIterator
from decimal import Decimal
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

APP_TABLES = {
    "auth_sessions",
    "categories",
    "fulfillments",
    "idempotency_requests",
    "kitchen_tickets",
    "order_items",
    "orders",
    "password_reset_tokens",
    "payments",
    "products",
    "restaurant_tables",
    "roles",
    "stock_movements",
    "user_roles",
    "users",
}

EXPLICIT_INDEXES = {
    "ix_idempotency_expiry",
    "ix_kitchen_tickets_status_created",
    "ix_order_items_product",
    "ix_orders_customer_created",
    "ix_orders_guest_created",
    "ix_orders_status_created",
    "ix_orders_table_id",
    "ix_payments_order_recorded",
    "ix_password_reset_tokens_user_created",
    "ix_products_category_available",
    "ix_sessions_user_expiry",
    "ix_stock_movements_product_recorded",
    "ix_user_roles_role_code_user_id",
    "ux_idempotency_guest_request",
    "ux_idempotency_user_request",
    "ux_payments_one_advance_per_order",
    "ux_stock_movements_order_item",
    "ux_users_email_ci",
}

DATABASE_FUNCTIONS = {
    "check_order_items_total",
    "check_order_stock_movement",
    "enforce_order_item_creation_transaction",
    "protect_payment_history",
    "reject_order_item_change",
    "reject_order_total_change",
    "reject_stock_movement_change",
    "validate_payment_insert",
}

DATABASE_TRIGGERS = {
    "ctr_order_items_total",
    "ctr_orders_items_total",
    "ctr_stock_movement_confirmed",
    "trg_order_items_immutable",
    "trg_order_items_same_transaction",
    "trg_orders_total_immutable",
    "trg_payments_protect_history",
    "trg_payments_validate_insert",
    "trg_stock_movements_immutable",
}

ROLE_CODES = {
    "ADMIN",
    "CASHIER",
    "CUSTOMER",
    "KITCHEN",
    "SUPER_ADMIN",
    "WAITER",
}

MUTABLE_TABLES = (
    "fulfillments",
    "payments",
    "idempotency_requests",
    "kitchen_tickets",
    "stock_movements",
    "order_items",
    "orders",
    "restaurant_tables",
    "products",
    "categories",
    "auth_sessions",
    "password_reset_tokens",
    "user_roles",
    "users",
)

DISPOSABLE_DATABASE_NAME = re.compile(r"^[a-z0-9][a-z0-9_]*(?:_test|_stage07)$")
ALEMBIC_HEAD = "20261106_0007"


def _test_database_target() -> tuple[str, str]:
    value = os.getenv("TEST_DATABASE_DSN")
    if not value:
        pytest.skip("TEST_DATABASE_DSN is not defined")

    asyncpg_dsn = value.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlsplit(asyncpg_dsn)
    database_name = unquote(parsed.path.removeprefix("/")).casefold()
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or "/" in database_name
        or DISPOSABLE_DATABASE_NAME.fullmatch(database_name) is None
    ):
        pytest.fail(
            "TEST_DATABASE_DSN must use PostgreSQL and a disposable database name "
            "ending in '_test' or '_stage07'"
        )

    destructive_authorization = os.getenv("ALLOW_DESTRUCTIVE_TEST_DATABASE", "").strip()
    if destructive_authorization != database_name:
        pytest.fail("ALLOW_DESTRUCTIVE_TEST_DATABASE must equal the exact disposable database name")
    return asyncpg_dsn, database_name


async def _clean_database(connection: asyncpg.Connection) -> None:
    qualified_tables = ", ".join(f"public.{name}" for name in MUTABLE_TABLES)
    await connection.execute(f"TRUNCATE TABLE {qualified_tables} RESTART IDENTITY CASCADE")


@pytest_asyncio.fixture
async def database() -> AsyncIterator[asyncpg.Connection]:
    database_dsn, authorized_database = _test_database_target()
    connection = await asyncpg.connect(database_dsn)
    try:
        connected_database = await connection.fetchval("SELECT current_database()")
        if connected_database != authorized_database:
            pytest.fail("connected database does not match the explicitly authorized test database")
        migrated = await connection.fetchval("SELECT to_regclass('public.alembic_version')")
        if migrated is None:
            pytest.fail("TEST_DATABASE_DSN must point to a database migrated to Alembic head")
        applied_revisions = {
            row["version_num"]
            for row in await connection.fetch("SELECT version_num FROM public.alembic_version")
        }
        if applied_revisions != {ALEMBIC_HEAD}:
            pytest.fail("TEST_DATABASE_DSN must point to the exact Alembic head")
        await _clean_database(connection)
        yield connection
        await _clean_database(connection)
    finally:
        await connection.close()


async def _create_user(connection: asyncpg.Connection, *, suffix: str = "actor") -> UUID:
    return await connection.fetchval(
        """
        INSERT INTO public.users (display_name, email, password_hash)
        VALUES ($1, $2, 'integration-test-hash')
        RETURNING id
        """,
        f"Integration {suffix}",
        f"{suffix}@integration.test",
    )


async def _create_product(
    connection: asyncpg.Connection,
    *,
    suffix: str = "main",
    stock_qty: int = 20,
) -> UUID:
    category_id = await connection.fetchval(
        """
        INSERT INTO public.categories (name)
        VALUES ($1)
        RETURNING id
        """,
        f"Category {suffix}",
    )
    return await connection.fetchval(
        """
        INSERT INTO public.products (category_id, name, price, stock_qty)
        VALUES ($1, $2, 10.00, $3)
        RETURNING id
        """,
        category_id,
        f"Product {suffix}",
        stock_qty,
    )


async def _create_requested_order(
    connection: asyncpg.Connection,
    *,
    actor_id: UUID,
    product_id: UUID,
    total: Decimal,
    quantity: int = 1,
    unit_price: Decimal | None = None,
) -> tuple[UUID, UUID]:
    line_price = unit_price if unit_price is not None else total
    async with connection.transaction():
        order_id = await connection.fetchval(
            """
            INSERT INTO public.orders (
                modality,
                channel,
                created_by_user_id,
                total_amount
            )
            VALUES ('PICKUP', 'PHONE', $1, $2)
            RETURNING id
            """,
            actor_id,
            total,
        )
        item_id = await connection.fetchval(
            """
            INSERT INTO public.order_items (
                order_id,
                product_id,
                product_name_snapshot,
                quantity,
                unit_price_snapshot
            )
            VALUES ($1, $2, 'Integration product', $3, $4)
            RETURNING id
            """,
            order_id,
            product_id,
            quantity,
            line_price,
        )
    return order_id, item_id


async def _create_idempotency_request(
    connection: asyncpg.Connection,
    *,
    actor_id: UUID,
    request_key: str,
) -> UUID:
    return await connection.fetchval(
        """
        INSERT INTO public.idempotency_requests (
            actor_user_id,
            operation,
            request_key,
            request_hash,
            expires_at
        )
        VALUES ($1, 'REGISTER_PAYMENT', $2, $3, CURRENT_TIMESTAMP + INTERVAL '1 hour')
        RETURNING id
        """,
        actor_id,
        request_key,
        "a" * 64,
    )


async def test_initial_migration_installs_the_exact_approved_objects(
    database: asyncpg.Connection,
) -> None:
    tables = await database.fetch(
        """
        SELECT c.relname
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
        """
    )
    table_names = {row["relname"] for row in tables}
    assert table_names == APP_TABLES | {"alembic_version"}

    explicit_indexes = await database.fetch(
        """
        SELECT index_class.relname
        FROM pg_catalog.pg_index AS index_data
        JOIN pg_catalog.pg_class AS index_class
          ON index_class.oid = index_data.indexrelid
        JOIN pg_catalog.pg_class AS table_class
          ON table_class.oid = index_data.indrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = table_class.relnamespace
        LEFT JOIN pg_catalog.pg_constraint AS constraint_data
          ON constraint_data.conindid = index_data.indexrelid
        WHERE namespace.nspname = 'public' AND constraint_data.oid IS NULL
        """
    )
    assert {row["relname"] for row in explicit_indexes} == EXPLICIT_INDEXES

    functions = await database.fetch(
        """
        SELECT procedure.proname
        FROM pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = procedure.pronamespace
        WHERE namespace.nspname = 'public' AND procedure.prokind = 'f'
        """
    )
    assert {row["proname"] for row in functions} == DATABASE_FUNCTIONS

    triggers = await database.fetch(
        """
        SELECT trigger_data.tgname
        FROM pg_catalog.pg_trigger AS trigger_data
        JOIN pg_catalog.pg_class AS table_class
          ON table_class.oid = trigger_data.tgrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = table_class.relnamespace
        WHERE namespace.nspname = 'public' AND NOT trigger_data.tgisinternal
        """
    )
    assert {row["tgname"] for row in triggers} == DATABASE_TRIGGERS

    views = await database.fetch(
        """
        SELECT c.relname
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'v'
        """
    )
    assert {row["relname"] for row in views} == {"order_payment_summary"}

    roles = await database.fetch("SELECT code FROM public.roles")
    assert {row["code"] for row in roles} == ROLE_CODES
    assert await database.fetchval("SELECT version_num FROM public.alembic_version") == ALEMBIC_HEAD


async def test_order_header_and_lines_share_a_transaction_and_total_is_deferred(
    database: asyncpg.Connection,
) -> None:
    actor_id = await _create_user(database)
    product_id = await _create_product(database)

    order_id, item_id = await _create_requested_order(
        database,
        actor_id=actor_id,
        product_id=product_id,
        total=Decimal("20.00"),
        quantity=2,
        unit_price=Decimal("10.00"),
    )
    assert await database.fetchval(
        "SELECT total_amount FROM public.orders WHERE id = $1", order_id
    ) == Decimal("20.00")
    assert (
        await database.fetchval("SELECT quantity FROM public.order_items WHERE id = $1", item_id)
        == 2
    )

    with pytest.raises(asyncpg.CheckViolationError, match="distinto de sus líneas"):
        async with database.transaction():
            await database.execute(
                """
                INSERT INTO public.orders (
                    modality,
                    channel,
                    created_by_user_id,
                    total_amount
                )
                VALUES ('PICKUP', 'PHONE', $1, 11.00)
                """,
                actor_id,
            )


async def test_order_and_line_financial_data_are_immutable(
    database: asyncpg.Connection,
) -> None:
    actor_id = await _create_user(database)
    product_id = await _create_product(database)
    second_product_id = await _create_product(database, suffix="second")
    order_id, item_id = await _create_requested_order(
        database,
        actor_id=actor_id,
        product_id=product_id,
        total=Decimal("10.00"),
    )

    with pytest.raises(asyncpg.CheckViolationError, match="importe del pedido"):
        await database.execute(
            "UPDATE public.orders SET total_amount = 12.00 WHERE id = $1",
            order_id,
        )

    with pytest.raises(asyncpg.CheckViolationError, match="alterar ni eliminar líneas"):
        await database.execute(
            "UPDATE public.order_items SET quantity = 2 WHERE id = $1",
            item_id,
        )

    with pytest.raises(asyncpg.CheckViolationError, match="alterar ni eliminar líneas"):
        await database.execute("DELETE FROM public.order_items WHERE id = $1", item_id)

    with pytest.raises(asyncpg.CheckViolationError, match="junto con la cabecera"):
        await database.execute(
            """
            INSERT INTO public.order_items (
                order_id,
                product_id,
                product_name_snapshot,
                quantity,
                unit_price_snapshot
            )
            VALUES ($1, $2, 'Late product', 1, 1.00)
            """,
            order_id,
            second_product_id,
        )


async def test_stock_is_nonnegative_and_order_movements_require_confirmation(
    database: asyncpg.Connection,
) -> None:
    actor_id = await _create_user(database)
    product_id = await _create_product(database)
    order_id, item_id = await _create_requested_order(
        database,
        actor_id=actor_id,
        product_id=product_id,
        total=Decimal("20.00"),
        quantity=2,
        unit_price=Decimal("10.00"),
    )

    with pytest.raises(asyncpg.CheckViolationError, match="products_stock_nonnegative"):
        await database.execute(
            "UPDATE public.products SET stock_qty = -1 WHERE id = $1",
            product_id,
        )

    with pytest.raises(
        asyncpg.CheckViolationError,
        match="Movimiento de stock incompatible con pedido confirmado",
    ):
        async with database.transaction():
            await database.execute(
                """
                INSERT INTO public.stock_movements (
                    product_id,
                    kind,
                    quantity_delta,
                    order_item_id,
                    actor_user_id
                )
                VALUES ($1, 'ORDER', -2, $2, $3)
                """,
                product_id,
                item_id,
                actor_id,
            )

    await database.execute(
        """
        UPDATE public.orders
        SET status = 'CONFIRMED',
            confirmed_by_user_id = $1,
            confirmed_at = CURRENT_TIMESTAMP
        WHERE id = $2
        """,
        actor_id,
        order_id,
    )

    async with database.transaction():
        movement_id = await database.fetchval(
            """
            INSERT INTO public.stock_movements (
                product_id,
                kind,
                quantity_delta,
                order_item_id,
                actor_user_id
            )
            VALUES ($1, 'ORDER', -2, $2, $3)
            RETURNING id
            """,
            product_id,
            item_id,
            actor_id,
        )

    with pytest.raises(asyncpg.CheckViolationError, match="históricos son inmutables"):
        await database.execute(
            "UPDATE public.stock_movements SET quantity_delta = -1 WHERE id = $1",
            movement_id,
        )


async def test_foreign_keys_and_kitchen_state_are_enforced(
    database: asyncpg.Connection,
) -> None:
    actor_id = await _create_user(database)

    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await database.execute(
            """
            INSERT INTO public.products (category_id, name, price, stock_qty)
            VALUES ($1, 'Orphan product', 10.00, 1)
            """,
            uuid4(),
        )

    product_id = await _create_product(database)
    order_id, _ = await _create_requested_order(
        database,
        actor_id=actor_id,
        product_id=product_id,
        total=Decimal("10.00"),
    )

    with pytest.raises(asyncpg.CheckViolationError, match="kitchen_tickets_state_fields"):
        await database.execute(
            """
            INSERT INTO public.kitchen_tickets (order_id, status)
            VALUES ($1, 'PREPARING')
            """,
            order_id,
        )

    ticket_id = await database.fetchval(
        """
        INSERT INTO public.kitchen_tickets (order_id, status)
        VALUES ($1, 'RECEIVED')
        RETURNING id
        """,
        order_id,
    )
    assert ticket_id is not None


async def test_advance_rounds_up_to_exactly_half_and_payment_history_is_immutable(
    database: asyncpg.Connection,
) -> None:
    actor_id = await _create_user(database)
    product_id = await _create_product(database)
    order_id, _ = await _create_requested_order(
        database,
        actor_id=actor_id,
        product_id=product_id,
        total=Decimal("10.01"),
    )

    wrong_request_id = await _create_idempotency_request(
        database,
        actor_id=actor_id,
        request_key="wrong-advance",
    )
    with pytest.raises(asyncpg.CheckViolationError, match=r"El anticipo debe ser 5\.01"):
        await database.execute(
            """
            INSERT INTO public.payments (
                order_id,
                kind,
                amount,
                method_code,
                recorded_by_user_id,
                operation_request_id
            )
            VALUES ($1, 'ADVANCE', 5.00, 'CASH', $2, $3)
            """,
            order_id,
            actor_id,
            wrong_request_id,
        )

    advance_request_id = await _create_idempotency_request(
        database,
        actor_id=actor_id,
        request_key="exact-advance",
    )
    payment_id = await database.fetchval(
        """
        INSERT INTO public.payments (
            order_id,
            kind,
            amount,
            method_code,
            recorded_by_user_id,
            operation_request_id
        )
        VALUES ($1, 'ADVANCE', 5.01, 'CASH', $2, $3)
        RETURNING id
        """,
        order_id,
        actor_id,
        advance_request_id,
    )

    with pytest.raises(asyncpg.UniqueViolationError, match="operation_request_id"):
        await database.execute(
            """
            INSERT INTO public.payments (
                order_id,
                kind,
                amount,
                method_code,
                recorded_by_user_id,
                operation_request_id
            )
            VALUES ($1, 'COLLECTION', 5.00, 'EFECTIVO', $2, $3)
            """,
            order_id,
            actor_id,
            advance_request_id,
        )

    summary = await database.fetchrow(
        """
        SELECT required_advance, remaining_after_required_advance, paid_total, balance_due
        FROM public.order_payment_summary
        WHERE order_id = $1
        """,
        order_id,
    )
    assert summary is not None
    assert tuple(summary) == (
        Decimal("5.01"),
        Decimal("5.00"),
        Decimal("5.01"),
        Decimal("5.00"),
    )

    excess_request_id = await _create_idempotency_request(
        database,
        actor_id=actor_id,
        request_key="excess-collection",
    )
    with pytest.raises(asyncpg.CheckViolationError, match="supera el saldo pendiente"):
        await database.execute(
            """
            INSERT INTO public.payments (
                order_id,
                kind,
                amount,
                method_code,
                recorded_by_user_id,
                operation_request_id
            )
            VALUES ($1, 'COLLECTION', 5.01, 'EFECTIVO', $2, $3)
            """,
            order_id,
            actor_id,
            excess_request_id,
        )

    with pytest.raises(asyncpg.CheckViolationError, match=r"datos financieros.*inmutables"):
        await database.execute(
            "UPDATE public.payments SET amount = 5.00 WHERE id = $1",
            payment_id,
        )

    with pytest.raises(asyncpg.CheckViolationError, match="eliminar un pago"):
        await database.execute("DELETE FROM public.payments WHERE id = $1", payment_id)


async def test_order_accepts_only_one_advance_with_distinct_idempotency_requests(
    database: asyncpg.Connection,
) -> None:
    actor_id = await _create_user(database, suffix="single-advance")
    product_id = await _create_product(database, suffix="single-advance")
    order_id, _ = await _create_requested_order(
        database,
        actor_id=actor_id,
        product_id=product_id,
        total=Decimal("10.00"),
    )
    first_request_id = await _create_idempotency_request(
        database,
        actor_id=actor_id,
        request_key="first-independent-advance",
    )
    second_request_id = await _create_idempotency_request(
        database,
        actor_id=actor_id,
        request_key="second-independent-advance",
    )

    await database.execute(
        """
        INSERT INTO public.payments (
            order_id,
            kind,
            amount,
            method_code,
            recorded_by_user_id,
            operation_request_id
        )
        VALUES ($1, 'ADVANCE', 5.00, 'CASH', $2, $3)
        """,
        order_id,
        actor_id,
        first_request_id,
    )

    with pytest.raises(
        asyncpg.UniqueViolationError,
        match="ux_payments_one_advance_per_order",
    ):
        await database.execute(
            """
            INSERT INTO public.payments (
                order_id,
                kind,
                amount,
                method_code,
                recorded_by_user_id,
                operation_request_id
            )
            VALUES ($1, 'ADVANCE', 5.00, 'CASH', $2, $3)
            """,
            order_id,
            actor_id,
            second_request_id,
        )
