"""Real PostgreSQL + HTTP coverage for ETAPA 08 block 08.02."""

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

JWT_SECRET = "integration-test-jwt-secret-with-more-than-32-characters"
ACTOR_PASSWORD = "m02-integration-password"


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
    user_id = await database.fetchval(
        """
        INSERT INTO public.users (display_name, email, password_hash)
        VALUES ($1, $2, $3) RETURNING id
        """,
        role,
        email,
        Argon2PasswordHasher().hash(ACTOR_PASSWORD),
    )
    await database.execute(
        "INSERT INTO public.user_roles (user_id, role_code) VALUES ($1, $2)", user_id, role
    )
    return user_id, email


def bearer(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": ACTOR_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.mark.asyncio
async def test_catalog_crud_stock_audit_and_manual_availability(
    database: asyncpg.Connection,
) -> None:
    admin_id, email = await create_actor(database, "ADMIN")
    with api_client() as client:
        headers = bearer(client, email)
        assert client.get("/api/v1/catalog/categories").json() == []
        created = client.post(
            "/api/v1/catalog/categories", json={"name": " Arroces "}, headers=headers
        )
        assert created.status_code == 201, created.text
        category_id = created.json()["id"]
        assert created.json()["name"] == "Arroces"
        duplicate = client.post(
            "/api/v1/catalog/categories", json={"name": "Arroces"}, headers=headers
        )
        assert duplicate.status_code == 409

        renamed = client.patch(
            f"/api/v1/catalog/categories/{category_id}",
            json={"name": "Arroces y tallarines"},
            headers=headers,
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Arroces y tallarines"

        created_product = client.post(
            "/api/v1/catalog/products",
            json={"category_id": category_id, "name": "Chaufa", "price": "22.50"},
            headers=headers,
        )
        assert created_product.status_code == 201, created_product.text
        product_id = created_product.json()["id"]
        assert created_product.json()["stock_qty"] == 0
        assert created_product.json()["is_available"] is True
        assert Decimal(created_product.json()["price"]) == Decimal("22.50")

        changed = client.patch(
            f"/api/v1/catalog/products/{product_id}",
            json={"price": "24.25", "name": "Chaufa especial"},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text
        assert Decimal(changed.json()["price"]) == Decimal("24.25")
        products = client.get(f"/api/v1/catalog/categories/{category_id}/products")
        assert products.status_code == 200
        assert [product["name"] for product in products.json()] == ["Chaufa especial"]
        assert Decimal(products.json()[0]["price"]) == Decimal("24.25")
        assert products.json()[0]["available_for_sale"] is False
        assert "stock_qty" not in products.json()[0]

        for quantity in (8, 12, 12):
            response = client.put(
                f"/api/v1/catalog/products/{product_id}/stock",
                json={"quantity": quantity},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            assert response.json()["stock_qty"] == quantity

        public_ready = client.get(f"/api/v1/catalog/categories/{category_id}/products")
        assert public_ready.json()[0]["available_for_sale"] is True

        unavailable = client.patch(
            f"/api/v1/catalog/products/{product_id}/availability",
            json={"is_available": False},
            headers=headers,
        )
        assert unavailable.status_code == 200, unavailable.text
        assert unavailable.json()["is_available"] is False
        public_product = client.get(f"/api/v1/catalog/categories/{category_id}/products").json()[0]
        assert public_product["available_for_sale"] is False
        assert "stock_qty" not in public_product

    movements = await database.fetch(
        """
        SELECT kind, quantity_delta, actor_user_id, order_item_id, recorded_at
        FROM public.stock_movements WHERE product_id = $1
        """,
        UUID(product_id),
    )
    assert len(movements) == 2
    assert sorted(row["quantity_delta"] for row in movements) == [4, 8]
    assert all(
        row["kind"] == "MANUAL"
        and row["actor_user_id"] == admin_id
        and row["order_item_id"] is None
        and row["recorded_at"] is not None
        for row in movements
    )


@pytest.mark.asyncio
async def test_catalog_permissions_and_rejected_values(database: asyncpg.Connection) -> None:
    _, admin_email = await create_actor(database, "SUPER_ADMIN")
    _, customer_email = await create_actor(database, "CUSTOMER")
    with api_client() as client:
        assert (
            client.post("/api/v1/catalog/categories", json={"name": "Bebidas"}).status_code == 401
        )
        customer = bearer(client, customer_email)
        assert (
            client.post(
                "/api/v1/catalog/categories", json={"name": "Bebidas"}, headers=customer
            ).status_code
            == 403
        )
        guest = client.post("/api/v1/auth/guest")
        assert guest.status_code == 201
        assert (
            client.post(
                "/api/v1/catalog/categories",
                json={"name": "Bebidas"},
                headers={"Authorization": "Bearer " + guest.json()["access_token"]},
            ).status_code
            == 403
        )
        admin = bearer(client, admin_email)
        category = client.post(
            "/api/v1/catalog/categories", json={"name": "Bebidas"}, headers=admin
        )
        assert category.status_code == 201
        category_id = category.json()["id"]
        assert (
            client.post(
                "/api/v1/catalog/products",
                json={"category_id": str(uuid4()), "name": "Té", "price": "2.00"},
                headers=admin,
            ).status_code
            == 404
        )
        negative_price = client.post(
            "/api/v1/catalog/products",
            json={"category_id": category_id, "name": "Té", "price": "-1.00"},
            headers=admin,
        )
        assert negative_price.status_code == 422
        assert "-1.00" not in negative_price.text
        product = client.post(
            "/api/v1/catalog/products",
            json={"category_id": category_id, "name": "Té", "price": "2.00"},
            headers=admin,
        )
        assert product.status_code == 201
        product_id = product.json()["id"]
        assert (
            client.put(
                f"/api/v1/catalog/products/{product_id}/stock",
                json={"quantity": -1},
                headers=admin,
            ).status_code
            == 422
        )
        assert client.get(f"/api/v1/catalog/categories/{uuid4()}/products").status_code == 404
        assert (
            client.patch(
                f"/api/v1/catalog/products/{uuid4()}/availability",
                json={"is_available": False},
                headers=admin,
            ).status_code
            == 404
        )
    assert await database.fetchval("SELECT count(*) FROM public.stock_movements") == 0
