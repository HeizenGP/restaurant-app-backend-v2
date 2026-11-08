"""Tests for KAIRO Admin endpoints: Users/Staff, Products listing, Stock Movements, Payments, and Dashboard."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from restaurant_app.core.config import Settings
from restaurant_app.core.dependencies import get_db_session
from restaurant_app.main import create_app
from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import (
    get_current_principal,
    require_admin,
)
from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind, User
from restaurant_app.modules.m02_catalog_stock.adapters.inbound.http.dependencies import (
    require_catalog_admin,
)
from restaurant_app.modules.m06_payments.adapters.inbound.http.dependencies import require_cashier


def make_admin_principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        session_id=uuid4(),
        roles=frozenset({RoleCode.ADMIN, RoleCode.SUPER_ADMIN}),
        kind=SessionKind.USER,
    )


def test_users_list_and_create_and_status() -> None:
    settings = Settings(
        postgres_password="fake-password",
        jwt_secret="0123456789abcdef0123456789abcdef",
    )
    app = create_app(settings)
    admin = make_admin_principal()
    mock_session = AsyncMock()

    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db_session] = lambda: mock_session

    sample_user = User(
        id=uuid4(),
        display_name="Chef Hiro",
        email="hiro@kairo.pe",
        is_active=True,
        roles=frozenset({RoleCode.KITCHEN}),
        created_at=datetime.now(UTC),
        phone="987654321",
    )

    with patch("restaurant_app.modules.m01_access.adapters.outbound.repositories.SqlAlchemyUserRepository.list_users", new_callable=AsyncMock) as mock_list, \
         patch("restaurant_app.modules.m01_access.adapters.outbound.repositories.SqlAlchemyUserRepository.create_staff", new_callable=AsyncMock) as mock_create, \
         patch("restaurant_app.modules.m01_access.adapters.outbound.repositories.SqlAlchemyUserRepository.set_active_status", new_callable=AsyncMock) as mock_status:
        
        mock_list.return_value = [sample_user]
        mock_create.return_value = sample_user
        mock_status.return_value = sample_user

        with TestClient(app) as client:
            # 1. List users
            res = client.get("/api/v1/users", headers={"Authorization": "Bearer fake"})
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 1
            assert data[0]["display_name"] == "Chef Hiro"
            assert data[0]["email"] == "hiro@kairo.pe"
            assert "KITCHEN" in data[0]["roles"]

            # 2. Create staff
            res_create = client.post(
                "/api/v1/users",
                headers={"Authorization": "Bearer fake"},
                json={
                    "display_name": "Mozo Carlos",
                    "email": "carlos@kairo.pe",
                    "password": "Password123",
                    "role": "WAITER",
                    "phone": "999888777",
                },
            )
            assert res_create.status_code == 201

            # 3. Toggle status
            res_patch = client.patch(
                f"/api/v1/users/{sample_user.id}/status",
                headers={"Authorization": "Bearer fake"},
                json={"is_active": False},
            )
            assert res_patch.status_code == 200


def test_catalog_all_products_and_movements() -> None:
    settings = Settings(
        postgres_password="fake-password",
        jwt_secret="0123456789abcdef0123456789abcdef",
    )
    app = create_app(settings)
    admin = make_admin_principal()
    mock_session = AsyncMock()

    app.dependency_overrides[require_catalog_admin] = lambda: admin
    app.dependency_overrides[get_db_session] = lambda: mock_session

    from restaurant_app.modules.m02_catalog_stock.domain.entities import Product
    sample_product = Product(
        id=uuid4(),
        category_id=uuid4(),
        name="Chaufán Especial",
        price=Decimal("42.00"),
        stock_qty=25,
        is_available=True,
        image_url="https://kairo.pe/img/chaufan.jpg",
        description="Arroz chaufa al wok",
    )

    with patch("restaurant_app.modules.m02_catalog_stock.adapters.outbound.repositories.SqlAlchemyCatalogRepository.list_all_products", new_callable=AsyncMock) as mock_products, \
         patch("restaurant_app.modules.m02_catalog_stock.adapters.outbound.repositories.SqlAlchemyCatalogRepository.list_stock_movements", new_callable=AsyncMock) as mock_movements:
        
        mock_products.return_value = [sample_product]
        mock_movements.return_value = [
            {
                "id": str(uuid4()),
                "product_id": str(sample_product.id),
                "product_name": "Chaufán Especial",
                "kind": "MANUAL",
                "quantity_delta": 10,
                "recorded_at": datetime.now(UTC).isoformat(),
                "actor_user_id": str(admin.user_id),
            }
        ]

        with TestClient(app) as client:
            res = client.get("/api/v1/catalog/products")
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 1
            assert data[0]["name"] == "Chaufán Especial"

            res_mov = client.get("/api/v1/catalog/stock/movements", headers={"Authorization": "Bearer fake"})
            assert res_mov.status_code == 200
            data_mov = res_mov.json()
            assert len(data_mov) == 1
            assert data_mov[0]["product_name"] == "Chaufán Especial"


def test_payments_list_endpoint() -> None:
    settings = Settings(
        postgres_password="fake-password",
        jwt_secret="0123456789abcdef0123456789abcdef",
    )
    app = create_app(settings)
    cashier = Principal(
        user_id=uuid4(),
        session_id=uuid4(),
        roles=frozenset({RoleCode.CASHIER, RoleCode.ADMIN}),
        kind=SessionKind.USER,
    )
    mock_session = AsyncMock()

    app.dependency_overrides[require_cashier] = lambda: cashier
    app.dependency_overrides[get_db_session] = lambda: mock_session

    from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel
    p_id = uuid4()
    o_id = uuid4()
    u_id = uuid4()

    mock_pm = MagicMock(spec=PaymentModel)
    mock_pm.id = p_id
    mock_pm.order_id = o_id
    mock_pm.kind = "COLLECTION"
    mock_pm.amount = Decimal("85.50")
    mock_pm.method_code = "YAPE"
    mock_pm.reference_code = "987654321"
    mock_pm.recorded_by_user_id = u_id
    mock_pm.recorded_at = datetime.now(UTC)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_pm]
    mock_session.scalars.return_value = mock_scalars

    with TestClient(app) as client:
        res = client.get("/api/v1/payments", headers={"Authorization": "Bearer fake"})
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["kind"] == "COLLECTION"
        assert data[0]["amount"] == 85.50
        assert data[0]["method_code"] == "YAPE"


def test_dashboard_reports_endpoint() -> None:
    settings = Settings(
        postgres_password="fake-password",
        jwt_secret="0123456789abcdef0123456789abcdef",
    )
    app = create_app(settings)
    admin = make_admin_principal()
    mock_session = AsyncMock()

    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db_session] = lambda: mock_session

    # Mock scalar returns for the queries
    mock_session.scalar.side_effect = [
        Decimal("1450.00"),  # today_sales
        12,                  # today_orders_count
        4,                   # active_orders_count
        8,                   # total_tables_count
        3,                   # occupied_tables_count
        24,                  # total_products_count
        2,                   # low_stock_count
    ]

    mock_execute = MagicMock()
    # modalities, statuses, top products
    mock_execute.all.side_effect = [
        [("LOCAL", 6), ("DELIVERY", 4), ("PICKUP", 2)],
        [("CONFIRMED", 3), ("REQUESTED", 1), ("CLOSED", 8)],
        [("Arroz Chaufa Especial", 15), ("Siu Mai de Langostinos", 12)],
    ]
    mock_session.execute.return_value = mock_execute

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_session.scalars.return_value = mock_scalars

    with TestClient(app) as client:
        res = client.get("/api/v1/reports/dashboard", headers={"Authorization": "Bearer fake"})
        assert res.status_code == 200
        data = res.json()
        assert data["today_sales"] == 1450.0
        assert data["today_orders_count"] == 12
        assert data["active_orders_count"] == 4
        assert data["occupied_tables_count"] == 3
        assert data["total_tables_count"] == 8
        assert data["total_products_count"] == 24
        assert data["low_stock_count"] == 2
        assert data["orders_by_modality"]["LOCAL"] == 6
        assert data["orders_by_status"]["CONFIRMED"] == 3
        assert len(data["top_products"]) == 2
