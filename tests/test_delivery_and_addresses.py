"""Tests for delivery zone endpoints, OSM proxy, and address endpoint guards."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from restaurant_app.core.config import Settings
from restaurant_app.main import create_app


def get_test_client() -> TestClient:
    settings = Settings(
        postgres_password="fake-password",
        jwt_secret="0123456789abcdef0123456789abcdef",
    )
    return TestClient(create_app(settings))


def test_delivery_check_zone_san_isidro() -> None:
    with get_test_client() as client:
        response = client.post(
            "/api/v1/delivery/check-zone",
            json={"latitude": -12.0968, "longitude": -77.0353},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_covered"] is True
        assert data["zone_code"] == "ZONE_1"
        assert data["delivery_fee"] == "5.00"
        assert data["restaurant_name"] == "KAIRO - Alta Cocina Asiática"


def test_delivery_check_zone_out_of_reach() -> None:
    with get_test_client() as client:
        response = client.post(
            "/api/v1/delivery/check-zone",
            json={"latitude": -11.5000, "longitude": -77.3000},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_covered"] is False
        assert data["zone_code"] is None
        assert "fuera de nuestra zona" in data["message"]


def test_delivery_zones_list() -> None:
    with get_test_client() as client:
        response = client.get("/api/v1/delivery/zones")
        assert response.status_code == 200
        data = response.json()
        assert len(data["zones"]) == 3
        assert data["restaurant"]["name"] == "KAIRO - Alta Cocina Asiática"


def test_delivery_reverse_geocode_endpoint() -> None:
    with (
        patch(
            "restaurant_app.modules.m07_fulfillment.delivery_zones._http_get_json",
            side_effect=Exception("Timeout"),
        ),
        get_test_client() as client,
    ):
        response = client.get(
            "/api/v1/delivery/geocode/reverse?latitude=-12.0968&longitude=-77.0353"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["latitude"] == -12.0968
        assert data["longitude"] == -77.0353
        assert "Coordenadas GPS" in data["address"]


def test_delivery_search_geocode_endpoint() -> None:
    with (
        patch(
            "restaurant_app.modules.m07_fulfillment.delivery_zones._http_get_json",
            return_value=[
                {
                    "display_name": "Av. Las Begonias, San Isidro, Lima, Perú",
                    "lat": "-12.0968",
                    "lon": "-77.0353",
                    "address": {
                        "road": "Avenida Las Begonias",
                        "house_number": "123",
                        "district": "San Isidro",
                        "city": "Lima",
                    },
                }
            ],
        ),
        get_test_client() as client,
    ):
        response = client.get("/api/v1/delivery/geocode/search?query=Begonias+San+Isidro")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["district"] == "San Isidro"
        assert data[0]["latitude"] == -12.0968


def test_user_addresses_requires_auth() -> None:
    with get_test_client() as client:
        response = client.get("/api/v1/users/me/addresses")
        assert response.status_code == 401
