"""End-to-end customer to consolidated table collection flow."""

from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg
import pytest

from tests.integration.test_m04_confirm_order import (
    actor,
    api_client,
    bearer,
    product,
    table,
)

pytest_plugins = ("tests.integration.test_initial_migration",)
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_registered_customer_two_orders_one_table_account_full_collection(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, price="10.00", stock=10)
    table_id = await table(database)
    _, staff_email = await actor(database, "SUPER_ADMIN")
    customer_email = f"table-client-{uuid4()}@example.test"

    with api_client() as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "Cliente Mesa 1",
                "email": customer_email,
                "password": "Customer-password1",
            },
        )
        assert registered.status_code == 201, registered.text
        login = client.post(
            "/api/v1/auth/login",
            json={"email": customer_email, "password": "Customer-password1"},
        )
        assert login.status_code == 200, login.text
        customer = {"Authorization": "Bearer " + login.json()["access_token"]}
        staff = bearer(client, staff_email)

        def create_order(key: str) -> dict[str, object]:
            response = client.post(
                "/api/v1/orders",
                json={
                    "modality": "LOCAL",
                    "table_id": str(table_id),
                    "items": [{"product_id": str(product_id), "quantity": 1}],
                },
                headers={**customer, "Idempotency-Key": key},
            )
            assert response.status_code == 201, response.text
            return response.json()

        def approve_and_confirm(order_id: str, suffix: str) -> None:
            decision = client.post(
                f"/api/v1/orders/{order_id}/decision",
                json={"approved": True, "table_verified": True},
                headers=staff,
            )
            assert decision.status_code == 200, decision.text
            confirmed = client.post(
                f"/api/v1/orders/{order_id}/confirm",
                headers={**staff, "Idempotency-Key": f"confirm-{suffix}"},
            )
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["status"] == "CONFIRMED"

        first = create_order("customer-first")
        assert first["status"] == "REQUESTED"
        assert first["table_id"] == str(table_id)
        assert first["table_account_id"]
        assert len(first["lines"]) == 1

        # Pending customer requests are visible to authorized staff and occupy the table.
        listed = client.get("/api/v1/orders", headers=staff)
        assert listed.status_code == 200, listed.text
        assert any(order["id"] == first["id"] for order in listed.json())
        tables = client.get("/api/v1/tables")
        assert tables.status_code == 200, tables.text
        selected = next(item for item in tables.json() if item["id"] == str(table_id))
        assert selected["is_occupied"] is True

        approve_and_confirm(str(first["id"]), "first")
        second = create_order("customer-second")
        assert second["table_account_id"] == first["table_account_id"]
        approve_and_confirm(str(second["id"]), "second")

        account_path = f"/api/v1/tables/{table_id}/account"
        account = client.get(account_path, headers=staff)
        assert account.status_code == 200, account.text
        body = account.json()
        assert body["status"] == "OPEN"
        assert len(body["orders"]) == 2
        assert Decimal(body["total_amount"]) == Decimal("20.00")
        assert Decimal(body["advance_amount"]) == Decimal("0.00")
        assert Decimal(body["balance"]) == Decimal("20.00")
        assert all(order["lines"] for order in body["orders"])

        collection_path = account_path + "/payments"
        partial = client.post(
            collection_path,
            json={"amount": "5.00", "method_code": "EFECTIVO"},
            headers={**staff, "Idempotency-Key": "table-partial"},
        )
        assert partial.status_code == 200, partial.text
        assert partial.json()["status"] == "OPEN"
        assert Decimal(partial.json()["balance"]) == Decimal("15.00")
        assert (
            client.post(
                collection_path,
                json={"amount": "15.01", "method_code": "EFECTIVO"},
                headers={**staff, "Idempotency-Key": "table-overpay"},
            ).status_code
            == 409
        )

        final = client.post(
            collection_path,
            json={
                "amount": "15.00",
                "method_code": "YAPE",
                "reference_code": "999111222",
            },
            headers={**staff, "Idempotency-Key": "table-final"},
        )
        assert final.status_code == 200, final.text
        assert final.json()["status"] == "PAID"
        assert Decimal(final.json()["balance"]) == Decimal("0.00")
        replay = client.post(
            collection_path,
            json={
                "amount": "15.00",
                "method_code": "YAPE",
                "reference_code": "999111222",
            },
            headers={**staff, "Idempotency-Key": "table-final"},
        )
        assert replay.status_code == 200 and replay.json() == final.json()

        released = client.get("/api/v1/tables")
        selected = next(item for item in released.json() if item["id"] == str(table_id))
        assert selected["is_occupied"] is False
        assert all(order["status"] == "CLOSED" for order in final.json()["orders"])

    account_id = UUID(str(first["table_account_id"]))
    assert (
        await database.fetchval("SELECT status FROM public.table_accounts WHERE id=$1", account_id)
        == "PAID"
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.orders WHERE table_account_id=$1", account_id
        )
        == 2
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.payments WHERE table_account_id=$1", account_id
        )
        == 2
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.orders WHERE table_account_id=$1 AND status='CLOSED'",
            account_id,
        )
        == 2
    )
