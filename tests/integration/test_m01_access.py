"""PostgreSQL + HTTP integration coverage for ETAPA 08 block 08.01."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import unquote, urlsplit
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from restaurant_app.core.config import Settings
from restaurant_app.main import create_app
from tests.integration.test_initial_migration import _test_database_target

pytest_plugins = ("tests.integration.test_initial_migration",)

pytestmark = pytest.mark.integration

JWT_SECRET = "integration-test-jwt-secret-with-more-than-32-characters"


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


def register(
    client: TestClient,
    *,
    email: str,
    password: str = "correct-password",
    name: str = "Integration Client",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(
    client: TestClient,
    *,
    email: str,
    password: str = "correct-password",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_registration_login_refresh_and_logout_persist_only_hashes(
    database: asyncpg.Connection,
) -> None:
    with api_client() as client:
        user = register(client, email="client@example.test")

        stored = await database.fetchrow(
            """
            SELECT u.password_hash, array_agg(ur.role_code ORDER BY ur.role_code) AS roles
            FROM public.users AS u
            JOIN public.user_roles AS ur ON ur.user_id = u.id
            WHERE u.id = $1
            GROUP BY u.password_hash
            """,
            UUID(user["id"]),
        )
        assert stored is not None
        assert stored["password_hash"].startswith("$argon2id$")
        assert "correct-password" not in stored["password_hash"]
        assert stored["roles"] == ["CUSTOMER"]
        assert "password" not in user and "password_hash" not in user

        duplicate = client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "Duplicate",
                "email": "CLIENT@example.test",
                "password": "another-password",
            },
        )
        assert duplicate.status_code == 409

        wrong_email = client.post(
            "/api/v1/auth/login",
            json={"email": "missing@example.test", "password": "wrong-password"},
        )
        wrong_password = client.post(
            "/api/v1/auth/login",
            json={"email": "client@example.test", "password": "wrong-password"},
        )
        assert wrong_email.status_code == wrong_password.status_code == 401
        assert (
            wrong_email.json() == wrong_password.json() == {"detail": "Invalid email or password"}
        )

        authenticated = login(client, email="client@example.test")
        refresh_token = authenticated["refresh_token"]
        assert refresh_token
        session_row = await database.fetchrow(
            """
            SELECT renewal_token_hash, revoked_at
            FROM public.auth_sessions
            WHERE user_id = $1
            """,
            UUID(user["id"]),
        )
        assert session_row is not None
        original_digest = session_row["renewal_token_hash"]
        assert len(original_digest) == 64
        assert refresh_token not in original_digest
        assert original_digest != "pending"

        refreshed = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refreshed.status_code == 200, refreshed.text
        replacement_refresh = refreshed.json()["refresh_token"]
        assert replacement_refresh and replacement_refresh != refresh_token
        replacement_digest = await database.fetchval(
            "SELECT renewal_token_hash FROM public.auth_sessions WHERE user_id = $1",
            UUID(user["id"]),
        )
        assert replacement_digest not in {None, original_digest}

        replay = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert replay.status_code == 401
        assert replay.headers["www-authenticate"] == "Bearer"

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
        )
        assert logout.status_code == 204
        assert await database.fetchval(
            "SELECT revoked_at IS NOT NULL FROM public.auth_sessions WHERE user_id = $1",
            UUID(user["id"]),
        )
        rejected_after_logout = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": replacement_refresh},
        )
        assert rejected_after_logout.status_code == 401
        revoked_access = client.post(
            f"/api/v1/users/{user['id']}/roles",
            json={"role": "WAITER"},
            headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
        )
        assert revoked_access.status_code == 401


async def test_guest_session_is_limited_and_has_no_refresh(
    database: asyncpg.Connection,
) -> None:
    with api_client() as client:
        target = register(client, email="target@example.test")
        guest = client.post("/api/v1/auth/guest")

        assert guest.status_code == 201
        payload = guest.json()
        assert payload["session_kind"] == "GUEST"
        assert payload["user"] is None
        assert payload["refresh_token"] is None

        session = await database.fetchrow(
            """
            SELECT kind, user_id, renewal_token_hash, revoked_at
            FROM public.auth_sessions
            WHERE kind = 'GUEST'
            """
        )
        assert session is not None
        assert session["user_id"] is None
        assert session["renewal_token_hash"] is None

        forbidden = client.post(
            f"/api/v1/users/{target['id']}/roles",
            json={"role": "WAITER"},
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        assert forbidden.status_code == 403

        missing = client.post(
            f"/api/v1/users/{target['id']}/roles",
            json={"role": "WAITER"},
        )
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == "Bearer"


async def test_roles_accumulate_and_authorization_is_enforced_at_http_and_handler(
    database: asyncpg.Connection,
) -> None:
    with api_client() as client:
        admin = register(client, email="admin@example.test", name="Admin")
        target = register(client, email="staff@example.test", name="Staff")
        super_admin = register(client, email="root@example.test", name="Root")
        await database.executemany(
            "INSERT INTO public.user_roles (user_id, role_code) VALUES ($1, $2)",
            [
                (UUID(admin["id"]), "ADMIN"),
                (UUID(super_admin["id"]), "SUPER_ADMIN"),
            ],
        )

        admin_auth = login(client, email="admin@example.test")
        target_auth_before_promotion = login(client, email="staff@example.test")
        assigned = client.post(
            f"/api/v1/users/{target['id']}/roles",
            json={"role": "CASHIER"},
            headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["roles"] == ["CASHIER", "CUSTOMER"]

        duplicate = client.post(
            f"/api/v1/users/{target['id']}/roles",
            json={"role": "CASHIER"},
            headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
        )
        assert duplicate.status_code == 409

        cashier_auth = login(client, email="staff@example.test")
        cashier_denied = client.post(
            f"/api/v1/users/{target['id']}/roles",
            json={"role": "WAITER"},
            headers={"Authorization": f"Bearer {cashier_auth['access_token']}"},
        )
        assert cashier_denied.status_code == 403

        promoted = client.post(
            f"/api/v1/users/{target['id']}/roles",
            json={"role": "ADMIN"},
            headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
        )
        assert promoted.status_code == 200
        current_roles_from_database = client.post(
            f"/api/v1/users/{admin['id']}/roles",
            json={"role": "CASHIER"},
            headers={"Authorization": f"Bearer {target_auth_before_promotion['access_token']}"},
        )
        assert current_roles_from_database.status_code == 200
        assert current_roles_from_database.json()["roles"] == ["ADMIN", "CASHIER", "CUSTOMER"]

        escalation_denied = client.post(
            f"/api/v1/users/{target['id']}/roles",
            json={"role": "SUPER_ADMIN"},
            headers={"Authorization": f"Bearer {admin_auth['access_token']}"},
        )
        assert escalation_denied.status_code == 403

        super_auth = login(client, email="root@example.test")
        elevated = client.post(
            f"/api/v1/users/{target['id']}/roles",
            json={"role": "SUPER_ADMIN"},
            headers={"Authorization": f"Bearer {super_auth['access_token']}"},
        )
        assert elevated.status_code == 200, elevated.text
        assert elevated.json()["roles"] == ["ADMIN", "CASHIER", "CUSTOMER", "SUPER_ADMIN"]


async def test_expired_persisted_session_rejects_access_and_refresh(
    database: asyncpg.Connection,
) -> None:
    with api_client() as client:
        user = register(client, email="expiring@example.test")
        authenticated = login(client, email="expiring@example.test")
        await database.execute(
            """
            UPDATE public.auth_sessions
            SET expires_at = created_at + INTERVAL '1 microsecond'
            WHERE user_id = $1
            """,
            UUID(user["id"]),
        )

        access_rejected = client.post(
            f"/api/v1/users/{user['id']}/roles",
            json={"role": "WAITER"},
            headers={"Authorization": f"Bearer {authenticated['access_token']}"},
        )
        refresh_rejected = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": authenticated["refresh_token"]},
        )

        assert access_rejected.status_code == 401
        assert refresh_rejected.status_code == 401
