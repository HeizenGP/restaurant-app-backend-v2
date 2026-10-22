"""HTTP + PostgreSQL checks for 08.04 without confirming orders."""

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
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from restaurant_app.core.config import Settings
from restaurant_app.main import create_app
from restaurant_app.modules.m01_access.adapters.outbound.password_hasher import (
    Argon2PasswordHasher,
)
from restaurant_app.modules.m04_orders.public import SqlAlchemyAdvanceOrderReader
from tests.integration.test_initial_migration import _test_database_target

pytest_plugins = ("tests.integration.test_initial_migration",)
pytestmark = pytest.mark.integration

JWT_SECRET = "m04-integration-jwt-secret-with-more-than-32-characters"
ACTOR_PASSWORD = "m04-integration-password"


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
async def async_api_clients() -> AsyncIterator[tuple[httpx.AsyncClient, httpx.AsyncClient]]:
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
        """INSERT INTO public.users(display_name,email,password_hash)
        VALUES($1,$2,$3) RETURNING id""",
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


async def catalog(database: asyncpg.Connection) -> UUID:
    category_id = await database.fetchval(
        "INSERT INTO public.categories(name) VALUES($1) RETURNING id", f"Platos-{uuid4()}"
    )
    return await database.fetchval(
        """INSERT INTO public.products(category_id,name,price,stock_qty,is_available)
        VALUES($1,'Chaufa',12.00,8,TRUE) RETURNING id""",
        category_id,
    )


@pytest.mark.asyncio
async def test_guest_local_request_snapshot_table_approval_and_replay(
    database: asyncpg.Connection,
) -> None:
    product_id = await catalog(database)
    admin_id, admin_email = await actor(database, "ADMIN")
    waiter_id, waiter_email = await actor(database, "WAITER")
    with api_client() as client:
        admin = bearer(client, admin_email)
        waiter = bearer(client, waiter_email)
        created_table = client.post(
            "/api/v1/tables", json={"code": "M-01", "area_label": "Salón"}, headers=admin
        )
        assert created_table.status_code == 201, created_table.text
        table_id = created_table.json()["id"]
        occupied = client.patch(
            f"/api/v1/tables/{table_id}/occupancy",
            json={"is_occupied": True},
            headers=waiter,
        )
        assert occupied.status_code == 200, occupied.text
        assert occupied.json()["is_occupied"] is True
        guest = client.post("/api/v1/auth/guest")
        assert guest.status_code == 201
        guest_headers = {
            "Authorization": "Bearer " + guest.json()["access_token"],
            "Idempotency-Key": "guest-local-1",
        }
        payload = {
            "modality": "LOCAL",
            "table_id": table_id,
            "items": [{"product_id": str(product_id), "quantity": 2}],
        }
        blocked = client.post("/api/v1/orders", json=payload, headers=guest_headers)
        assert blocked.status_code == 422, blocked.text
        assert client.get("/api/v1/orders", headers=guest_headers).json() == []
        released = client.patch(
            f"/api/v1/tables/{table_id}/occupancy",
            json={"is_occupied": False},
            headers=admin,
        )
        assert released.status_code == 200, released.text
        assert released.json()["is_occupied"] is False
        created = client.post("/api/v1/orders", json=payload, headers=guest_headers)
        assert created.status_code == 201, created.text
        order_id = created.json()["id"]
        assert created.json()["status"] == "REQUESTED"
        assert created.json()["table_id"] == table_id
        assert created.json()["channel"] == "APP"
        assert Decimal(created.json()["total_amount"]) == Decimal("24.00")
        assert created.json()["lines"][0]["product_name_snapshot"] == "Chaufa"
        assert Decimal(created.json()["lines"][0]["unit_price_snapshot"]) == Decimal("12.00")
        catalog_changed = client.patch(
            f"/api/v1/catalog/products/{product_id}",
            json={"name": "Chaufa nuevo", "price": "15.00"},
            headers=admin,
        )
        assert catalog_changed.status_code == 200, catalog_changed.text
        saved = client.get(f"/api/v1/orders/{order_id}", headers=guest_headers)
        assert saved.status_code == 200
        assert saved.json()["lines"][0]["product_name_snapshot"] == "Chaufa"
        assert Decimal(saved.json()["lines"][0]["unit_price_snapshot"]) == Decimal("12.00")
        assert Decimal(saved.json()["total_amount"]) == Decimal("24.00")
        replay = client.post("/api/v1/orders", json=payload, headers=guest_headers)
        assert replay.status_code == 201
        assert replay.json()["id"] == order_id
        changed_payload = {**payload, "items": [{"product_id": str(product_id), "quantity": 3}]}
        assert (
            client.post("/api/v1/orders", json=changed_payload, headers=guest_headers).status_code
            == 409
        )
        assert client.get(f"/api/v1/orders/{order_id}", headers=guest_headers).status_code == 200
        assert len(client.get("/api/v1/orders", headers=guest_headers).json()) == 1
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision",
                json={"approved": True, "table_verified": False},
                headers=waiter,
            ).status_code
            == 409
        )
        approved = client.post(
            f"/api/v1/orders/{order_id}/decision",
            json={"approved": True, "table_verified": True},
            headers=waiter,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert approved.json()["table_verified_at"] is not None
        assert client.get("/api/v1/tables", headers=guest_headers).json()[0]["is_occupied"] is True
        occupied_after_approval = client.patch(
            f"/api/v1/tables/{table_id}/occupancy",
            json={"is_occupied": True},
            headers=waiter,
        )
        assert occupied_after_approval.status_code == 200
        assert occupied_after_approval.json()["is_occupied"] is True
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision",
                json={"approved": True, "table_verified": True},
                headers=waiter,
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision",
                json={"approved": False},
                headers=admin,
            ).status_code
            == 409
        )
    row = await database.fetchrow(
        "SELECT status,table_id,total_amount,decided_by_user_id,table_verified_at "
        "FROM public.orders WHERE id=$1",
        UUID(order_id),
    )
    assert row is not None
    assert row["status"] == "APPROVED"
    assert row["table_id"] == UUID(table_id)
    assert row["table_verified_at"] is not None
    assert await database.fetchval("SELECT count(*) FROM public.orders") == 1
    assert await database.fetchval("SELECT count(*) FROM public.order_items") == 1
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 8
    )
    assert row["decided_by_user_id"] == waiter_id
    assert row["decided_by_user_id"] != admin_id
    assert (
        await database.fetchval(
            "SELECT is_occupied FROM public.restaurant_tables WHERE id=$1", UUID(table_id)
        )
        is True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("guest", [False, True], ids=["registered", "guest-session"])
async def test_additional_local_orders_require_current_verified_table_owner(
    database: asyncpg.Connection, guest: bool
) -> None:
    product_id = await catalog(database)
    _, admin_email = await actor(database, "ADMIN")
    _, waiter_email = await actor(database, "WAITER")
    if not guest:
        _, customer_email = await actor(database, "CUSTOMER")
        _, other_email = await actor(database, "CUSTOMER")
    with api_client() as client:
        admin = bearer(client, admin_email)
        waiter = bearer(client, waiter_email)
        if guest:
            first = client.post("/api/v1/auth/guest")
            other = client.post("/api/v1/auth/guest")
            assert first.status_code == other.status_code == 201
            owner = {"Authorization": "Bearer " + first.json()["access_token"]}
            outsider = {"Authorization": "Bearer " + other.json()["access_token"]}
        else:
            owner = bearer(client, customer_email)
            outsider = bearer(client, other_email)
        table_response = client.post("/api/v1/tables", json={"code": "T-01"}, headers=admin)
        assert table_response.status_code == 201, table_response.text
        table_id = table_response.json()["id"]
        payload = {
            "modality": "LOCAL",
            "table_id": table_id,
            "items": [{"product_id": str(product_id), "quantity": 1}],
        }
        first_order = client.post(
            "/api/v1/orders", json=payload, headers={**owner, "Idempotency-Key": "first"}
        )
        assert first_order.status_code == 201, first_order.text
        assert first_order.json()["status"] == "REQUESTED"
        assert table_response.json()["is_occupied"] is False
        still_free = client.get("/api/v1/tables", headers=owner)
        assert still_free.status_code == 200
        assert still_free.json()[0]["is_occupied"] is False
        # A QR/table ID and a pending request cannot establish ownership.
        pending_outsider = client.post(
            "/api/v1/orders",
            json=payload,
            headers={**outsider, "Idempotency-Key": "outsider-before-approval"},
        )
        assert pending_outsider.status_code == 201, pending_outsider.text
        manually_occupied = client.patch(
            f"/api/v1/tables/{table_id}/occupancy",
            json={"is_occupied": True},
            headers=waiter,
        )
        assert manually_occupied.status_code == 200, manually_occupied.text
        assert (
            client.post(
                "/api/v1/orders",
                json=payload,
                headers={**owner, "Idempotency-Key": "pending-is-not-membership"},
            ).status_code
            == 422
        )
        unverified = client.post(
            f"/api/v1/orders/{first_order.json()['id']}/decision",
            json={"approved": True, "table_verified": False},
            headers=waiter,
        )
        assert unverified.status_code == 409, unverified.text
        assert client.get("/api/v1/tables", headers=owner).json()[0]["is_occupied"] is True
        approved = client.post(
            f"/api/v1/orders/{first_order.json()['id']}/decision",
            json={"approved": True, "table_verified": True},
            headers=waiter,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert client.get("/api/v1/tables", headers=owner).json()[0]["is_occupied"] is True
        conflict = client.post(
            f"/api/v1/orders/{pending_outsider.json()['id']}/decision",
            json={"approved": True, "table_verified": True},
            headers=waiter,
        )
        assert conflict.status_code == 409, conflict.text
        assert (
            client.post(
                "/api/v1/orders",
                json=payload,
                headers={**outsider, "Idempotency-Key": "outsider-while-occupied"},
            ).status_code
            == 422
        )
        if not guest:
            # A second login session of the same registered user keeps the association.
            owner = bearer(client, customer_email)
        additional = client.post(
            "/api/v1/orders", json=payload, headers={**owner, "Idempotency-Key": "additional"}
        )
        assert additional.status_code == 201, additional.text
        assert additional.json()["status"] == "REQUESTED"
        assert (
            client.post(
                f"/api/v1/orders/{additional.json()['id']}/decision",
                json={"approved": True, "table_verified": False},
                headers=waiter,
            ).status_code
            == 409
        )
        verified_additional = client.post(
            f"/api/v1/orders/{additional.json()['id']}/decision",
            json={"approved": True, "table_verified": True},
            headers=waiter,
        )
        assert verified_additional.status_code == 200, verified_additional.text
        assert (
            client.patch(
                f"/api/v1/tables/{table_id}/occupancy",
                json={"is_occupied": False},
                headers=waiter,
            ).status_code
            == 403
        )
        released = client.patch(
            f"/api/v1/tables/{table_id}/occupancy",
            json={"is_occupied": False},
            headers=admin,
        )
        assert released.status_code == 200, released.text
        occupied_again = client.patch(
            f"/api/v1/tables/{table_id}/occupancy",
            json={"is_occupied": True},
            headers=waiter,
        )
        assert occupied_again.status_code == 200, occupied_again.text
        assert (
            client.post(
                "/api/v1/orders",
                json=payload,
                headers={**owner, "Idempotency-Key": "stale-membership"},
            ).status_code
            == 422
        )
    table_row = await database.fetchrow(
        "SELECT is_occupied, occupancy_started_at FROM public.restaurant_tables WHERE id=$1",
        UUID(table_id),
    )
    assert table_row is not None and table_row["is_occupied"] is True
    first_verified_at = await database.fetchval(
        "SELECT table_verified_at FROM public.orders WHERE id=$1", UUID(first_order.json()["id"])
    )
    assert first_verified_at is not None
    assert table_row["occupancy_started_at"] > first_verified_at
    assert await database.fetchval("SELECT count(*) FROM public.orders") == 3
    assert await database.fetchval("SELECT count(*) FROM public.order_items") == 3


@pytest.mark.asyncio
async def test_delivery_review_rejection_visibility_and_permissions(
    database: asyncpg.Connection,
) -> None:
    product_id = await catalog(database)
    _, customer_email = await actor(database, "CUSTOMER")
    _, other_email = await actor(database, "CUSTOMER")
    admin_id, admin_email = await actor(database, "ADMIN")
    _, waiter_email = await actor(database, "WAITER")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        other = bearer(client, other_email)
        admin = bearer(client, admin_email)
        waiter = bearer(client, waiter_email)
        cashier = bearer(client, cashier_email)
        payload = {
            "modality": "DELIVERY",
            "delivery_address": "Av. Lima 123",
            "contact_name": "Ana",
            "contact_phone": "999111222",
            "items": [{"product_id": str(product_id), "quantity": 1}],
        }
        headers = {**customer, "Idempotency-Key": "delivery-1"}
        created = client.post("/api/v1/orders", json=payload, headers=headers)
        assert created.status_code == 201, created.text
        order_id = created.json()["id"]
        assert created.json()["table_id"] is None
        assert created.json()["delivery_address"] == "Av. Lima 123"
        assert client.get(f"/api/v1/orders/{order_id}", headers=other).status_code == 404
        assert client.get(f"/api/v1/orders/{order_id}", headers=cashier).status_code == 404
        assert client.get(f"/api/v1/orders/{order_id}", headers=waiter).status_code == 404
        assert client.get("/api/v1/orders", headers=other).json() == []
        assert client.get("/api/v1/orders", headers=waiter).json() == []
        assert len(client.get("/api/v1/orders", headers=admin).json()) == 1
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision", json={"approved": True}, headers=cashier
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision", json={"approved": True}, headers=waiter
            ).status_code
            == 403
        )
        rejected = client.post(
            f"/api/v1/orders/{order_id}/decision", json={"approved": False}, headers=admin
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "REJECTED"
        second = client.post(
            "/api/v1/orders",
            json=payload,
            headers={**customer, "Idempotency-Key": "delivery-2"},
        )
        assert second.status_code == 201, second.text
        approved = client.post(
            f"/api/v1/orders/{second.json()['id']}/decision",
            json={"approved": True},
            headers=admin,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert approved.json()["table_verified_at"] is None
        assert (
            client.get(f"/api/v1/orders/{order_id}", headers=customer).json()["status"]
            == "REJECTED"
        )
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision", json={"approved": True}, headers=admin
            ).status_code
            == 409
        )
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 0
    assert (
        await database.fetchval(
            "SELECT decided_by_user_id FROM public.orders WHERE id=$1", UUID(order_id)
        )
        == admin_id
    )


@pytest.mark.asyncio
async def test_manual_whatsapp_approved_and_disabled_product_blocked(
    database: asyncpg.Connection,
) -> None:
    product_id = await catalog(database)
    _, admin_email = await actor(database, "ADMIN")
    _, waiter_email = await actor(database, "WAITER")
    with api_client() as client:
        admin = bearer(client, admin_email)
        waiter = bearer(client, waiter_email)
        payload = {
            "modality": "PICKUP",
            "channel": "WHATSAPP",
            "contact_name": "Luis",
            "contact_phone": "999555444",
            "items": [{"product_id": str(product_id), "quantity": 2}],
        }
        headers = {**admin, "Idempotency-Key": "manual-wa-1"}
        assert (
            client.post(
                "/api/v1/orders/manual",
                json=payload,
                headers={**waiter, "Idempotency-Key": "waiter-not-admin"},
            ).status_code
            == 403
        )
        created = client.post("/api/v1/orders/manual", json=payload, headers=headers)
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "APPROVED"
        assert created.json()["channel"] == "WHATSAPP"
        assert created.json()["decided_at"] is not None
        phone = client.post(
            "/api/v1/orders/manual",
            json={**payload, "channel": "PHONE"},
            headers={**admin, "Idempotency-Key": "manual-phone"},
        )
        assert phone.status_code == 201, phone.text
        assert phone.json()["channel"] == "PHONE"
        assert phone.json()["status"] == "APPROVED"
        assert (
            client.post("/api/v1/orders/manual", json=payload, headers=headers).json()["id"]
            == created.json()["id"]
        )
        assert (
            client.post(
                "/api/v1/orders/manual",
                json={**payload, "channel": "APP"},
                headers={**admin, "Idempotency-Key": "manual-invalid"},
            ).status_code
            == 422
        )
        disabled = client.patch(
            f"/api/v1/catalog/products/{product_id}/availability",
            json={"is_available": False},
            headers=admin,
        )
        assert disabled.status_code == 200
        assert (
            client.post("/api/v1/orders/manual", json=payload, headers=headers).json()["id"]
            == created.json()["id"]
        )
        blocked = client.post(
            "/api/v1/orders/manual",
            json=payload,
            headers={**admin, "Idempotency-Key": "manual-disabled"},
        )
        assert blocked.status_code == 409
    assert await database.fetchval("SELECT count(*) FROM public.orders") == 2
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 8
    )


@pytest.mark.asyncio
async def test_customer_pickup_admin_approval_and_request_validation(
    database: asyncpg.Connection,
) -> None:
    product_id = await catalog(database)
    _, customer_email = await actor(database, "CUSTOMER")
    _, admin_email = await actor(database, "ADMIN")
    with api_client() as client:
        customer = bearer(client, customer_email)
        admin = bearer(client, admin_email)
        payload = {
            "modality": "PICKUP",
            "contact_name": "Eva",
            "contact_phone": "999000111",
            "items": [{"product_id": str(product_id), "quantity": 1}],
        }
        assert client.post("/api/v1/orders", json=payload, headers=customer).status_code == 422
        assert (
            client.post(
                "/api/v1/orders",
                json={**payload, "items": payload["items"] * 2},
                headers={**customer, "Idempotency-Key": "duplicates"},
            ).status_code
            == 422
        )
        created = client.post(
            "/api/v1/orders",
            json=payload,
            headers={**customer, "Idempotency-Key": "pickup-1"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "REQUESTED"
        assert created.json()["modality"] == "PICKUP"
        assert created.json()["table_id"] is None
        approved = client.post(
            f"/api/v1/orders/{created.json()['id']}/decision",
            json={"approved": True},
            headers=admin,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert approved.json()["table_verified_at"] is None
        assert len(client.get("/api/v1/orders", headers=customer).json()) == 1
    assert await database.fetchval("SELECT count(*) FROM public.payments") == 0
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
    dsn, _ = _test_database_target()
    engine = create_async_engine(dsn.replace("postgresql://", "postgresql+asyncpg://", 1))
    try:
        async with AsyncSession(engine) as session:
            order_for_advance = await SqlAlchemyAdvanceOrderReader(session).get_order(
                UUID(created.json()["id"]), lock=True
            )
            assert order_for_advance is not None
            assert order_for_advance.id == UUID(created.json()["id"])
            assert order_for_advance.modality == "PICKUP"
            assert order_for_advance.status == "APPROVED"
            assert order_for_advance.total_amount == Decimal("12.00")
            assert await SqlAlchemyAdvanceOrderReader(session).get_order(uuid4()) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_app_request_waits_for_manual_occupancy_change(
    database: asyncpg.Connection,
) -> None:
    product_id = await catalog(database)
    _, customer_email = await actor(database, "CUSTOMER")
    table_id = await database.fetchval(
        "INSERT INTO public.restaurant_tables(code) VALUES($1) RETURNING id",
        f"M-{uuid4().hex[:12]}",
    )
    payload = {
        "modality": "LOCAL",
        "table_id": str(table_id),
        "items": [{"product_id": str(product_id), "quantity": 1}],
    }
    async with async_api_clients() as (client, _):
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": customer_email, "password": ACTOR_PASSWORD},
        )
        assert login.status_code == 200, login.text
        headers = {
            "Authorization": "Bearer " + login.json()["access_token"],
            "Idempotency-Key": f"manual-occupancy-{uuid4()}",
        }
        task: asyncio.Task[httpx.Response] | None = None
        try:
            async with database.transaction():
                await database.execute(
                    "UPDATE public.restaurant_tables "
                    "SET is_occupied=TRUE, occupancy_started_at=clock_timestamp() WHERE id=$1",
                    table_id,
                )
                blocker_xid = await database.fetchval("SELECT pg_current_xact_id()::xid::text")
                task = asyncio.create_task(
                    client.post("/api/v1/orders", json=payload, headers=headers)
                )
                async with asyncio.timeout(10):
                    while True:
                        waiting = await database.fetchval(
                            "SELECT count(*) FROM pg_locks "
                            "WHERE locktype='transactionid' AND NOT granted "
                            "AND transactionid::text=$1",
                            blocker_xid,
                        )
                        if waiting >= 1:
                            break
                        if task.done():
                            pytest.fail(
                                "APP request completed before the concurrent occupancy change committed"
                            )
                        await asyncio.sleep(0.05)
            response = await asyncio.wait_for(task, timeout=10)
        finally:
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    assert response.status_code == 422, response.text
    assert (
        await database.fetchval(
            "SELECT is_occupied FROM public.restaurant_tables WHERE id=$1", table_id
        )
        is True
    )
    assert await database.fetchval("SELECT count(*) FROM public.orders") == 0
    assert await database.fetchval("SELECT count(*) FROM public.order_items") == 0
    assert await database.fetchval("SELECT count(*) FROM public.idempotency_requests") == 0


@pytest.mark.asyncio
async def test_simultaneous_local_approvals_cannot_assign_two_table_owners(
    database: asyncpg.Connection,
) -> None:
    product_id = await catalog(database)
    _, first_email = await actor(database, "CUSTOMER")
    _, second_email = await actor(database, "CUSTOMER")
    _, waiter_email = await actor(database, "WAITER")
    table_id = await database.fetchval(
        "INSERT INTO public.restaurant_tables(code) VALUES($1) RETURNING id",
        f"M-{uuid4().hex[:12]}",
    )
    payload = {
        "modality": "LOCAL",
        "table_id": str(table_id),
        "items": [{"product_id": str(product_id), "quantity": 1}],
    }
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with async_api_clients() as (first_client, second_client):
        first_login = await first_client.post(
            "/api/v1/auth/login", json={"email": first_email, "password": ACTOR_PASSWORD}
        )
        second_login = await second_client.post(
            "/api/v1/auth/login", json={"email": second_email, "password": ACTOR_PASSWORD}
        )
        waiter_login = await first_client.post(
            "/api/v1/auth/login", json={"email": waiter_email, "password": ACTOR_PASSWORD}
        )
        assert all(
            response.status_code == 200 for response in (first_login, second_login, waiter_login)
        )
        first_order = await first_client.post(
            "/api/v1/orders",
            json=payload,
            headers={
                "Authorization": "Bearer " + first_login.json()["access_token"],
                "Idempotency-Key": "first-owner",
            },
        )
        second_order = await second_client.post(
            "/api/v1/orders",
            json=payload,
            headers={
                "Authorization": "Bearer " + second_login.json()["access_token"],
                "Idempotency-Key": "second-owner",
            },
        )
        assert first_order.status_code == second_order.status_code == 201
        waiter_headers = {"Authorization": "Bearer " + waiter_login.json()["access_token"]}
        try:
            async with database.transaction():
                await database.fetchval(
                    "SELECT id FROM public.restaurant_tables WHERE id=$1 FOR UPDATE", table_id
                )
                blocker_xid = await database.fetchval("SELECT pg_current_xact_id()::xid::text")
                tasks = [
                    asyncio.create_task(
                        client.post(
                            f"/api/v1/orders/{response.json()['id']}/decision",
                            json={"approved": True, "table_verified": True},
                            headers=waiter_headers,
                        )
                    )
                    for client, response in (
                        (first_client, first_order),
                        (second_client, second_order),
                    )
                ]
                async with asyncio.timeout(10):
                    while True:
                        waiting = await database.fetchval(
                            "SELECT count(*) FROM pg_locks "
                            "WHERE locktype='transactionid' AND NOT granted "
                            "AND transactionid::text=$1",
                            blocker_xid,
                        )
                        if waiting >= 1:
                            break
                        if any(task.done() for task in tasks):
                            pytest.fail("A decision completed before the table lock barrier")
                        await asyncio.sleep(0.05)
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert (
        await database.fetchval("SELECT count(*) FROM public.orders WHERE status='APPROVED'") == 1
    )
    assert (
        await database.fetchval("SELECT count(*) FROM public.orders WHERE status='REQUESTED'") == 1
    )
    assert (
        await database.fetchval(
            "SELECT is_occupied FROM public.restaurant_tables WHERE id=$1", table_id
        )
        is True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("same_payload", [True, False], ids=["same-payload", "different-payload"])
async def test_concurrent_same_key_is_atomic_and_idempotent(
    database: asyncpg.Connection, same_payload: bool
) -> None:
    product_id = await catalog(database)
    customer_id, customer_email = await actor(database, "CUSTOMER")
    request_key = f"parallel-{uuid4()}"
    base_payload = {
        "modality": "PICKUP",
        "contact_name": "Ana",
        "contact_phone": "999111222",
        "items": [{"product_id": str(product_id), "quantity": 1}],
    }
    second_payload = (
        base_payload
        if same_payload
        else {
            **base_payload,
            "items": [{"product_id": str(product_id), "quantity": 2}],
        }
    )
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with async_api_clients() as (first_client, second_client):
        login = await first_client.post(
            "/api/v1/auth/login",
            json={"email": customer_email, "password": ACTOR_PASSWORD},
        )
        assert login.status_code == 200, login.text
        headers = {
            "Authorization": "Bearer " + login.json()["access_token"],
            "Idempotency-Key": request_key,
        }
        try:
            async with database.transaction():
                await database.fetchval(
                    "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                    f"CREATE_ORDER:{customer_id}:{request_key}",
                )
                tasks = [
                    asyncio.create_task(
                        client.post("/api/v1/orders", json=payload, headers=headers)
                    )
                    for client, payload in (
                        (first_client, base_payload),
                        (second_client, second_payload),
                    )
                ]
                async with asyncio.timeout(10):
                    while True:
                        waiting = await database.fetchval(
                            "SELECT count(*) FROM pg_locks "
                            "WHERE locktype = 'advisory' AND NOT granted "
                            "AND database = (SELECT oid FROM pg_database WHERE datname = current_database())"
                        )
                        if waiting >= 2:
                            break
                        if any(task.done() for task in tasks):
                            outcomes = [
                                str(task.exception())
                                if task.exception()
                                else task.result().status_code
                                for task in tasks
                                if task.done()
                            ]
                            pytest.fail(
                                f"A concurrent request finished before the lock barrier: {outcomes}"
                            )
                        await asyncio.sleep(0.05)
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    if same_payload:
        assert [response.status_code for response in responses] == [201, 201]
        assert responses[0].json()["id"] == responses[1].json()["id"]
    else:
        assert sorted(response.status_code for response in responses) == [201, 409]
    winner = next(response for response in responses if response.status_code == 201).json()
    async with database.transaction(isolation="repeatable_read", readonly=True):
        order_row = await database.fetchrow(
            "SELECT id,status,customer_user_id,total_amount FROM public.orders"
        )
        item_row = await database.fetchrow(
            "SELECT order_id,quantity,unit_price_snapshot FROM public.order_items"
        )
        request_row = await database.fetchrow(
            "SELECT actor_user_id,request_key,result_order_id,completed_at "
            "FROM public.idempotency_requests"
        )
        assert await database.fetchval("SELECT count(*) FROM public.orders") == 1
        assert await database.fetchval("SELECT count(*) FROM public.order_items") == 1
        assert await database.fetchval("SELECT count(*) FROM public.idempotency_requests") == 1
        assert await database.fetchval("SELECT count(*) FROM public.payments") == 0
        assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
        assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 0
        assert (
            await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
            == 8
        )
        assert order_row is not None and item_row is not None and request_row is not None
        assert order_row["id"] == UUID(winner["id"])
        assert order_row["status"] == "REQUESTED"
        assert order_row["customer_user_id"] == customer_id
        assert item_row["order_id"] == order_row["id"]
        assert item_row["quantity"] == winner["lines"][0]["quantity"]
        assert order_row["total_amount"] == item_row["unit_price_snapshot"] * item_row["quantity"]
        assert request_row["actor_user_id"] == customer_id
        assert request_row["request_key"] == request_key
        assert request_row["result_order_id"] == order_row["id"]
        assert request_row["completed_at"] is not None
