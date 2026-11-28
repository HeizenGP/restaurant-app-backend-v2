"""End-to-end customer to consolidated table collection flow."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import asyncpg
import pytest
from httpx2 import Response

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
    other_table_id = await table(database)
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
        shift = client.post("/api/v1/cash-shifts", headers=staff, json={"initial_amount": 0})
        assert shift.status_code == 201, shift.text

        def submit_order(key: str, selected_table: UUID) -> Response:
            return client.post(
                "/api/v1/orders",
                json={
                    "modality": "LOCAL",
                    "table_id": str(selected_table),
                    "items": [{"product_id": str(product_id), "quantity": 1}],
                },
                headers={**customer, "Idempotency-Key": key},
            )

        def create_order(key: str, selected_table: UUID = table_id) -> dict[str, object]:
            response = submit_order(key, selected_table)
            assert response.status_code == 201, response.text
            return response.json()

        def my_table_ids() -> list[str]:
            response = client.get("/api/v1/tables", headers=customer)
            assert response.status_code == 200, response.text
            assert response.headers["Cache-Control"] == "private, no-store"
            entries = response.json()
            assert all(isinstance(entry["is_mine"], bool) for entry in entries)
            return [entry["id"] for entry in entries if entry["is_mine"]]

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
            tickets = client.get("/api/v1/kitchen/tickets", headers=staff)
            assert tickets.status_code == 200, tickets.text
            ticket = next(entry for entry in tickets.json() if entry["order_id"] == order_id)
            path = f"/api/v1/kitchen/tickets/{ticket['id']}"
            started = client.post(f"{path}/start", headers=staff)
            assert started.status_code == 200, started.text
            ready = client.post(
                f"{path}/ready", headers=staff, json={"all_items_prepared": True}
            )
            assert ready.status_code == 200, ready.text

        first = create_order("customer-first")
        assert first["status"] == "REQUESTED"
        assert first["table_id"] == str(table_id)
        assert first["table_account_id"]
        assert len(first["lines"]) == 1
        assert my_table_ids() == [str(table_id)]
        other = submit_order("customer-other-before-approval", other_table_id)
        assert other.status_code == 409, other.text
        assert "Ya tienes una mesa asignada." in other.json()["detail"]

        # Pending customer requests are visible to authorized staff and occupy the table.
        listed = client.get("/api/v1/orders", headers=staff)
        assert listed.status_code == 200, listed.text
        assert any(order["id"] == first["id"] for order in listed.json())
        invalid_session = client.get(
            "/api/v1/tables", headers={"Authorization": "Bearer invalid-session"}
        )
        assert invalid_session.status_code == 401, invalid_session.text
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
        assert my_table_ids() == [str(table_id)]
        other = submit_order("customer-other-after-partial", other_table_id)
        assert other.status_code == 409, other.text
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
        assert my_table_ids() == []
        next_order = create_order("customer-other-after-full", other_table_id)
        assert next_order["table_id"] == str(other_table_id)
        assert my_table_ids() == [str(other_table_id)]

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


@pytest.mark.asyncio
async def test_guest_concurrent_orders_can_only_claim_one_table(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, price="10.00", stock=10)
    table_ids = [await table(database), await table(database)]
    with api_client() as client:
        guest = client.post("/api/v1/auth/guest")
        assert guest.status_code == 201, guest.text
        headers = {"Authorization": "Bearer " + guest.json()["access_token"]}
        barrier = Barrier(2, timeout=10)

        def submit(table_id: UUID) -> Response:
            barrier.wait()
            return client.post(
                "/api/v1/orders",
                json={
                    "modality": "LOCAL",
                    "table_id": str(table_id),
                    "items": [{"product_id": str(product_id), "quantity": 1}],
                },
                headers={**headers, "Idempotency-Key": f"guest-request-{table_id}"},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(submit, table_ids))

        assert sorted(response.status_code for response in responses) == [201, 409]
        order = next(response.json() for response in responses if response.status_code == 201)
        listing = client.get("/api/v1/tables", headers=headers)
        assert listing.status_code == 200, listing.text
        assigned = [entry["id"] for entry in listing.json() if entry["is_mine"]]
        assert assigned == [order["table_id"]]
