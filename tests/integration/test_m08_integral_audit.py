"""08.10 cross-module Super Admin authorization on isolated PostgreSQL."""

from uuid import UUID, uuid4

import asyncpg
import pytest

from tests.integration.test_m04_confirm_order import (
    actor,
    api_client,
    app_order_payload,
    bearer,
)

pytest_plugins = ("tests.integration.test_initial_migration",)
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_super_admin_operates_all_seven_modules(database: asyncpg.Connection) -> None:
    super_id, super_email = await actor(database, "SUPER_ADMIN")
    target_id, _ = await actor(database, "CUSTOMER")
    _, customer_email = await actor(database, "CUSTOMER")

    with api_client() as client:
        root = bearer(client, super_email)
        customer = bearer(client, customer_email)

        # M01: only a Super Admin may grant staff permissions across roles.
        granted = client.post(
            f"/api/v1/users/{target_id}/roles",
            json={"role": "WAITER"},
            headers=root,
        )
        assert granted.status_code == 200, granted.text
        assert "WAITER" in granted.json()["roles"]

        # M02/M03: the same principal can manage catalog and tables.
        category = client.post(
            "/api/v1/catalog/categories",
            json={"name": f"Auditoria-{uuid4()}"},
            headers=root,
        )
        assert category.status_code == 201, category.text
        product = client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": category.json()["id"],
                "name": "Chaufa auditoria",
                "price": "10.00",
            },
            headers=root,
        )
        assert product.status_code == 201, product.text
        product_id = UUID(product.json()["id"])
        stock = client.put(
            f"/api/v1/catalog/products/{product_id}/stock",
            json={"quantity": 4},
            headers=root,
        )
        assert stock.status_code == 200 and stock.json()["stock_qty"] == 4
        table = client.post(
            "/api/v1/tables", json={"code": f"AUD-{uuid4().hex[:12]}"}, headers=root
        )
        assert table.status_code == 201, table.text
        table_id = UUID(table.json()["id"])

        # M04/M05: Super Admin bypasses WAITER and KITCHEN guards.
        local = client.post(
            "/api/v1/orders/waiter",
            json={
                "table_id": str(table_id),
                "items": [{"product_id": str(product_id), "quantity": 1}],
            },
            headers={**root, "Idempotency-Key": "super-local"},
        )
        assert local.status_code == 201, local.text
        order_id = UUID(local.json()["id"])
        tickets = client.get("/api/v1/kitchen/tickets", headers=root)
        assert tickets.status_code == 200, tickets.text
        ticket_id = next(
            UUID(item["id"]) for item in tickets.json() if item["order_id"] == str(order_id)
        )
        ticket_path = f"/api/v1/kitchen/tickets/{ticket_id}"
        assert client.post(f"{ticket_path}/start", headers=root).status_code == 200
        assert (
            client.post(
                f"{ticket_path}/ready", json={"all_items_prepared": True}, headers=root
            ).status_code
            == 200
        )

        # M07/M06: service, cashier collection and closure remain distinct
        # permissions for ordinary roles, but Super Admin can perform each.
        base = f"/api/v1/orders/{order_id}"
        served = client.post(f"{base}/serve", headers={**root, "Idempotency-Key": "serve"})
        assert served.status_code == 200, served.text
        paid = client.post(
            f"{base}/payments",
            json={"amount": "10.00", "method_code": "EFECTIVO"},
            headers={**root, "Idempotency-Key": "pay"},
        )
        assert paid.status_code == 200, paid.text
        closed = client.post(f"{base}/close", headers={**root, "Idempotency-Key": "close"})
        assert closed.status_code == 200, closed.text
        assert closed.json()["stage"] == "CLOSED"
        released = client.patch(
            f"/api/v1/tables/{table_id}/occupancy",
            json={"is_occupied": False},
            headers=root,
        )
        assert released.status_code == 200 and released.json()["is_occupied"] is False

        # M04/M06 administrative path: APP pickup approval, advance and confirmation.
        remote = client.post(
            "/api/v1/orders",
            json=app_order_payload("PICKUP", product_id),
            headers={**customer, "Idempotency-Key": "remote"},
        )
        assert remote.status_code == 201, remote.text
        remote_id = UUID(remote.json()["id"])
        remote_path = f"/api/v1/orders/{remote_id}"
        decision = client.post(f"{remote_path}/decision", json={"approved": True}, headers=root)
        assert decision.status_code == 200, decision.text
        advance = client.post(
            f"{remote_path}/advance/verify",
            headers={**root, "Idempotency-Key": "advance"},
        )
        assert advance.status_code == 200, advance.text
        assert advance.json()["verified_amount"] == "5.00"
        confirmed = client.post(
            f"{remote_path}/confirm", headers={**root, "Idempotency-Key": "confirm"}
        )
        assert confirmed.status_code == 200, confirmed.text

    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.fulfillments WHERE order_id=$1 AND recorded_by_user_id=$2",
            order_id,
            super_id,
        )
        == 1
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.payments WHERE order_id=$1 AND recorded_by_user_id=$2",
            order_id,
            super_id,
        )
        == 1
    )
    assert (
        await database.fetchval("SELECT closed_by_user_id FROM public.orders WHERE id=$1", order_id)
        == super_id
    )
