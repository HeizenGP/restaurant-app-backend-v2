"""Validate simulated collection method/reference through HTTP and PostgreSQL."""

from decimal import Decimal
from uuid import UUID

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
async def test_reference_validation_history_and_idempotency(database: asyncpg.Connection) -> None:
    product_id = await product(database, price="40.00", stock=1)
    table_id = await table(database)
    _, waiter_email = await actor(database, "WAITER")
    _, cashier_email = await actor(database, "CASHIER")
    with api_client() as client:
        waiter = bearer(client, waiter_email)
        cashier = bearer(client, cashier_email)
        order = client.post(
            "/api/v1/orders/waiter",
            json={
                "table_id": str(table_id),
                "items": [{"product_id": str(product_id), "quantity": 1}],
            },
            headers={**waiter, "Idempotency-Key": "reference-order"},
        )
        assert order.status_code == 201, order.text
        order_id = UUID(order.json()["id"])
        path = f"/api/v1/orders/{order_id}/payments"
        invalid = [
            {"method_code": "SIMULADO"},
            {"method_code": "YAPE"},
            {"method_code": "YAPE", "reference_code": "123456789"},
            {"method_code": "YAPE", "reference_code": "98765432"},
            {"method_code": "PLIN", "reference_code": "98765432X"},
            {"method_code": "TARJETA", "reference_code": "1234567890123456"},
            {"method_code": "EFECTIVO", "reference_code": "123456789"},
        ]
        for index, details in enumerate(invalid):
            denied = client.post(
                path,
                json={"amount": "1.00", **details},
                headers={**cashier, "Idempotency-Key": f"invalid-ref-{index}"},
            )
            assert denied.status_code == 422, denied.text
        cases = [
            ("YAPE", "987654321"),
            ("PLIN", "912345678"),
            ("TARJETA", "123456789"),
            ("EFECTIVO", None),
        ]
        for index, (method, reference) in enumerate(cases):
            payload = {
                "amount": "10.00",
                "method_code": method,
                "reference_code": reference,
            }
            headers = {**cashier, "Idempotency-Key": f"valid-ref-{index}"}
            success = client.post(path, json=payload, headers=headers)
            assert success.status_code == 200, success.text
            replay = client.post(path, json=payload, headers=headers)
            assert replay.status_code == 200 and replay.json() == success.json()
            if method == "YAPE":
                changed = client.post(
                    path,
                    json={**payload, "reference_code": "999999999"},
                    headers=headers,
                )
                assert changed.status_code == 409, changed.text
        summary = client.get(path, headers=cashier)
        assert summary.status_code == 200
        assert summary.json()["payment_status"] == "PAID"
        assert Decimal(summary.json()["balance"]) == Decimal("0.00")
        assert {
            (item["method_code"], item["reference_code"])
            for item in summary.json()["payments"]
        } == set(cases)
    rows = await database.fetch(
        "SELECT method_code, reference_code FROM public.payments "
        "WHERE order_id=$1 AND kind='COLLECTION'",
        order_id,
    )
    assert {(row["method_code"], row["reference_code"]) for row in rows} == set(cases)
