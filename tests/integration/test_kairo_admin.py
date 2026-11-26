"""Exercise administration and checkout against disposable PostgreSQL."""

from decimal import Decimal

import asyncpg
import pytest

from tests.integration.test_m04_confirm_order import actor, api_client, bearer, product, table

pytest_plugins = ("tests.integration.test_initial_migration",)
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_register_and_item_checkout_are_atomic_and_attributable(database: asyncpg.Connection) -> None:
    item = await product(database, price="10.00", stock=20)
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    cashier_id, cashier_email = await actor(database, "CASHIER")
    _, cook_email = await actor(database, "KITCHEN")
    prefix = "/api/v1"
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        cashier = bearer(client, cashier_email)
        cook = bearer(client, cook_email)
        orders = []
        for count in (1, 2):
            order = client.post(
                f"{prefix}/orders/waiter", headers={**waiter, "Idempotency-Key": f"admin-test-{count}"},
                json={"table_id": str(table_id), "items": [{"product_id": str(item), "quantity": count}]},
            )
            assert order.status_code == 201, order.text
            orders.append(order.json())
        pending = client.get(f"{prefix}/kitchen", headers=cook)
        assert pending.status_code == 200, pending.text
        for ticket in pending.json():
            for transition in ("start", "ready"):
                response = client.post(f"{prefix}/kitchen/{ticket['id']}/{transition}", headers=cook)
                assert response.status_code == 200, response.text
        account_path = f"{prefix}/tables/{table_id}/account"
        account = client.get(account_path, headers=cashier)
        assert account.status_code == 200, account.text
        account_data = account.json()
        target_order_id = orders[-1]["id"]
        target = next(order for order in account_data["orders"] if order["id"] == target_order_id)
        checkout = {
            "account_id": account_data["id"],
            "payments": [
                {"amount": "6.00", "method_code": "EFECTIVO"},
                {"amount": "4.00", "method_code": "YAPE", "reference_code": "912345678"},
            ],
            "items": [{"item_id": target["lines"][0]["item_id"], "quantity": 1}],
        }
        path = f"{account_path}/checkout"
        key = {**cashier, "Idempotency-Key": "mixed-admin-test"}
        assert client.post(path, headers=key, json=checkout).status_code == 409
        opened = client.post(f"{prefix}/cash-shifts", headers=cashier, json={"initial_amount": 100})
        assert opened.status_code == 201, opened.text
        shift_id = opened.json()["id"]
        assert client.post(f"{prefix}/cash-shifts", headers=cashier, json={"initial_amount": 1}).status_code == 409
        partial = client.post(path, headers=key, json=checkout)
        assert partial.status_code == 200, partial.text
        assert Decimal(partial.json()["balance"]) == Decimal(20)
        assert client.post(path, headers=key, json=checkout).json() == partial.json()
        target = next(order for order in partial.json()["orders"] if order["id"] == target_order_id)
        assert target["lines"][0]["paid_quantity"] == 1
        assert Decimal(target["paid_amount"]) == Decimal(10)
        assert Decimal(client.get(f"{prefix}/orders/{target_order_id}/payments", headers=cashier).json()["paid_amount"]) == Decimal(10)
        payment_count = await database.fetchval("SELECT count(*) FROM public.payments")
        assert payment_count == 2
        closed_bill = client.post(
            path, headers={**cashier, "Idempotency-Key": "close-admin-test"},
            json={"account_id": account_data["id"], "payments": [{"amount": "20", "method_code": "EFECTIVO"}]},
        )
        assert closed_bill.status_code == 200, closed_bill.text
        assert closed_bill.json()["status"] == "PAID"
        assert not await database.fetchval("SELECT is_occupied FROM public.restaurant_tables WHERE id=$1", table_id)
        close = client.post(f"{prefix}/cash-shifts/{shift_id}/close", headers=cashier, json={"counted_cash": 127})
        assert close.status_code == 200, close.text
        assert Decimal(close.json()["difference"]) == Decimal(1)
        assert Decimal(close.json()["totals"]["YAPE"]) == Decimal(4)
        assert client.get(f"{prefix}/cash-shifts/current", headers=cashier).json() is None
        history = client.get(f"{prefix}/payments", headers=cashier, params={"method": "YAPE"})
        assert history.status_code == 200, history.text
        assert len(history.json()) == 1
        assert history.json()[0]["recorded_by_user_id"] == str(cashier_id)


@pytest.mark.asyncio
async def test_admin_controls_catalog_work_shifts_audit_and_reports(database: asyncpg.Connection) -> None:
    admin_id, admin_email = await actor(database, "ADMIN")
    worker_id, worker_email = await actor(database, "KITCHEN")
    item = await product(database)
    prefix = "/api/v1"
    with api_client() as client:
        admin = bearer(client, admin_email)
        cook = bearer(client, worker_email)
        assert client.get(f"{prefix}/audit/activity", headers=cook).status_code == 403
        assert client.post(f"{prefix}/users/{admin_id}/roles", headers=admin, json={"role": "CASHIER"}).status_code == 403
        stock_path = f"{prefix}/catalog/products/{item}/stock"
        assert client.put(stock_path, headers=admin, json={"quantity": 1}).status_code == 422
        changed = client.put(stock_path, headers=admin, json={
            "quantity": 1, "reason": "Conteo físico", "minimum_stock": 4, "expected_quantity": 10,
        })
        assert changed.status_code == 200, changed.text
        assert changed.json()["minimum_stock"] == 4
        assert client.put(
            stock_path, headers=admin, json={"quantity": 5, "reason": "Conteo anterior", "expected_quantity": 10},
        ).status_code == 409
        events = client.get(f"{prefix}/audit/activity", headers=admin, params={"resource": "stock_movements"})
        assert events.status_code == 200, events.text
        assert events.json()[0]["actor_id"] == str(admin_id)
        assert events.json()[0]["after"]["reason"] == "Conteo físico"
        failed_login = client.post(f"{prefix}/auth/login", json={"email": admin_email, "password": "wrong"})
        assert failed_login.status_code == 401
        accesses = client.get(f"{prefix}/audit/access", headers=admin)
        assert accesses.json()[0]["outcome"] == "REJECTED"
        path = f"{prefix}/administration/work-shifts"
        body = {"user_id": str(worker_id), "starts_at": "2026-11-25T14:00:00Z", "ends_at": "2026-11-25T20:00:00Z"}
        shift = client.post(path, headers=admin, json=body)
        assert shift.status_code == 201, shift.text
        assert client.post(path, headers=admin, json=body).status_code == 409
        for name in ("sales", "orders", "products", "occupancy", "inventory", "staff"):
            report = client.get(f"{prefix}/reports/analytics/{name}", headers=admin, params={"start": "2026-11-01", "end": "2026-11-25"})
            assert report.status_code == 200, (name, report.text)
            assert "series" in report.json()
        notifications = client.get(f"{prefix}/administration/notifications", headers=admin)
        assert notifications.status_code == 200, notifications.text
