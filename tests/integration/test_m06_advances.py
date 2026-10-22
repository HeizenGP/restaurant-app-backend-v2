"""08.05 HTTP and PostgreSQL checks without ConfirmOrder or cashier collections."""

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
from restaurant_app.modules.m06_payments.public import SqlAlchemyAdvanceReader
from tests.integration.test_initial_migration import _test_database_target

pytest_plugins = ("tests.integration.test_initial_migration",)
pytestmark = pytest.mark.integration

JWT_SECRET = "m06-integration-jwt-secret-with-more-than-32-characters"
ACTOR_PASSWORD = "m06-integration-password"


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


async def product(database: asyncpg.Connection, price: str) -> UUID:
    category_id = await database.fetchval(
        "INSERT INTO public.categories(name) VALUES($1) RETURNING id", f"Platos-{uuid4()}"
    )
    return await database.fetchval(
        "INSERT INTO public.products(category_id,name,price,stock_qty,is_available) "
        "VALUES($1,'Chaufa',$2,8,TRUE) RETURNING id",
        category_id,
        Decimal(price),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("modality", "price", "required", "remaining", "reviewer_role"),
    [
        ("PICKUP", "10.01", "5.01", "5.00", "ADMIN"),
        ("DELIVERY", "80.00", "40.00", "40.00", "SUPER_ADMIN"),
        ("PICKUP", "0.01", "0.01", "0.00", "ADMIN"),
    ],
)
async def test_advance_quote_verification_permissions_and_single_payment(
    database: asyncpg.Connection,
    modality: str,
    price: str,
    required: str,
    remaining: str,
    reviewer_role: str,
) -> None:
    product_id = await product(database, price)
    _, customer_email = await actor(database, "CUSTOMER")
    _, other_email = await actor(database, "CUSTOMER")
    reviewer_id, reviewer_email = await actor(database, reviewer_role)
    _, second_admin_email = await actor(database, "ADMIN")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        other = bearer(client, other_email)
        reviewer = bearer(client, reviewer_email)
        second_admin = bearer(client, second_admin_email)
        cashier = bearer(client, cashier_email)
        payload = {
            "modality": modality,
            "contact_name": "Ana",
            "contact_phone": "999111222",
            "items": [{"product_id": str(product_id), "quantity": 1}],
        }
        if modality == "DELIVERY":
            payload["delivery_address"] = "Av. Lima 123"
        created = client.post(
            "/api/v1/orders", json=payload, headers={**customer, "Idempotency-Key": "order"}
        )
        assert created.status_code == 201, created.text
        order_id = created.json()["id"]
        quote_path = f"/api/v1/orders/{order_id}/advance"
        verify_path = f"{quote_path}/verify"
        quote = client.get(quote_path, headers=customer)
        assert quote.status_code == 200, quote.text
        assert Decimal(quote.json()["required_amount"]) == Decimal(required)
        assert Decimal(quote.json()["verified_amount"]) == Decimal("0.00")
        assert Decimal(quote.json()["remaining_amount"]) == Decimal(price)
        assert client.get(quote_path, headers=other).status_code == 404
        assert client.get(quote_path, headers=cashier).status_code == 404
        assert client.get(quote_path, headers=reviewer).status_code == 200
        assert client.get(quote_path).status_code == 401
        assert (
            client.post(verify_path, headers={**cashier, "Idempotency-Key": "no"}).status_code
            == 403
        )
        assert (
            client.post(verify_path, headers={**customer, "Idempotency-Key": "no"}).status_code
            == 403
        )
        assert (
            client.post(verify_path, headers={**reviewer, "Idempotency-Key": "before"}).status_code
            == 409
        )
        assert await database.fetchval("SELECT count(*) FROM public.payments") == 0
        approved = client.post(
            f"/api/v1/orders/{order_id}/decision",
            json={"approved": True},
            headers=reviewer,
        )
        assert approved.status_code == 200, approved.text
        assert client.post(verify_path, headers=reviewer).status_code == 422
        verified = client.post(verify_path, headers={**reviewer, "Idempotency-Key": "advance-1"})
        assert verified.status_code == 200, verified.text
        assert Decimal(verified.json()["required_amount"]) == Decimal(required)
        assert Decimal(verified.json()["verified_amount"]) == Decimal(required)
        assert Decimal(verified.json()["remaining_amount"]) == Decimal(remaining)
        assert verified.json()["verified_at"] is not None
        replay = client.post(verify_path, headers={**reviewer, "Idempotency-Key": "advance-1"})
        assert replay.status_code == 200 and replay.json() == verified.json()
        second_key = client.post(
            verify_path, headers={**second_admin, "Idempotency-Key": "advance-2"}
        )
        assert second_key.status_code == 200 and second_key.json() == verified.json()
        assert (
            client.post(
                f"/api/v1/orders/{uuid4()}/advance/verify",
                headers={**reviewer, "Idempotency-Key": "advance-1"},
            ).status_code
            == 409
        )
        assert client.get(quote_path, headers=customer).json() == verified.json()
    row = await database.fetchrow(
        "SELECT kind,amount,method_code,recorded_by_user_id,recorded_at,operation_request_id "
        "FROM public.payments WHERE order_id=$1",
        UUID(order_id),
    )
    assert row is not None
    assert row["kind"] == "ADVANCE"
    assert row["amount"] == Decimal(required)
    assert row["method_code"] is None
    assert row["recorded_by_user_id"] == reviewer_id
    assert row["recorded_at"] is not None
    assert await database.fetchval("SELECT count(*) FROM public.payments") == 1
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests "
            "WHERE operation='VERIFY_ADVANCE' AND result_order_id=$1",
            UUID(order_id),
        )
        == 2
    )
    assert (
        await database.fetchval(
            "SELECT operation FROM public.idempotency_requests WHERE id=$1",
            row["operation_request_id"],
        )
        == "VERIFY_ADVANCE"
    )
    assert (
        await database.fetchval("SELECT status FROM public.orders WHERE id=$1", UUID(order_id))
        == "APPROVED"
    )
    assert (
        await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
        == 8
    )
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0


@pytest.mark.asyncio
async def test_manual_channel_needs_advance_but_local_and_rejected_do_not_receive_one(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, "20.00")
    _, admin_email = await actor(database, "ADMIN")
    _, customer_email = await actor(database, "CUSTOMER")
    table_id = await database.fetchval(
        "INSERT INTO public.restaurant_tables(code) VALUES($1) RETURNING id",
        f"T-{uuid4().hex[:12]}",
    )
    with api_client() as client:
        admin = bearer(client, admin_email)
        customer = bearer(client, customer_email)
        items = [{"product_id": str(product_id), "quantity": 1}]
        manual = client.post(
            "/api/v1/orders/manual",
            json={
                "modality": "PICKUP",
                "channel": "WHATSAPP",
                "contact_name": "Luis",
                "contact_phone": "999555444",
                "items": items,
            },
            headers={**admin, "Idempotency-Key": "manual-pickup"},
        )
        assert manual.status_code == 201, manual.text
        assert manual.json()["status"] == "APPROVED"
        manual_advance = client.post(
            f"/api/v1/orders/{manual.json()['id']}/advance/verify",
            headers={**admin, "Idempotency-Key": "manual-advance"},
        )
        assert manual_advance.status_code == 200, manual_advance.text
        assert Decimal(manual_advance.json()["verified_amount"]) == Decimal("10.00")
        local = client.post(
            "/api/v1/orders",
            json={"modality": "LOCAL", "table_id": str(table_id), "items": items},
            headers={**customer, "Idempotency-Key": "local"},
        )
        assert local.status_code == 201, local.text
        assert (
            client.post(
                f"/api/v1/orders/{local.json()['id']}/advance/verify",
                headers={**admin, "Idempotency-Key": "local-advance"},
            ).status_code
            == 409
        )
        pickup = client.post(
            "/api/v1/orders",
            json={
                "modality": "PICKUP",
                "contact_name": "Ana",
                "contact_phone": "999111222",
                "items": items,
            },
            headers={**customer, "Idempotency-Key": "pickup-rejected"},
        )
        assert pickup.status_code == 201, pickup.text
        rejected = client.post(
            f"/api/v1/orders/{pickup.json()['id']}/decision",
            json={"approved": False},
            headers=admin,
        )
        assert rejected.status_code == 200, rejected.text
        assert (
            client.post(
                f"/api/v1/orders/{pickup.json()['id']}/advance/verify",
                headers={**admin, "Idempotency-Key": "rejected-advance"},
            ).status_code
            == 409
        )
    assert await database.fetchval("SELECT count(*) FROM public.payments") == 1
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0


@pytest.mark.asyncio
async def test_simultaneous_same_key_verification_records_one_advance(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, "12.00")
    _, customer_email = await actor(database, "CUSTOMER")
    admin_id, admin_email = await actor(database, "ADMIN")
    request_key = f"parallel-{uuid4()}"
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with async_api_clients() as (first_client, second_client):
        admin_login = await first_client.post(
            "/api/v1/auth/login", json={"email": admin_email, "password": ACTOR_PASSWORD}
        )
        customer_login = await first_client.post(
            "/api/v1/auth/login", json={"email": customer_email, "password": ACTOR_PASSWORD}
        )
        assert admin_login.status_code == customer_login.status_code == 200
        admin = {"Authorization": "Bearer " + admin_login.json()["access_token"]}
        customer = {"Authorization": "Bearer " + customer_login.json()["access_token"]}
        created = await first_client.post(
            "/api/v1/orders",
            json={
                "modality": "PICKUP",
                "contact_name": "Ana",
                "contact_phone": "999111222",
                "items": [{"product_id": str(product_id), "quantity": 1}],
            },
            headers={**customer, "Idempotency-Key": "order"},
        )
        assert created.status_code == 201, created.text
        order_id = UUID(created.json()["id"])
        approved = await first_client.post(
            f"/api/v1/orders/{order_id}/decision", json={"approved": True}, headers=admin
        )
        assert approved.status_code == 200, approved.text
        headers = {**admin, "Idempotency-Key": request_key}
        try:
            async with database.transaction():
                await database.fetchval(
                    "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                    f"VERIFY_ADVANCE:{admin_id}:{request_key}",
                )
                tasks = [
                    asyncio.create_task(
                        client.post(f"/api/v1/orders/{order_id}/advance/verify", headers=headers)
                    )
                    for client in (first_client, second_client)
                ]
                async with asyncio.timeout(10):
                    while True:
                        waiting = await database.fetchval(
                            "SELECT count(*) FROM pg_locks "
                            "WHERE locktype='advisory' AND NOT granted "
                            "AND database=(SELECT oid FROM pg_database WHERE datname=current_database())"
                        )
                        if waiting >= 2:
                            break
                        if any(task.done() for task in tasks):
                            pytest.fail("A verification completed before the advisory lock barrier")
                        await asyncio.sleep(0.05)
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    async with database.transaction(isolation="repeatable_read", readonly=True):
        assert await database.fetchval("SELECT count(*) FROM public.payments") == 1
        assert (
            await database.fetchval(
                "SELECT count(*) FROM public.idempotency_requests WHERE operation='VERIFY_ADVANCE'"
            )
            == 1
        )
        assert await database.fetchval(
            "SELECT amount FROM public.payments WHERE order_id=$1", order_id
        ) == Decimal("6.00")
        assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 0
        assert (
            await database.fetchval("SELECT stock_qty FROM public.products WHERE id=$1", product_id)
            == 8
        )
    dsn, _ = _test_database_target()
    engine = create_async_engine(dsn.replace("postgresql://", "postgresql+asyncpg://", 1))
    try:
        async with AsyncSession(engine) as session:
            advance = await SqlAlchemyAdvanceReader(session).get_verified_advance(order_id)
            assert advance is not None
            assert advance.order_id == order_id
            assert advance.amount == Decimal("6.00")
            assert await SqlAlchemyAdvanceReader(session).get_verified_advance(uuid4()) is None
    finally:
        await engine.dispose()
