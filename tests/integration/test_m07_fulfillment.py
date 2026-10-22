"""08.09 fulfillment and closure against an explicitly authorized PostgreSQL test DB."""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from restaurant_app.modules.m07_fulfillment.adapters.outbound.repositories import (
    SqlAlchemyFulfillmentRepository,
)
from tests.integration.test_m04_confirm_order import (
    actor,
    api_client,
    app_order_payload,
    async_clients,
    bearer,
    product,
    table,
    wait_for_lock_waiters,
)

pytest_plugins = ("tests.integration.test_initial_migration",)
pytestmark = pytest.mark.integration


def waiter_order(
    client: TestClient, waiter: dict[str, str], table_id: UUID, product_id: UUID
) -> UUID:
    response = client.post(
        "/api/v1/orders/waiter",
        json={"table_id": str(table_id), "items": [{"product_id": str(product_id), "quantity": 1}]},
        headers={**waiter, "Idempotency-Key": f"direct-{uuid4()}"},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


def ready_ticket(
    client: TestClient,
    kitchen: dict[str, str],
    order_id: UUID,
    *,
    tracking_actor: dict[str, str] | None = None,
) -> None:
    tickets = client.get("/api/v1/kitchen/tickets", headers=kitchen)
    assert tickets.status_code == 200, tickets.text
    ticket_id = next(
        UUID(item["id"]) for item in tickets.json() if item["order_id"] == str(order_id)
    )
    path = f"/api/v1/kitchen/tickets/{ticket_id}"
    started = client.post(f"{path}/start", headers=kitchen)
    assert started.status_code == 200, started.text
    if tracking_actor is not None:
        tracking = client.get(f"/api/v1/orders/{order_id}/tracking", headers=tracking_actor)
        assert tracking.status_code == 200, tracking.text
        assert tracking.json()["stage"] == "PREPARING"
    ready = client.post(f"{path}/ready", json={"all_items_prepared": True}, headers=kitchen)
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "READY"


@pytest.mark.asyncio
async def test_local_service_closure_tracking_and_audit(database: asyncpg.Connection) -> None:
    product_id = await product(database, price="20.00")
    table_id = await table(database)
    waiter_id, waiter_email = await actor(database, "WAITER")
    admin_id, admin_email = await actor(database, "ADMIN")
    _, super_email = await actor(database, "SUPER_ADMIN")
    _, kitchen_email = await actor(database, "KITCHEN")
    _, cashier_email = await actor(database, "CASHIER")
    _, customer_email = await actor(database, "CUSTOMER")
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        admin = bearer(client, admin_email)
        super_admin = bearer(client, super_email)
        kitchen = bearer(client, kitchen_email)
        cashier = bearer(client, cashier_email)
        customer = bearer(client, customer_email)
        order_id = waiter_order(client, waiter, table_id, product_id)
        base = f"/api/v1/orders/{order_id}"
        initial = client.get(f"{base}/tracking", headers=waiter)
        assert initial.status_code == 200, initial.text
        assert initial.json()["stage"] == "RECEIVED"
        assert Decimal(initial.json()["balance"]) == Decimal("20.00")
        assert client.get(f"{base}/tracking", headers=customer).status_code == 404
        assert client.get(f"{base}/tracking").status_code == 401
        assert client.post(f"{base}/serve", headers=waiter).status_code == 422
        assert (
            client.post(
                f"{base}/serve", headers={**admin, "Idempotency-Key": "admin-cannot-serve"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"{base}/serve", headers={**waiter, "Idempotency-Key": "before-ready"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"{base}/close", headers={**admin, "Idempotency-Key": "before-ready"}
            ).status_code
            == 409
        )
        ready_ticket(client, kitchen, order_id, tracking_actor=waiter)
        assert client.get(f"{base}/tracking", headers=waiter).json()["stage"] == "READY"
        assert (
            client.post(
                f"{base}/close", headers={**admin, "Idempotency-Key": "before-service"}
            ).status_code
            == 409
        )
        served = client.post(f"{base}/serve", headers={**waiter, "Idempotency-Key": "service"})
        assert served.status_code == 200, served.text
        assert served.json()["kind"] == "SERVED"
        assert served.json()["recorded_by_user_id"] == str(waiter_id)
        replay = client.post(f"{base}/serve", headers={**waiter, "Idempotency-Key": "service"})
        assert replay.status_code == 200 and replay.json() == served.json()
        assert (
            client.post(
                f"{base}/serve", headers={**waiter, "Idempotency-Key": "another-service-key"}
            ).json()
            == served.json()
        )
        assert (
            client.post(
                f"{base}/serve", headers={**super_admin, "Idempotency-Key": "super-service"}
            ).json()
            == served.json()
        )
        assert (
            client.post(
                f"/api/v1/orders/{uuid4()}/serve", headers={**waiter, "Idempotency-Key": "service"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"{base}/pickup", headers={**admin, "Idempotency-Key": "wrong-kind"}
            ).status_code
            == 409
        )
        outstanding = client.post(
            f"{base}/close", headers={**admin, "Idempotency-Key": "before-payment"}
        )
        assert outstanding.status_code == 409 and "S/ 20.00" in outstanding.text
        assert (
            client.post(
                f"{base}/close", headers={**waiter, "Idempotency-Key": "waiter-close"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"{base}/payments",
                json={"amount": "20.00", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "full-payment"},
            ).status_code
            == 200
        )
        closed = client.post(f"{base}/close", headers={**admin, "Idempotency-Key": "close"})
        assert closed.status_code == 200, closed.text
        assert closed.json()["stage"] == "CLOSED"
        assert closed.json()["payment_status"] == "PAID"
        assert Decimal(closed.json()["balance"]) == Decimal("0.00")
        assert closed.json()["fulfilled_at"] and closed.json()["closed_at"]
        assert (
            client.post(f"{base}/close", headers={**admin, "Idempotency-Key": "close"}).json()
            == closed.json()
        )
        assert (
            client.post(
                f"{base}/close", headers={**super_admin, "Idempotency-Key": "super-close"}
            ).json()
            == closed.json()
        )
        assert client.get(f"{base}/tracking", headers=super_admin).status_code == 200
        assert client.get(base, headers=waiter).json()["status"] == "CLOSED"
    fulfillment = await database.fetchrow(
        "SELECT kind,recorded_by_user_id,recorded_at FROM public.fulfillments WHERE order_id=$1",
        order_id,
    )
    order = await database.fetchrow(
        "SELECT status,closed_by_user_id,closed_at,version FROM public.orders WHERE id=$1",
        order_id,
    )
    assert fulfillment is not None and order is not None
    assert (fulfillment["kind"], fulfillment["recorded_by_user_id"]) == ("SERVED", waiter_id)
    assert fulfillment["recorded_at"] is not None
    assert (order["status"], order["closed_by_user_id"], order["version"]) == (
        "CLOSED",
        admin_id,
        2,
    )
    assert order["closed_at"] is not None
    assert await database.fetchval("SELECT count(*) FROM public.fulfillments") == 1
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests "
            "WHERE operation='RECORD_FULFILLMENT' AND result_order_id=$1",
            order_id,
        )
        == 1
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests "
            "WHERE operation='CLOSE_ORDER' AND result_order_id=$1",
            order_id,
        )
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("modality", "endpoint", "kind"),
    [("PICKUP", "pickup", "PICKED_UP"), ("DELIVERY", "deliver", "DELIVERED")],
)
async def test_remote_handover_final_payment_close_and_owner_tracking(
    database: asyncpg.Connection, modality: str, endpoint: str, kind: str
) -> None:
    product_id = await product(database, price="10.01")
    customer_id, customer_email = await actor(database, "CUSTOMER")
    _, unrelated_email = await actor(database, "CUSTOMER")
    admin_id, admin_email = await actor(database, "ADMIN")
    _, waiter_email = await actor(database, "WAITER")
    _, kitchen_email = await actor(database, "KITCHEN")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        unrelated = bearer(client, unrelated_email)
        admin = bearer(client, admin_email)
        waiter = bearer(client, waiter_email)
        kitchen = bearer(client, kitchen_email)
        cashier = bearer(client, cashier_email)
        created = client.post(
            "/api/v1/orders",
            json=app_order_payload(modality, product_id),
            headers={**customer, "Idempotency-Key": "remote-order"},
        )
        assert created.status_code == 201, created.text
        order_id = UUID(created.json()["id"])
        base = f"/api/v1/orders/{order_id}"
        assert client.get(f"{base}/tracking", headers=unrelated).status_code == 404
        assert client.get(f"{base}/tracking", headers=customer).json()["stage"] == "REQUESTED"
        assert (
            client.post(
                f"{base}/{endpoint}", headers={**admin, "Idempotency-Key": "early"}
            ).status_code
            == 409
        )
        assert (
            client.post(f"{base}/decision", json={"approved": True}, headers=admin).status_code
            == 200
        )
        advance = client.post(
            f"{base}/advance/verify", headers={**admin, "Idempotency-Key": "advance"}
        )
        assert advance.status_code == 200 and Decimal(advance.json()["verified_amount"]) == Decimal(
            "5.01"
        )
        assert (
            client.post(
                f"{base}/confirm", headers={**admin, "Idempotency-Key": "confirm"}
            ).status_code
            == 200
        )
        ready_ticket(client, kitchen, order_id, tracking_actor=customer)
        assert client.get(f"{base}/tracking", headers=customer).json()["stage"] == "READY"
        assert (
            client.post(
                f"{base}/{endpoint}", headers={**waiter, "Idempotency-Key": "waiter"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"{base}/payments",
                json={"amount": "5.00", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "before-handover"},
            ).status_code
            == 409
        )
        handover = client.post(
            f"{base}/{endpoint}", headers={**admin, "Idempotency-Key": "handover"}
        )
        assert handover.status_code == 200, handover.text
        assert handover.json()["kind"] == kind
        assert handover.json()["recorded_by_user_id"] == str(admin_id)
        tracking = client.get(f"{base}/tracking", headers=customer)
        assert tracking.status_code == 200 and tracking.json()["stage"] == kind
        assert Decimal(tracking.json()["balance"]) == Decimal("5.00")
        assert (
            client.post(
                f"{base}/close", headers={**admin, "Idempotency-Key": "before-final"}
            ).status_code
            == 409
        )
        final = client.post(
            f"{base}/payments",
            json={"amount": "5.00", "method_code": "EFECTIVO"},
            headers={**cashier, "Idempotency-Key": "final"},
        )
        assert final.status_code == 200, final.text
        closed = client.post(f"{base}/close", headers={**admin, "Idempotency-Key": "close"})
        assert closed.status_code == 200, closed.text
        assert closed.json()["stage"] == "CLOSED"
        assert client.get(f"{base}/tracking", headers=customer).json()["stage"] == "CLOSED"
        assert client.get(f"{base}/tracking", headers=unrelated).status_code == 404
    saved = await database.fetchrow(
        "SELECT kind,recorded_by_user_id FROM public.fulfillments WHERE order_id=$1", order_id
    )
    assert saved is not None and (saved["kind"], saved["recorded_by_user_id"]) == (kind, admin_id)
    assert (
        await database.fetchval("SELECT customer_user_id FROM public.orders WHERE id=$1", order_id)
        == customer_id
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.fulfillments WHERE order_id=$1", order_id
        )
        == 1
    )


@pytest.mark.asyncio
async def test_concurrent_service_same_key_records_one_row(database: asyncpg.Connection) -> None:
    product_id = await product(database)
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    _, kitchen_email = await actor(database, "KITCHEN")
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        kitchen = bearer(client, kitchen_email)
        order_id = waiter_order(client, waiter, table_id, product_id)
        ready_ticket(client, kitchen, order_id)
    path = f"/api/v1/orders/{order_id}/serve"
    headers = {**waiter, "Idempotency-Key": f"race-{uuid4()}"}
    async with async_clients() as (first, second):
        async with database.transaction():
            await database.fetchrow("SELECT id FROM public.orders WHERE id=$1 FOR UPDATE", order_id)
            tasks = [
                asyncio.create_task(client.post(path, headers=headers))
                for client in (first, second)
            ]
            await wait_for_lock_waiters(database, tasks)
        responses = await asyncio.gather(*tasks)
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert responses[0].json() == responses[1].json()
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.fulfillments WHERE order_id=$1", order_id
        )
        == 1
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests WHERE operation='RECORD_FULFILLMENT' "
            "AND result_order_id=$1",
            order_id,
        )
        == 1
    )


@pytest.mark.asyncio
async def test_concurrent_close_different_keys_preserves_single_audit(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, price="8.00")
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    admin_id, admin_email = await actor(database, "ADMIN")
    _, kitchen_email = await actor(database, "KITCHEN")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        admin = bearer(client, admin_email)
        kitchen = bearer(client, kitchen_email)
        cashier = bearer(client, cashier_email)
        order_id = waiter_order(client, waiter, table_id, product_id)
        ready_ticket(client, kitchen, order_id)
        base = f"/api/v1/orders/{order_id}"
        assert (
            client.post(
                f"{base}/serve", headers={**waiter, "Idempotency-Key": "served"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"{base}/payments",
                json={"amount": "8.00", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "paid"},
            ).status_code
            == 200
        )
    path = f"/api/v1/orders/{order_id}/close"
    async with async_clients() as (first, second):
        async with database.transaction():
            await database.fetchrow("SELECT id FROM public.orders WHERE id=$1 FOR UPDATE", order_id)
            tasks = [
                asyncio.create_task(
                    client.post(path, headers={**admin, "Idempotency-Key": f"close-{index}"})
                )
                for index, client in enumerate((first, second))
            ]
            await wait_for_lock_waiters(database, tasks)
        responses = await asyncio.gather(*tasks)
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert responses[0].json() == responses[1].json()
    order = await database.fetchrow(
        "SELECT status,closed_by_user_id,closed_at,version FROM public.orders WHERE id=$1", order_id
    )
    assert order is not None
    assert (order["status"], order["closed_by_user_id"], order["version"]) == (
        "CLOSED",
        admin_id,
        2,
    )
    assert order["closed_at"] is not None
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests WHERE operation='CLOSE_ORDER' "
            "AND result_order_id=$1",
            order_id,
        )
        == 1
    )


@pytest.mark.asyncio
async def test_close_rolls_back_if_idempotency_persistence_fails(
    database: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    product_id = await product(database, price="8.00")
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    _, admin_email = await actor(database, "ADMIN")
    _, kitchen_email = await actor(database, "KITCHEN")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        admin = bearer(client, admin_email)
        kitchen = bearer(client, kitchen_email)
        cashier = bearer(client, cashier_email)
        order_id = waiter_order(client, waiter, table_id, product_id)
        ready_ticket(client, kitchen, order_id)
        base = f"/api/v1/orders/{order_id}"
        assert (
            client.post(
                f"{base}/serve", headers={**waiter, "Idempotency-Key": "served"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"{base}/payments",
                json={"amount": "8.00", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "paid"},
            ).status_code
            == 200
        )

        original = SqlAlchemyFulfillmentRepository.record_close

        async def fail_record_close(*args: object, **kwargs: object) -> None:
            raise RuntimeError("injected idempotency failure")

        monkeypatch.setattr(SqlAlchemyFulfillmentRepository, "record_close", fail_record_close)
        with pytest.raises(RuntimeError, match="injected idempotency failure"):
            client.post(f"{base}/close", headers={**admin, "Idempotency-Key": "close"})
        saved = await database.fetchrow(
            "SELECT status,closed_by_user_id,closed_at FROM public.orders WHERE id=$1", order_id
        )
        assert saved is not None
        assert (saved["status"], saved["closed_by_user_id"], saved["closed_at"]) == (
            "CONFIRMED",
            None,
            None,
        )
        assert (
            await database.fetchval(
                "SELECT count(*) FROM public.idempotency_requests WHERE operation='CLOSE_ORDER' "
                "AND result_order_id=$1",
                order_id,
            )
            == 0
        )
        monkeypatch.setattr(SqlAlchemyFulfillmentRepository, "record_close", original)
        successful = client.post(f"{base}/close", headers={**admin, "Idempotency-Key": "close"})
        assert successful.status_code == 200, successful.text
