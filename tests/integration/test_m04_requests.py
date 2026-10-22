"""HTTP + PostgreSQL checks for 08.04 without confirming orders."""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from restaurant_app.core.config import Settings
from restaurant_app.main import create_app
from restaurant_app.modules.m01_access.adapters.outbound.password_hasher import (
    Argon2PasswordHasher,
)
from tests.integration.test_initial_migration import _test_database_target

pytest_plugins = ("tests.integration.test_initial_migration",)
pytestmark = pytest.mark.integration

JWT_SECRET = "m04-integration-jwt-secret-with-more-than-32-characters"
ACTOR_PASSWORD = "m04-integration-password"


@contextmanager
def api_client() -> Iterator[TestClient]:
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
    with TestClient(application) as client:
        yield client


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
