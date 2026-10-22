"""Real PostgreSQL + HTTP verification of the M03 table slice."""

from collections.abc import Iterator
from contextlib import contextmanager
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

JWT_SECRET = "m03-integration-jwt-secret-with-more-than-32-characters"
ACTOR_PASSWORD = "m03-integration-password"


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


async def create_actor(database: asyncpg.Connection, role: str) -> tuple[UUID, str]:
    email = f"{role.lower()}-{uuid4()}@example.test"
    actor_id = await database.fetchval(
        """
        INSERT INTO public.users (display_name, email, password_hash)
        VALUES ($1, $2, $3) RETURNING id
        """,
        role,
        email,
        Argon2PasswordHasher().hash(ACTOR_PASSWORD),
    )
    await database.execute(
        "INSERT INTO public.user_roles (user_id, role_code) VALUES ($1, $2)", actor_id, role
    )
    return actor_id, email


def bearer(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": ACTOR_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.mark.asyncio
async def test_admin_distribution_and_public_selection(database: asyncpg.Connection) -> None:
    admin_id, admin_email = await create_actor(database, "ADMIN")
    _, waiter_email = await create_actor(database, "WAITER")
    with api_client() as client:
        admin = bearer(client, admin_email)
        waiter = bearer(client, waiter_email)
        assert client.get("/api/v1/tables").json() == []
        created = client.post(
            "/api/v1/tables", json={"code": " M-01 ", "area_label": " Salón "}, headers=admin
        )
        assert created.status_code == 201, created.text
        table_id = created.json()["id"]
        assert created.json()["code"] == "M-01"
        assert created.json()["area_label"] == "Salón"
        assert created.json()["is_occupied"] is False
        assert created.json()["updated_by_user_id"] == str(admin_id)
        created_at = created.json()["updated_at"]
        duplicate = client.post("/api/v1/tables", json={"code": "M-01"}, headers=admin)
        assert duplicate.status_code == 409
        public = client.get("/api/v1/tables")
        assert public.status_code == 200
        assert public.json()[0] == {
            "id": table_id,
            "code": "M-01",
            "area_label": "Salón",
            "is_occupied": False,
        }
        detail = client.get(f"/api/v1/tables/{table_id}", headers=waiter)
        assert detail.status_code == 200
        assert detail.json()["updated_at"] is not None
        updated = client.patch(
            f"/api/v1/tables/{table_id}",
            json={"code": "M-02", "area_label": None},
            headers=admin,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["code"] == "M-02"
        assert updated.json()["area_label"] is None
        assert updated.json()["updated_at"] != created_at
        assert client.get("/api/v1/tables").json()[0]["code"] == "M-02"
        second = client.post("/api/v1/tables", json={"code": "M-03"}, headers=admin)
        assert second.status_code == 201
        assert (
            client.patch(
                f"/api/v1/tables/{table_id}", json={"code": "M-03"}, headers=admin
            ).status_code
            == 409
        )
        assert (
            client.patch(
                f"/api/v1/tables/{table_id}", json={"code": "M-03"}, headers=waiter
            ).status_code
            == 403
        )
        assert client.patch(f"/api/v1/tables/{table_id}", json={}, headers=admin).status_code == 422
        assert client.post("/api/v1/tables", json={"code": "  "}, headers=admin).status_code == 422
        assert client.get(f"/api/v1/tables/{uuid4()}", headers=waiter).status_code == 404
        assert (
            client.patch(
                f"/api/v1/tables/{uuid4()}", json={"code": "M-04"}, headers=admin
            ).status_code
            == 404
        )
    row = await database.fetchrow(
        "SELECT code, area_label, is_occupied, updated_by_user_id, updated_at "
        "FROM public.restaurant_tables WHERE id = $1",
        UUID(table_id),
    )
    assert row is not None
    assert row["code"] == "M-02"
    assert row["area_label"] is None
    assert row["is_occupied"] is False
    assert row["updated_by_user_id"] == admin_id
    assert row["updated_at"] is not None
    assert await database.fetchval("SELECT count(*) FROM public.orders") == 0


@pytest.mark.asyncio
async def test_occupancy_roles_audit_and_idempotent_repeat(database: asyncpg.Connection) -> None:
    admin_id, admin_email = await create_actor(database, "ADMIN")
    waiter_id, waiter_email = await create_actor(database, "WAITER")
    _, customer_email = await create_actor(database, "CUSTOMER")
    _, cashier_email = await create_actor(database, "CASHIER")
    super_id, super_email = await create_actor(database, "SUPER_ADMIN")
    with api_client() as client:
        admin = bearer(client, admin_email)
        waiter = bearer(client, waiter_email)
        customer = bearer(client, customer_email)
        cashier = bearer(client, cashier_email)
        super_admin = bearer(client, super_email)
        created = client.post("/api/v1/tables", json={"code": "M-10"}, headers=admin)
        assert created.status_code == 201
        table_id = created.json()["id"]
        endpoint = f"/api/v1/tables/{table_id}/occupancy"
        assert client.patch(endpoint, json={"is_occupied": True}).status_code == 401
        assert (
            client.patch(endpoint, json={"is_occupied": True}, headers=customer).status_code == 403
        )
        assert (
            client.patch(endpoint, json={"is_occupied": True}, headers=cashier).status_code == 403
        )
        guest = client.post("/api/v1/auth/guest")
        assert guest.status_code == 201
        guest_bearer = {"Authorization": "Bearer " + guest.json()["access_token"]}
        assert (
            client.patch(endpoint, json={"is_occupied": True}, headers=guest_bearer).status_code
            == 403
        )
        assert client.get(f"/api/v1/tables/{table_id}", headers=customer).status_code == 403
        occupied = client.patch(endpoint, json={"is_occupied": True}, headers=waiter)
        assert occupied.status_code == 200, occupied.text
        assert occupied.json()["is_occupied"] is True
        assert occupied.json()["updated_by_user_id"] == str(waiter_id)
        occupied_at = occupied.json()["updated_at"]
        repeated = client.patch(endpoint, json={"is_occupied": True}, headers=admin)
        assert repeated.status_code == 200
        assert repeated.json()["updated_at"] == occupied_at
        assert repeated.json()["updated_by_user_id"] == str(waiter_id)
        assert (
            client.patch(endpoint, json={"is_occupied": False}, headers=waiter).status_code == 403
        )
        assert client.get("/api/v1/tables").json()[0]["is_occupied"] is True
        released = client.patch(endpoint, json={"is_occupied": False}, headers=admin)
        assert released.status_code == 200, released.text
        assert released.json()["is_occupied"] is False
        assert released.json()["updated_by_user_id"] == str(admin_id)
        assert released.json()["updated_at"] != occupied_at
        assert client.patch(endpoint, json={"is_occupied": True}, headers=waiter).status_code == 200
        assert (
            client.patch(endpoint, json={"is_occupied": False}, headers=super_admin).status_code
            == 200
        )
        assert (
            client.patch(
                f"/api/v1/tables/{uuid4()}/occupancy",
                json={"is_occupied": True},
                headers=waiter,
            ).status_code
            == 404
        )
        assert client.patch(endpoint, json={"is_occupied": "yes"}, headers=admin).status_code == 422
    row = await database.fetchrow(
        "SELECT is_occupied, updated_by_user_id, updated_at "
        "FROM public.restaurant_tables WHERE id = $1",
        UUID(table_id),
    )
    assert row is not None
    assert row["is_occupied"] is False
    assert row["updated_by_user_id"] == super_id
    assert row["updated_at"] is not None
    assert await database.fetchval("SELECT count(*) FROM public.orders") == 0
