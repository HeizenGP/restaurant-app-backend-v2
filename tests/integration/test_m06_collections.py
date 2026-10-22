"""08.08 cashier collections on an explicitly authorized disposable PostgreSQL database."""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg
import httpx2 as httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from restaurant_app.modules.m06_payments.public import SqlAlchemyPaymentBalanceReader
from tests.integration.test_initial_migration import _test_database_target
from tests.integration.test_m04_confirm_order import (
    ACTOR_PASSWORD,
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


@pytest.mark.asyncio
async def test_local_cashier_partial_final_replay_permissions_and_balance(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, price="10.00", stock=3)
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    cashier_id, cashier_email = await actor(database, "CASHIER")
    _, admin_email = await actor(database, "ADMIN")
    _, super_email = await actor(database, "SUPER_ADMIN")
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        cashier = bearer(client, cashier_email)
        admin = bearer(client, admin_email)
        super_admin = bearer(client, super_email)
        created = client.post(
            "/api/v1/orders/waiter",
            json={
                "table_id": str(table_id),
                "items": [{"product_id": str(product_id), "quantity": 1}],
            },
            headers={**waiter, "Idempotency-Key": "cashier-local-order"},
        )
        assert created.status_code == 201, created.text
        order_id = UUID(created.json()["id"])
        path = f"/api/v1/orders/{order_id}/payments"
        empty = client.get(path, headers=cashier)
        assert empty.status_code == 200, empty.text
        assert (empty.json()["payment_status"], Decimal(empty.json()["balance"])) == (
            "UNPAID",
            Decimal("10.00"),
        )
        assert client.get(path, headers=super_admin).status_code == 200
        assert client.get(path, headers=admin).status_code == 404
        assert client.get(path, headers=waiter).status_code == 404
        assert client.get(path).status_code == 401
        assert (
            client.post(
                path, json={"amount": "1.00", "method_code": "EFECTIVO"}, headers=admin
            ).status_code
            == 403
        )
        first = client.post(
            path,
            json={"amount": "3.00", "method_code": "EFECTIVO"},
            headers={**cashier, "Idempotency-Key": "cashier-partial"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["payment_status"] == "PARTIAL"
        assert Decimal(first.json()["balance"]) == Decimal("7.00")
        replay = client.post(
            path,
            json={"amount": "3.00", "method_code": "EFECTIVO"},
            headers={**cashier, "Idempotency-Key": "cashier-partial"},
        )
        assert replay.status_code == 200 and replay.json() == first.json()
        assert (
            client.post(
                path,
                json={"amount": "2.00", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "cashier-partial"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                path,
                json={"amount": "7.01", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "overpay"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                path,
                json={"amount": "0.001", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "fractional-cent"},
            ).status_code
            == 422
        )
        final = client.post(
            path,
            json={"amount": "7.00", "method_code": "SIMULADO"},
            headers={**cashier, "Idempotency-Key": "cashier-final"},
        )
        assert final.status_code == 200, final.text
        assert final.json()["payment_status"] == "PAID"
        assert Decimal(final.json()["balance"]) == Decimal("0.00")
        assert (
            client.post(
                path,
                json={"amount": "0.01", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "after-paid"},
            ).status_code
            == 409
        )
    rows = await database.fetch(
        "SELECT kind,amount,method_code,recorded_by_user_id,recorded_at,operation_request_id "
        "FROM public.payments WHERE order_id=$1 ORDER BY recorded_at,id",
        order_id,
    )
    assert [(row["kind"], row["amount"]) for row in rows] == [
        ("COLLECTION", Decimal("3.00")),
        ("COLLECTION", Decimal("7.00")),
    ]
    assert all(row["recorded_by_user_id"] == cashier_id and row["recorded_at"] for row in rows)
    assert all(row["operation_request_id"] for row in rows)
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.idempotency_requests "
            "WHERE operation='RECORD_COLLECTION' AND result_order_id=$1",
            order_id,
        )
        == 2
    )
    dsn, _ = _test_database_target()
    engine = create_async_engine(dsn.replace("postgresql://", "postgresql+asyncpg://", 1))
    try:
        async with AsyncSession(engine) as session:
            balance = await SqlAlchemyPaymentBalanceReader(session).get_balance(
                order_id, total_amount=Decimal("10.00")
            )
            assert balance == Decimal("0.00")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("modality", "handover_kind"), [("PICKUP", "PICKED_UP"), ("DELIVERY", "DELIVERED")]
)
async def test_remote_exact_final_balance_only_after_recorded_handover(
    database: asyncpg.Connection, modality: str, handover_kind: str
) -> None:
    product_id = await product(database, price="10.01", stock=2)
    _, customer_email = await actor(database, "CUSTOMER")
    admin_id, admin_email = await actor(database, "ADMIN")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        customer = bearer(client, customer_email)
        admin = bearer(client, admin_email)
        cashier = bearer(client, cashier_email)
        created = client.post(
            "/api/v1/orders",
            json=app_order_payload(modality, product_id),
            headers={**customer, "Idempotency-Key": "remote-order"},
        )
        assert created.status_code == 201, created.text
        order_id = UUID(created.json()["id"])
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/decision",
                json={"approved": True},
                headers=admin,
            ).status_code
            == 200
        )
        advance = client.post(
            f"/api/v1/orders/{order_id}/advance/verify",
            headers={**admin, "Idempotency-Key": "remote-advance"},
        )
        assert advance.status_code == 200, advance.text
        assert Decimal(advance.json()["verified_amount"]) == Decimal("5.01")
        assert (
            client.post(
                f"/api/v1/orders/{order_id}/confirm",
                headers={**admin, "Idempotency-Key": "remote-confirm"},
            ).status_code
            == 200
        )
        path = f"/api/v1/orders/{order_id}/payments"
        for headers in (customer, cashier):
            summary = client.get(path, headers=headers)
            assert summary.status_code == 200, summary.text
            assert summary.json()["payment_status"] == "PARTIAL"
            assert Decimal(summary.json()["paid_amount"]) == Decimal("5.01")
            assert Decimal(summary.json()["balance"]) == Decimal("5.00")
        assert (
            client.post(
                path,
                json={"amount": "5.00", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "before-delivery"},
            ).status_code
            == 409
        )
        # 08.09 creates this row in production; 08.08 only consumes the approved public contract.
        await database.execute(
            "INSERT INTO public.fulfillments(order_id,kind,recorded_by_user_id) VALUES($1,$2,$3)",
            order_id,
            handover_kind,
            admin_id,
        )
        assert (
            client.post(
                path,
                json={"amount": "2.00", "method_code": "EFECTIVO"},
                headers={**cashier, "Idempotency-Key": "remote-partial"},
            ).status_code
            == 409
        )
        final = client.post(
            path,
            json={"amount": "5.00", "method_code": "EFECTIVO"},
            headers={**cashier, "Idempotency-Key": "remote-final"},
        )
        assert final.status_code == 200, final.text
        assert Decimal(final.json()["balance"]) == Decimal("0.00")
        assert final.json()["payment_status"] == "PAID"
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.payments WHERE order_id=$1 AND kind='ADVANCE'", order_id
        )
        == 1
    )
    assert (
        await database.fetchval(
            "SELECT count(*) FROM public.payments WHERE order_id=$1 AND kind='COLLECTION'", order_id
        )
        == 1
    )


@pytest.mark.asyncio
async def test_two_cashiers_competing_for_balance_do_not_overpay(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, price="10.00", stock=2)
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    cashier_emails = [(await actor(database, "CASHIER"))[1] for _ in range(2)]
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        order_response = client.post(
            "/api/v1/orders/waiter",
            json={
                "table_id": str(table_id),
                "items": [{"product_id": str(product_id), "quantity": 1}],
            },
            headers={**waiter, "Idempotency-Key": "racing-cashier-order"},
        )
        assert order_response.status_code == 201, order_response.text
        order_id = UUID(order_response.json()["id"])
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with async_clients() as (first, second):
        clients = (first, second)
        tokens = []
        for client, email in zip(clients, cashier_emails, strict=True):
            login = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": ACTOR_PASSWORD}
            )
            assert login.status_code == 200
            tokens.append(login.json()["access_token"])
        try:
            async with database.transaction():
                await database.fetchval(
                    "SELECT id FROM public.orders WHERE id=$1 FOR UPDATE", order_id
                )
                tasks = [
                    asyncio.create_task(
                        client.post(
                            f"/api/v1/orders/{order_id}/payments",
                            json={"amount": "7.00", "method_code": "EFECTIVO"},
                            headers={
                                "Authorization": "Bearer " + token,
                                "Idempotency-Key": f"race-{index}-{uuid4()}",
                            },
                        )
                    )
                    for index, (client, token) in enumerate(zip(clients, tokens, strict=True))
                ]
                await wait_for_lock_waiters(database, tasks)
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        assert sorted(response.status_code for response in responses) == [200, 409]
    dsn, _ = _test_database_target()
    third = await asyncpg.connect(dsn)
    try:
        async with third.transaction(isolation="repeatable_read"):
            assert await third.fetchval(
                "SELECT COALESCE(SUM(amount),0) FROM public.payments WHERE order_id=$1", order_id
            ) == Decimal("7.00")
            assert (
                await third.fetchval(
                    "SELECT count(*) FROM public.payments WHERE order_id=$1 AND kind='COLLECTION'",
                    order_id,
                )
                == 1
            )
            assert (
                await third.fetchval(
                    "SELECT count(*) FROM public.idempotency_requests "
                    "WHERE operation='RECORD_COLLECTION' AND result_order_id=$1",
                    order_id,
                )
                == 1
            )
    finally:
        await third.close()


@pytest.mark.asyncio
async def test_same_key_concurrent_retry_records_one_collection(
    database: asyncpg.Connection,
) -> None:
    product_id = await product(database, price="10.00", stock=2)
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    cashier_id, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        order_response = client.post(
            "/api/v1/orders/waiter",
            json={
                "table_id": str(table_id),
                "items": [{"product_id": str(product_id), "quantity": 1}],
            },
            headers={**waiter, "Idempotency-Key": "same-key-order"},
        )
        assert order_response.status_code == 201, order_response.text
        order_id = UUID(order_response.json()["id"])
    request_key = f"same-collection-{uuid4()}"
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with async_clients() as (first, second):
        login = await first.post(
            "/api/v1/auth/login", json={"email": cashier_email, "password": ACTOR_PASSWORD}
        )
        assert login.status_code == 200
        headers = {
            "Authorization": "Bearer " + login.json()["access_token"],
            "Idempotency-Key": request_key,
        }
        try:
            async with database.transaction():
                await database.fetchval(
                    "SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                    f"RECORD_COLLECTION:{cashier_id}:{request_key}",
                )
                tasks = [
                    asyncio.create_task(
                        client.post(
                            f"/api/v1/orders/{order_id}/payments",
                            json={"amount": "2.00", "method_code": "EFECTIVO"},
                            headers=headers,
                        )
                    )
                    for client in (first, second)
                ]
                await wait_for_lock_waiters(database, tasks, event="advisory")
            responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        assert [response.status_code for response in responses] == [200, 200]
        assert responses[0].json() == responses[1].json()
    dsn, _ = _test_database_target()
    third = await asyncpg.connect(dsn)
    try:
        async with third.transaction(isolation="repeatable_read"):
            assert (
                await third.fetchval(
                    "SELECT count(*) FROM public.payments WHERE order_id=$1 AND kind='COLLECTION'",
                    order_id,
                )
                == 1
            )
            assert (
                await third.fetchval(
                    "SELECT count(*) FROM public.idempotency_requests "
                    "WHERE operation='RECORD_COLLECTION' AND result_order_id=$1",
                    order_id,
                )
                == 1
            )
    finally:
        await third.close()
