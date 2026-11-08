"""08.07 confirmation, rollback and concurrency on an isolated PostgreSQL database."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from decimal import Decimal
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

import asyncpg
import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from restaurant_app.core.config import Settings
from restaurant_app.main import create_app
from restaurant_app.modules.m01_access.adapters.outbound.password_hasher import (
    Argon2PasswordHasher,
)
from tests.integration.test_initial_migration import _test_database_target

pytest_plugins = ("tests.integration.test_initial_migration",)
pytestmark = pytest.mark.integration

JWT_SECRET = "m04-confirm-integration-jwt-secret-over-32-characters"
ACTOR_PASSWORD = "m04-confirm-integration-password"


def build_test_application() -> FastAPI:
    authorized_dsn, authorized_database = _test_database_target()
    target = urlsplit(authorized_dsn)
    if target.hostname is None or target.username is None or target.password is None:
        pytest.fail("TEST_DATABASE_DSN must include host, user, and password")
    application = create_app(
        Settings(
            _env_file=None,
            environment="test",
            postgres_host=target.hostname,
            postgres_port=target.port or 5432,
            postgres_db=authorized_database,
            postgres_user=unquote(target.username),
            postgres_password=unquote(target.password),
            jwt_secret=JWT_SECRET,
            cors_origins=[],
        )
    )
    if application.state.database.engine.url.database != authorized_database:
        pytest.fail("HTTP test target differs from the authorized disposable database")
    return application


@contextmanager
def api_client() -> Iterator[TestClient]:
    with TestClient(build_test_application()) as client:
        yield client


@asynccontextmanager
async def async_clients() -> AsyncIterator[tuple[httpx.AsyncClient, httpx.AsyncClient]]:
    application = build_test_application()
    try:
        async with (
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application), base_url="http://testserver"
            ) as first,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application), base_url="http://testserver"
            ) as second,
        ):
            yield first, second
    finally:
        await application.state.database.dispose()


async def actor(database: asyncpg.Connection, role: str) -> tuple[UUID, str]:
    email = f"{role.lower()}-{uuid4()}@example.test"
    user_id = await database.fetchval(
        "INSERT INTO public.users(display_name,email,password_hash) VALUES($1,$2,$3) RETURNING id",
        role,
        email,
        Argon2PasswordHasher().hash(ACTOR_PASSWORD),
    )
    await database.execute(
        "INSERT INTO public.user_roles(user_id,role_code) VALUES($1,$2)", user_id, role
    )
    return user_id, email


def bearer(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": ACTOR_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


async def product(database: asyncpg.Connection, *, price: str = "10.00", stock: int = 10) -> UUID:
    category_id = await database.fetchval(
        "INSERT INTO public.categories(name) VALUES($1) RETURNING id", f"Platos-{uuid4()}"
    )
    return await database.fetchval(
        """INSERT INTO public.products(category_id,name,price,stock_qty,is_available)
        VALUES($1,'Chaufa',$2,$3,TRUE) RETURNING id""",
        category_id,
        Decimal(price),
        stock,
    )


async def table(database: asyncpg.Connection) -> UUID:
    return await database.fetchval(
        "INSERT INTO public.restaurant_tables(code) VALUES($1) RETURNING id",
        f"M-{uuid4().hex[:12]}",
    )


def app_order_payload(
    modality: str, product_id: UUID, *, quantity: int = 1, table_id: UUID | None = None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "modality": modality,
        "items": [{"product_id": str(product_id), "quantity": quantity}],
    }
    if modality == "LOCAL":
        assert table_id is not None
        payload["table_id"] = str(table_id)
    else:
        payload["contact_name"] = "Ana"
        payload["contact_phone"] = "999111222"
        if modality == "DELIVERY":
            payload["delivery_address"] = "Av. Lima 123"
    return payload


@pytest.mark.asyncio
async def test_local_app_requires_review_then_debits_once_and_issues_one_ticket(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, stock=10)
    table_id = await table(database)
    _, customer_email = await actor(database, "CUSTOMER")
    waiter_id, waiter_email = await actor(database, "WAITER")
    _, admin_email = await actor(database, "ADMIN")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        waiter = bearer(client, waiter_email)
        admin = bearer(client, admin_email)
        cashier = bearer(client, cashier_email)
        created = client.post(
            "/api/v1/orders",
            json=app_order_payload("LOCAL", product_id, quantity=2, table_id=table_id),
            headers={**customer, "Idempotency-Key": "local-order"},
        )
        assert created.status_code == 201, created.text
        order_id = UUID(created.json()["id"])
        path = f"/api/v1/orders/{order_id}/confirm"
        assert (
            client.post(path, headers={**waiter, "Idempotency-Key": "too-early"}).status_code == 409
        )
        assert (
            client.post(path, headers={**customer, "Idempotency-Key": "customer"}).status_code
            == 403
        )
        assert (
            client.post(path, headers={**cashier, "Idempotency-Key": "cashier"}).status_code == 403
        )
        assert client.post(path, headers=waiter).status_code == 422
        approved = client.post(
            f"/api/v1/orders/{order_id}/decision",
            json={"approved": True, "table_verified": True},
            headers=waiter,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert (
            await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
            == 10
        )
        assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
        first = client.post(path, headers={**waiter, "Idempotency-Key": "confirm-local"})
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "CONFIRMED"
        replay = client.post(path, headers={**waiter, "Idempotency-Key": "confirm-local"})
        assert replay.status_code == 200 and replay.json() == first.json()
        another = client.post(path, headers={**admin, "Idempotency-Key": "second-actor"})
        assert another.status_code == 200 and another.json() == first.json()
        assert (
            client.post(path, headers={**waiter, "Idempotency-Key": "confirm-local"}).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/orders/{uuid4()}/confirm",
                headers={**waiter, "Idempotency-Key": "confirm-local"},
            ).status_code
            == 409
        )
    order = await database.fetchrow(
        "SELECT status,confirmed_by_user_id,confirmed_at,version FROM public.orders WHERE id=$1",
        order_id,
    )
    assert order is not None
    assert (order["status"], order["confirmed_by_user_id"], order["version"]) == (
        "CONFIRMED",
        waiter_id,
        1,
    )
    assert order["confirmed_at"] is not None
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 8
    )
    movement = await database.fetchrow(
        "SELECT kind,quantity_delta,actor_user_id,order_item_id FROM public.stock_movements"
    )
    assert movement is not None
    assert (movement["kind"], movement["quantity_delta"], movement["actor_user_id"]) == (
        "ORDER",
        -2,
        waiter_id,
    )
    assert movement["order_item_id"] is not None
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 1
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.kitchen_tickets WHERE order_id=$1", order_id
        )
        == 1
    )
    assert await database.fetchval("SELECT count(*) FROM public.payments") == 0
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests "
            "WHERE operation='CONFIRM_ORDER' AND result_order_id=$1",
            order_id,
        )
        == 2
    )


@pytest.mark.asyncio
async def test_waiter_direct_order_occupies_and_rolls_back_on_stock_failure(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, stock=2)
    first_table = await table(database)
    second_table = await table(database)
    waiter_id, waiter_email = await actor(database, "WAITER")
    _, admin_email = await actor(database, "ADMIN")
    _, kitchen_email = await actor(database, "KITCHEN")
    path = "/api/v1/orders/waiter"
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        admin = bearer(client, admin_email)
        kitchen = bearer(client, kitchen_email)
        payload = {
            "table_id": str(first_table),
            "items": [{"product_id": str(product_id), "quantity": 2}],
        }
        assert (
            client.post(
                path, json=payload, headers={**admin, "Idempotency-Key": "admin"}
            ).status_code
            == 403
        )
        created = client.post(path, json=payload, headers={**waiter, "Idempotency-Key": "direct"})
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "CONFIRMED"
        assert created.json()["channel"] == "WAITER"
        order_id = UUID(created.json()["id"])
        replay = client.post(path, json=payload, headers={**waiter, "Idempotency-Key": "direct"})
        assert replay.status_code == 201 and replay.json() == created.json()
        changed = {
            "table_id": str(first_table),
            "items": [{"product_id": str(product_id), "quantity": 1}],
        }
        assert (
            client.post(
                path, json=changed, headers={**waiter, "Idempotency-Key": "direct"}
            ).status_code
            == 409
        )
        failed = client.post(
            path,
            json={
                "table_id": str(second_table),
                "items": [{"product_id": str(product_id), "quantity": 1}],
            },
            headers={**waiter, "Idempotency-Key": "stock-fail"},
        )
        assert failed.status_code == 409, failed.text
        kitchen_list = client.get("/api/v1/kitchen/tickets", headers=kitchen)
        assert kitchen_list.status_code == 200
        assert [ticket["order_id"] for ticket in kitchen_list.json()] == [str(order_id)]
    assert await database.fetchval(
        "SELECT is_occupied FROM public.restaurant_tables WHERE id=$1", first_table
    )
    assert not await database.fetchval(
        "SELECT is_occupied FROM public.restaurant_tables WHERE id=$1", second_table
    )
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 0
    )
    assert await database.fetchval("SELECT count(*) FROM public.orders") == 1
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 1
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 1
    assert await database.fetchval("SELECT count(*) FROM public.payments") == 0
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests WHERE request_key='stock-fail'"
        )
        == 0
    )
    assert (
        await database.fetchval(
            "SELECT created_by_user_id FROM public.orders WHERE id=$1", order_id
        )
        == waiter_id
    )


@pytest.mark.asyncio
async def test_multiline_waiter_order_debits_each_line_once(database: asyncpg.Connection) -> None:
    first_product = await product(database, stock=10)
    second_product = await product(database, stock=7)
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    payload = {
        "table_id": str(table_id),
        "items": [
            {"product_id": str(first_product), "quantity": 2},
            {"product_id": str(second_product), "quantity": 3},
        ],
    }
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        first = client.post(
            "/api/v1/orders/waiter",
            json=payload,
            headers={**waiter, "Idempotency-Key": "multiline"},
        )
        assert first.status_code == 201, first.text
        assert first.json()["status"] == "CONFIRMED"
        replay = client.post(
            "/api/v1/orders/waiter",
            json=payload,
            headers={**waiter, "Idempotency-Key": "multiline"},
        )
        assert replay.status_code == 201 and replay.json() == first.json()
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", first_product)
        == 8
    )
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", second_product)
        == 4
    )
    movements = await database.fetch(
        "SELECT product_id,quantity_delta,order_item_id FROM public.stock_movements"
    )
    assert {(row["product_id"], row["quantity_delta"]) for row in movements} == {
        (first_product, -2),
        (second_product, -3),
    }
    assert len({row["order_item_id"] for row in movements}) == 2
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("modality", ["PICKUP", "DELIVERY"])
async def test_remote_confirmation_requires_exact_verified_advance(
    database: asyncpg.Connection, modality: str
) -> None:
    product_id = await product(database, price="10.01", stock=3)
    _, customer_email = await actor(database, "CUSTOMER")
    admin_id, admin_email = await actor(database, "ADMIN")
    _, waiter_email = await actor(database, "WAITER")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        admin = bearer(client, admin_email)
        waiter = bearer(client, waiter_email)
        cashier = bearer(client, cashier_email)
        created = client.post(
            "/api/v1/orders",
            json=app_order_payload(modality, product_id),
            headers={**customer, "Idempotency-Key": "remote-order"},
        )
        assert created.status_code == 201, created.text
        order_id = UUID(created.json()["id"])
        path = f"/api/v1/orders/{order_id}/confirm"
        approved = client.post(
            f"/api/v1/orders/{order_id}/decision",
            json={"approved": True},
            headers=admin,
        )
        assert approved.status_code == 200
        assert client.post(path, headers={**waiter, "Idempotency-Key": "waiter"}).status_code == 403
        assert (
            client.post(path, headers={**cashier, "Idempotency-Key": "cashier"}).status_code == 403
        )
        blocked = client.post(path, headers={**admin, "Idempotency-Key": "before-advance"})
        assert blocked.status_code == 409, blocked.text
        assert (
            await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
            == 3
        )
        assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
        verified = client.post(
            f"/api/v1/orders/{order_id}/advance/verify",
            headers={**admin, "Idempotency-Key": "advance"},
        )
        assert verified.status_code == 200, verified.text
        assert Decimal(verified.json()["verified_amount"]) == Decimal("5.01")
        confirmed = client.post(path, headers={**admin, "Idempotency-Key": "confirm"})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["status"] == "CONFIRMED"
        assert (
            client.post(path, headers={**admin, "Idempotency-Key": "confirm"}).json()
            == confirmed.json()
        )
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 2
    )
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 1
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.kitchen_tickets WHERE order_id=$1", order_id
        )
        == 1
    )
    payment = await database.fetchrow(
        "SELECT amount,recorded_by_user_id FROM public.payments WHERE order_id=$1 AND kind='ADVANCE'",
        order_id,
    )
    assert payment is not None
    assert payment["amount"] == Decimal("5.01")
    assert payment["recorded_by_user_id"] == admin_id
    assert await database.fetchval("SELECT count(*) FROM public.payments") == 1


@pytest.mark.asyncio
async def test_rejected_and_unavailable_orders_never_reach_kitchen(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, stock=1)
    first_table = await table(database)
    second_table = await table(database)
    _, customer_email = await actor(database, "CUSTOMER")
    _, waiter_email = await actor(database, "WAITER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        waiter = bearer(client, waiter_email)
        rejected = client.post(
            "/api/v1/orders",
            json=app_order_payload("LOCAL", product_id, table_id=first_table),
            headers={**customer, "Idempotency-Key": "reject-me"},
        )
        assert rejected.status_code == 201
        rejected_id = UUID(rejected.json()["id"])
        decision = client.post(
            f"/api/v1/orders/{rejected_id}/decision",
            json={"approved": False},
            headers=waiter,
        )
        assert decision.status_code == 200 and decision.json()["status"] == "REJECTED"
        assert (
            client.post(
                f"/api/v1/orders/{rejected_id}/confirm",
                headers={**waiter, "Idempotency-Key": "rejected-confirm"},
            ).status_code
            == 409
        )
        pending = client.post(
            "/api/v1/orders",
            json=app_order_payload("LOCAL", product_id, quantity=2, table_id=second_table),
            headers={**customer, "Idempotency-Key": "stock-order"},
        )
        assert pending.status_code == 201
        pending_id = UUID(pending.json()["id"])
        approved = client.post(
            f"/api/v1/orders/{pending_id}/decision",
            json={"approved": True, "table_verified": True},
            headers=waiter,
        )
        assert approved.status_code == 200
        confirm_path = f"/api/v1/orders/{pending_id}/confirm"
        no_stock = client.post(confirm_path, headers={**waiter, "Idempotency-Key": "not-enough"})
        assert no_stock.status_code == 409, no_stock.text
        await database.execute(
            "UPDATE public.products SET stock_qty=3,is_available=FALSE WHERE id=$1", product_id
        )
        disabled = client.post(confirm_path, headers={**waiter, "Idempotency-Key": "disabled"})
        assert disabled.status_code == 409, disabled.text
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 0
    assert (
        await database.fetchval("SELECT status FROM public.orders WHERE id=$1", pending_id)
        == "APPROVED"
    )


@pytest.mark.asyncio
async def test_ticket_insert_conflict_rolls_back_stock_status_and_idempotency(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, stock=5)
    table_id = await table(database)
    _, customer_email = await actor(database, "CUSTOMER")
    _, waiter_email = await actor(database, "WAITER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        waiter = bearer(client, waiter_email)
        created = client.post(
            "/api/v1/orders",
            json=app_order_payload("LOCAL", product_id, quantity=2, table_id=table_id),
            headers={**customer, "Idempotency-Key": "rollback-order"},
        )
        assert created.status_code == 201
        order_id = UUID(created.json()["id"])
        approved = client.post(
            f"/api/v1/orders/{order_id}/decision",
            json={"approved": True, "table_verified": True},
            headers=waiter,
        )
        assert approved.status_code == 200
        # Deliberately corrupt only this disposable fixture to force failure after debit/status.
        await database.execute("INSERT INTO public.kitchen_tickets(order_id) VALUES($1)", order_id)
        failed = client.post(
            f"/api/v1/orders/{order_id}/confirm",
            headers={**waiter, "Idempotency-Key": "rollback-confirm"},
        )
        assert failed.status_code == 409, failed.text
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 5
    )
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 0
    assert (
        await database.fetchval("SELECT status FROM public.orders WHERE id=$1", order_id)
        == "APPROVED"
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.kitchen_tickets WHERE order_id=$1", order_id
        )
        == 1
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests WHERE request_key='rollback-confirm'"
        )
        == 0
    )


@pytest.mark.asyncio
async def test_manual_whatsapp_needs_advance_but_no_second_approval(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, price="20.00", stock=2)
    _, admin_email = await actor(database, "ADMIN")
    with api_client() as client:
        admin = bearer(client, admin_email)
        created = client.post(
            "/api/v1/orders/manual",
            json={
                "modality": "PICKUP",
                "channel": "WHATSAPP",
                "contact_name": "Ana",
                "contact_phone": "999111222",
                "items": [{"product_id": str(product_id), "quantity": 1}],
            },
            headers={**admin, "Idempotency-Key": "manual-whatsapp"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "APPROVED"
        order_id = UUID(created.json()["id"])
        path = f"/api/v1/orders/{order_id}/confirm"
        assert (
            client.post(path, headers={**admin, "Idempotency-Key": "manual-confirm"}).status_code
            == 409
        )
        advance = client.post(
            f"/api/v1/orders/{order_id}/advance/verify",
            headers={**admin, "Idempotency-Key": "manual-advance"},
        )
        assert advance.status_code == 200, advance.text
        assert Decimal(advance.json()["verified_amount"]) == Decimal("10.00")
        confirmed = client.post(path, headers={**admin, "Idempotency-Key": "manual-confirm"})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["channel"] == "WHATSAPP"
        assert confirmed.json()["status"] == "CONFIRMED"
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 1
    )
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 1
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 1
    assert await database.fetchval("SELECT count(*) FROM public.payments") == 1


@pytest.mark.asyncio
async def test_local_app_account_prevents_stale_table_occupation(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database)
    table_id = await table(database)
    _, customer_email = await actor(database, "CUSTOMER")
    _, waiter_email = await actor(database, "WAITER")
    _, admin_email = await actor(database, "ADMIN")
    with api_client() as client:
        customer = bearer(client, customer_email)
        waiter = bearer(client, waiter_email)
        admin = bearer(client, admin_email)
        created = client.post(
            "/api/v1/orders",
            json=app_order_payload("LOCAL", product_id, table_id=table_id),
            headers={**customer, "Idempotency-Key": "epoch-order"},
        )
        assert created.status_code == 201
        order_id = UUID(created.json()["id"])
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision",
                json={"approved": True, "table_verified": True},
                headers=waiter,
            ).status_code
            == 200
        )
        occupancy = f"/api/v1/tables/{table_id}/occupancy"
        release = client.patch(occupancy, json={"is_occupied": False}, headers=admin)
        assert release.status_code == 409, release.text
        confirmed = client.post(
            f"/api/v1/orders/{order_id}/confirm",
            headers={**waiter, "Idempotency-Key": "protected-table"},
        )
        assert confirmed.status_code == 200, confirmed.text
    assert (
        await database.fetchval("SELECT status FROM public.orders WHERE id=$1", order_id)
        == "CONFIRMED"
    )
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 9
    )
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 1


async def wait_for_lock_waiters(
    database: asyncpg.Connection,
    tasks: list[asyncio.Task[httpx.Response]],
    *,
    event: str | None = None,
) -> None:
    """Require two independent app sessions to be blocked before releasing the barrier."""

    async def observed() -> None:
        while True:
            waiting = await database.fetchval(
                """SELECT count(*) FROM pg_locks
                WHERE NOT granted AND ($1::text IS NULL OR locktype=$1)
                  AND ($1::text IS DISTINCT FROM 'advisory'
                       OR database=(SELECT oid FROM pg_database WHERE datname=current_database()))""",
                event,
            )
            if waiting >= 2:
                return
            if any(task.done() for task in tasks):
                details = [
                    (task.result().status_code if not task.exception() else repr(task.exception()))
                    for task in tasks
                    if task.done()
                ]
                pytest.fail(f"A confirmation completed before the lock barrier: {details}")
            await asyncio.sleep(0.05)

    try:
        await asyncio.wait_for(observed(), timeout=8)
    except TimeoutError:
        rows = await database.fetch(
            "SELECT wait_event_type,wait_event,state,left(query,120) AS query "
            "FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"
        )
        pytest.fail(f"Lock barrier did not form: {[tuple(row) for row in rows]}")


@pytest.mark.asyncio
async def test_simultaneous_same_key_confirmation_has_one_effect(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, stock=4)
    table_id = await table(database)
    _, customer_email = await actor(database, "CUSTOMER")
    waiter_id, waiter_email = await actor(database, "WAITER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        waiter = bearer(client, waiter_email)
        created = client.post(
            "/api/v1/orders",
            json=app_order_payload("LOCAL", product_id, quantity=2, table_id=table_id),
            headers={**customer, "Idempotency-Key": "parallel-order"},
        )
        assert created.status_code == 201
        order_id = UUID(created.json()["id"])
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision",
                json={"approved": True, "table_verified": True},
                headers=waiter,
            ).status_code
            == 200
        )
    request_key = f"same-{uuid4()}"
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with async_clients() as (first, second):
        login = await first.post(
            "/api/v1/auth/login", json={"email": waiter_email, "password": ACTOR_PASSWORD}
        )
        assert login.status_code == 200
        headers = {
            "Authorization": "Bearer " + login.json()["access_token"],
            "Idempotency-Key": request_key,
        }
        try:
            async with database.transaction():
                await database.fetchval(
                    "SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                    f"CONFIRM_ORDER:{waiter_id}:{request_key}",
                )
                tasks = [
                    asyncio.create_task(
                        client.post(f"/api/v1/orders/{order_id}/confirm", headers=headers)
                    )
                    for client in (first, second)
                ]
                await wait_for_lock_waiters(database, tasks, event="advisory")
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
        assert [response.status_code for response in responses] == [200, 200]
        assert responses[0].json() == responses[1].json()
    dsn, _ = _test_database_target()
    third = await asyncpg.connect(dsn)
    try:
        async with third.transaction(isolation="repeatable_read"):
            assert (
                await third.fetchval(
                    "SELECT stock_qty FROM public.products WHERE id=$1", product_id
                )
                == 2
            )
            assert (
                await third.fetchval("SELECT status FROM public.orders WHERE id=$1", order_id)
                == "CONFIRMED"
            )
            assert await third.fetchval("SELECT count(*) FROM public.stock_movements") == 1
            assert await third.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 1
            assert (
                await third.fetchval(
                    "SELECT count(*) FROM public.idempotency_requests "
                    "WHERE operation='CONFIRM_ORDER' AND result_order_id=$1",
                    order_id,
                )
                == 1
            )
    finally:
        await third.close()


@pytest.mark.asyncio
async def test_two_orders_competing_for_last_unit_never_oversell(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, stock=1)
    table_ids = [await table(database), await table(database)]
    _, customer_email = await actor(database, "CUSTOMER")
    _, waiter_email = await actor(database, "WAITER")
    order_ids: list[UUID] = []
    with api_client() as client:
        customer = bearer(client, customer_email)
        waiter = bearer(client, waiter_email)
        for index, table_id in enumerate(table_ids):
            created = client.post(
                "/api/v1/orders",
                json=app_order_payload("LOCAL", product_id, table_id=table_id),
                headers={**customer, "Idempotency-Key": f"racing-order-{index}"},
            )
            assert created.status_code == 201, created.text
            order_id = UUID(created.json()["id"])
            order_ids.append(order_id)
            approved = client.post(
                f"/api/v1/orders/{order_id}/decision",
                json={"approved": True, "table_verified": True},
                headers=waiter,
            )
            assert approved.status_code == 200, approved.text
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with async_clients() as (first, second):
        login = await first.post(
            "/api/v1/auth/login", json={"email": waiter_email, "password": ACTOR_PASSWORD}
        )
        assert login.status_code == 200
        authorization = {"Authorization": "Bearer " + login.json()["access_token"]}
        try:
            async with database.transaction():
                await database.fetchval(
                    "SELECT id FROM public.products WHERE id=$1 FOR UPDATE", product_id
                )
                tasks = [
                    asyncio.create_task(
                        client.post(
                            f"/api/v1/orders/{order_id}/confirm",
                            headers={**authorization, "Idempotency-Key": f"race-{index}"},
                        )
                    )
                    for index, (client, order_id) in enumerate(
                        zip((first, second), order_ids, strict=True)
                    )
                ]
                await wait_for_lock_waiters(database, tasks)
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
        assert sorted(response.status_code for response in responses) == [200, 409]
    dsn, _ = _test_database_target()
    third = await asyncpg.connect(dsn)
    try:
        async with third.transaction(isolation="repeatable_read"):
            assert (
                await third.fetchval(
                    "SELECT stock_qty FROM public.products WHERE id=$1", product_id
                )
                == 0
            )
            statuses = [
                await third.fetchval("SELECT status FROM public.orders WHERE id=$1", order_id)
                for order_id in order_ids
            ]
            assert sorted(statuses) == ["APPROVED", "CONFIRMED"]
            assert await third.fetchval("SELECT count(*) FROM public.stock_movements") == 1
            assert await third.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 1
            assert (
                await third.fetchval(
                    "SELECT count(*) FROM public.idempotency_requests WHERE operation='CONFIRM_ORDER'"
                )
                == 1
            )
    finally:
        await third.close()


@pytest.mark.asyncio
async def test_two_waiters_on_distinct_tables_same_product_do_not_deadlock(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, stock=2)
    table_ids = [await table(database), await table(database)]
    waiter_emails = [(await actor(database, "WAITER"))[1] for _ in range(2)]
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with async_clients() as (first, second):
        clients = (first, second)
        headers = []
        for client, email in zip(clients, waiter_emails, strict=True):
            login = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": ACTOR_PASSWORD}
            )
            assert login.status_code == 200
            headers.append({"Authorization": "Bearer " + login.json()["access_token"]})
        try:
            async with database.transaction():
                await database.fetchval(
                    "SELECT id FROM public.products WHERE id=$1 FOR SHARE", product_id
                )
                barrier_xid = str(await database.fetchval("SELECT pg_current_xact_id()::xid"))
                tasks = [
                    asyncio.create_task(
                        client.post(
                            "/api/v1/orders/waiter",
                            json={
                                "table_id": str(table_id),
                                "items": [{"product_id": str(product_id), "quantity": 1}],
                            },
                            headers={**auth, "Idempotency-Key": f"waiter-race-{index}"},
                        )
                    )
                    for index, (client, table_id, auth) in enumerate(
                        zip(clients, table_ids, headers, strict=True)
                    )
                ]

                async def both_wait_on_barrier() -> None:
                    while True:
                        waits = await database.fetchrow(
                            "SELECT count(*) AS total, "
                            "count(*) FILTER (WHERE transactionid::text=$1) AS on_barrier "
                            "FROM pg_locks WHERE NOT granted "
                            "AND ((locktype='transactionid' AND transactionid::text=$1) "
                            "OR (locktype='tuple' AND relation='public.products'::regclass)) "
                            "AND pid<>pg_backend_pid()",
                            barrier_xid,
                        )
                        if waits is not None and waits["total"] >= 2 and waits["on_barrier"] >= 1:
                            return
                        if any(task.done() for task in tasks):
                            pytest.fail(
                                "A waiter request finished before both product locks waited"
                            )
                        await asyncio.sleep(0.05)

                try:
                    await asyncio.wait_for(both_wait_on_barrier(), timeout=8)
                except TimeoutError:
                    locks = await database.fetch(
                        "SELECT locktype,mode,transactionid::text,pid FROM pg_locks "
                        "WHERE NOT granted"
                    )
                    pytest.fail(
                        f"Product lock barrier did not form: {[tuple(row) for row in locks]}"
                    )
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        assert [response.status_code for response in responses] == [201, 201]
        assert len({response.json()["id"] for response in responses}) == 2
        assert all(response.json()["status"] == "CONFIRMED" for response in responses)
    dsn, _ = _test_database_target()
    third = await asyncpg.connect(dsn)
    try:
        async with third.transaction(isolation="repeatable_read"):
            assert (
                await third.fetchval(
                    "SELECT stock_qty FROM public.products WHERE id=$1", product_id
                )
                == 0
            )
            assert await third.fetchval("SELECT count(*) FROM public.orders") == 2
            assert await third.fetchval("SELECT count(*) FROM public.stock_movements") == 2
            assert await third.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 2
            assert (
                await third.fetchval(
                    "SELECT count(*) FROM public.idempotency_requests "
                    "WHERE operation='CONFIRM_ORDER'"
                )
                == 2
            )
            for table_id in table_ids:
                assert await third.fetchval(
                    "SELECT is_occupied FROM public.restaurant_tables WHERE id=$1", table_id
                )
    finally:
        await third.close()
