"""08.06 kitchen reads and transitions against an explicitly authorized PostgreSQL test DB."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
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

JWT_SECRET = "m05-integration-jwt-secret-with-more-than-32-characters"
ACTOR_PASSWORD = "m05-integration-password"


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


async def seed_ticket(
    database: asyncpg.Connection,
    *,
    actor_id: UUID,
    modality: str,
    confirmed: bool = True,
    line_count: int = 3,
) -> tuple[UUID, UUID]:
    category_id = await database.fetchval(
        "INSERT INTO public.categories(name) VALUES($1) RETURNING id", f"Platos-{uuid4()}"
    )
    table_id = None
    if modality == "LOCAL":
        table_id = await database.fetchval(
            "INSERT INTO public.restaurant_tables(code) VALUES($1) RETURNING id",
            f"M-{uuid4().hex[:12]}",
        )
    async with database.transaction():
        order_id = await database.fetchval(
            """INSERT INTO public.orders (
                modality, channel, status, created_by_user_id, table_id, delivery_address,
                total_amount, confirmed_by_user_id, confirmed_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id""",
            modality,
            "WAITER" if modality == "LOCAL" else "PHONE",
            "REQUESTED",
            actor_id,
            table_id,
            "Av. Lima 123" if modality == "DELIVERY" else None,
            Decimal(str(10 * sum(range(1, line_count + 1)))),
            None,
            None,
        )
        for index in range(1, line_count + 1):
            product_id = await database.fetchval(
                """INSERT INTO public.products(category_id,name,price,stock_qty)
                VALUES($1,$2,10.00,30) RETURNING id""",
                category_id,
                f"Plato {index}",
            )
            await database.execute(
                """INSERT INTO public.order_items(
                    order_id,product_id,product_name_snapshot,quantity,unit_price_snapshot
                ) VALUES($1,$2,$3,$4,10.00)""",
                order_id,
                product_id,
                f"Plato {index}",
                index,
            )
        if confirmed:
            await database.execute(
                """UPDATE public.orders
                SET status='CONFIRMED', confirmed_by_user_id=$2, confirmed_at=$3
                WHERE id=$1""",
                order_id,
                actor_id,
                datetime.now(UTC),
            )
        ticket_id = await database.fetchval(
            "INSERT INTO public.kitchen_tickets(order_id) VALUES($1) RETURNING id", order_id
        )
    return order_id, ticket_id


@pytest.mark.asyncio
async def test_kitchen_list_filters_detail_permissions_and_manual_ready(
    database: asyncpg.Connection,
) -> None:
    kitchen_id, kitchen_email = await actor(database, "KITCHEN")
    _, second_kitchen_email = await actor(database, "KITCHEN")
    _, super_email = await actor(database, "SUPER_ADMIN")
    _, admin_email = await actor(database, "ADMIN")
    _, waiter_email = await actor(database, "WAITER")
    _, customer_email = await actor(database, "CUSTOMER")
    local_order, local_ticket = await seed_ticket(database, actor_id=kitchen_id, modality="LOCAL")
    _, pickup_ticket = await seed_ticket(database, actor_id=kitchen_id, modality="PICKUP")
    _, delivery_ticket = await seed_ticket(database, actor_id=kitchen_id, modality="DELIVERY")
    _, pending_ticket = await seed_ticket(
        database, actor_id=kitchen_id, modality="LOCAL", confirmed=False
    )
    path = "/api/v1/kitchen/tickets"
    with api_client() as client:
        kitchen = bearer(client, kitchen_email)
        second_kitchen = bearer(client, second_kitchen_email)
        super_admin = bearer(client, super_email)
        for email in (admin_email, waiter_email, customer_email):
            unauthorized = bearer(client, email)
            assert client.get(path, headers=unauthorized).status_code == 403
            assert client.get(f"{path}/{local_ticket}", headers=unauthorized).status_code == 403
            assert (
                client.post(f"{path}/{local_ticket}/start", headers=unauthorized).status_code == 403
            )
            assert (
                client.post(
                    f"{path}/{local_ticket}/ready",
                    headers=unauthorized,
                    json={"all_items_prepared": True},
                ).status_code
                == 403
            )
        assert client.get(path).status_code == 401
        guest_session = client.post("/api/v1/auth/guest")
        assert guest_session.status_code == 201
        guest = {"Authorization": "Bearer " + guest_session.json()["access_token"]}
        assert client.get(path, headers=guest).status_code == 403
        assert client.get(path, headers=super_admin).status_code == 200
        listed = client.get(path, headers=kitchen)
        assert listed.status_code == 200, listed.text
        assert {item["id"] for item in listed.json()} == {
            str(local_ticket),
            str(pickup_ticket),
            str(delivery_ticket),
        }
        for modality, ticket_id in (
            ("LOCAL", local_ticket),
            ("PICKUP", pickup_ticket),
            ("DELIVERY", delivery_ticket),
        ):
            filtered = client.get(path, params={"modality": modality}, headers=kitchen)
            assert filtered.status_code == 200
            assert [item["id"] for item in filtered.json()] == [str(ticket_id)]
        assert client.get(path, params={"modality": "INVALID"}, headers=kitchen).status_code == 422
        assert client.get(f"{path}/{pending_ticket}", headers=kitchen).status_code == 404
        assert client.post(f"{path}/{pending_ticket}/start", headers=kitchen).status_code == 404
        assert (
            client.post(
                f"{path}/{pending_ticket}/ready",
                headers=kitchen,
                json={"all_items_prepared": True},
            ).status_code
            == 404
        )
        assert client.get(f"{path}/{uuid4()}", headers=kitchen).status_code == 404
        detail = client.get(f"{path}/{local_ticket}", headers=kitchen)
        assert detail.status_code == 200
        assert detail.json()["order_id"] == str(local_order)
        assert sorted(
            (line["product_name_snapshot"], line["quantity"]) for line in detail.json()["lines"]
        ) == [
            ("Plato 1", 1),
            ("Plato 2", 2),
            ("Plato 3", 3),
        ]
        ready_path = f"{path}/{local_ticket}/ready"
        assert (
            client.post(ready_path, headers=kitchen, json={"all_items_prepared": True}).status_code
            == 409
        )
        assert client.post(ready_path, headers=kitchen).status_code == 422
        assert (
            client.post(ready_path, headers=kitchen, json={"all_items_prepared": 1}).status_code
            == 422
        )
        started = client.post(f"{path}/{local_ticket}/start", headers=kitchen)
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "PREPARING"
        assert started.json()["started_by_user_id"] == str(kitchen_id)
        assert started.json()["started_at"] is not None
        replay_start = client.post(f"{path}/{local_ticket}/start", headers=second_kitchen)
        assert replay_start.status_code == 200 and replay_start.json() == started.json()
        assert (
            client.post(ready_path, headers=kitchen, json={"all_items_prepared": False}).status_code
            == 409
        )
        assert client.get(f"{path}/{local_ticket}", headers=kitchen).json() == started.json()
        ready = client.post(ready_path, headers=kitchen, json={"all_items_prepared": True})
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "READY"
        assert ready.json()["ready_at"] is not None
        assert ready.json()["ready_by_user_id"] == str(kitchen_id)
        replay_ready = client.post(
            ready_path, headers=second_kitchen, json={"all_items_prepared": True}
        )
        assert replay_ready.status_code == 200 and replay_ready.json() == ready.json()
        assert client.post(f"{path}/{local_ticket}/start", headers=kitchen).status_code == 409
    saved = await database.fetchrow(
        "SELECT status, started_by_user_id, ready_by_user_id FROM public.kitchen_tickets WHERE id=$1",
        local_ticket,
    )
    assert saved is not None
    assert (saved["status"], saved["started_by_user_id"], saved["ready_by_user_id"]) == (
        "READY",
        kitchen_id,
        kitchen_id,
    )
    assert await database.fetchval("SELECT count(*) FROM public.kitchen_tickets") == 4
    assert await database.fetchval("SELECT count(*) FROM public.payments") == 0
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 0
    assert (
        await database.fetchval("SELECT status FROM public.orders WHERE id=$1", local_order)
        == "CONFIRMED"
    )


@pytest.mark.asyncio
async def test_two_kitchen_workers_replay_one_transition(database: asyncpg.Connection) -> None:
    first_id, first_email = await actor(database, "KITCHEN")
    second_id, second_email = await actor(database, "KITCHEN")
    _, ticket_id = await seed_ticket(database, actor_id=first_id, modality="PICKUP", line_count=1)
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
            first_login, second_login = await asyncio.gather(
                first.post(
                    "/api/v1/auth/login", json={"email": first_email, "password": ACTOR_PASSWORD}
                ),
                second.post(
                    "/api/v1/auth/login", json={"email": second_email, "password": ACTOR_PASSWORD}
                ),
            )
            assert first_login.status_code == second_login.status_code == 200
            first_auth = {"Authorization": "Bearer " + first_login.json()["access_token"]}
            second_auth = {"Authorization": "Bearer " + second_login.json()["access_token"]}
            path = f"/api/v1/kitchen/tickets/{ticket_id}"
            starts = await asyncio.gather(
                first.post(f"{path}/start", headers=first_auth),
                second.post(f"{path}/start", headers=second_auth),
            )
            assert [response.status_code for response in starts] == [200, 200]
            assert starts[0].json() == starts[1].json()
            ready = await asyncio.gather(
                first.post(f"{path}/ready", headers=first_auth, json={"all_items_prepared": True}),
                second.post(
                    f"{path}/ready", headers=second_auth, json={"all_items_prepared": True}
                ),
            )
            assert [response.status_code for response in ready] == [200, 200]
            assert ready[0].json() == ready[1].json()
    finally:
        await application.state.database.dispose()
    row = await database.fetchrow(
        "SELECT status, started_by_user_id, ready_by_user_id FROM public.kitchen_tickets WHERE id=$1",
        ticket_id,
    )
    assert row is not None
    assert row["status"] == "READY"
    assert row["started_by_user_id"] in {first_id, second_id}
    assert row["ready_by_user_id"] in {first_id, second_id}
