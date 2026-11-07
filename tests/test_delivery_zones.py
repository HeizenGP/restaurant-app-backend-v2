"""Unit tests for delivery zone calculations and coordinate validations."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from restaurant_app.modules.m07_fulfillment.delivery_zones import (
    KAIRO_LATITUDE,
    KAIRO_LONGITUDE,
    evaluate_delivery_zone,
    haversine_distance_km,
    reverse_geocode_osm,
    search_address_osm,
)


def test_haversine_distance_same_point_is_zero() -> None:
    distance = haversine_distance_km(
        KAIRO_LATITUDE, KAIRO_LONGITUDE, KAIRO_LATITUDE, KAIRO_LONGITUDE
    )
    assert distance == 0.0


def test_haversine_distance_approximate() -> None:
    # Miraflores Parque Kennedy ~ 2.5 km from San Isidro Las Begonias
    distance = haversine_distance_km(KAIRO_LATITUDE, KAIRO_LONGITUDE, -12.1215, -77.0298)
    assert 2.0 <= distance <= 3.5


def test_evaluate_zone_exact_restaurant_location() -> None:
    quote = evaluate_delivery_zone(Decimal(str(KAIRO_LATITUDE)), Decimal(str(KAIRO_LONGITUDE)))
    assert quote.is_covered is True
    assert quote.distance_km == 0.0
    assert quote.zone_code == "ZONE_1"
    assert quote.delivery_fee == "5.00"
    assert quote.estimated_min_minutes == 20


def test_evaluate_zone_tier_two_miraflores() -> None:
    # Approx 4 km
    lat = -12.1300
    lon = -77.0200
    quote = evaluate_delivery_zone(lat, lon)
    assert quote.is_covered is True
    assert quote.zone_code == "ZONE_2"
    assert quote.delivery_fee == "8.00"


def test_evaluate_zone_tier_three_surco() -> None:
    # Approx 9 km away
    lat = -12.1400
    lon = -76.9800
    quote = evaluate_delivery_zone(lat, lon)
    assert quote.is_covered is True
    assert quote.zone_code == "ZONE_3"
    assert quote.delivery_fee == "12.00"


def test_evaluate_zone_out_of_range() -> None:
    # Ancón / Chosica / Out of Lima (> 25 km)
    quote = evaluate_delivery_zone(-11.7500, -77.1500)
    assert quote.is_covered is False
    assert quote.zone_code is None
    assert quote.delivery_fee is None
    assert "fuera de nuestra zona de reparto" in (quote.message or "")


def test_evaluate_zone_invalid_coordinates() -> None:
    quote = evaluate_delivery_zone(95.0, 200.0)
    assert quote.is_covered is False
    assert quote.message == "Coordenadas geográficas inválidas."


@pytest.mark.asyncio
async def test_reverse_geocode_osm_fallback_on_network_error() -> None:
    with patch(
        "restaurant_app.modules.m07_fulfillment.delivery_zones._http_get_json",
        side_effect=Exception("Network timeout"),
    ):
        result = await reverse_geocode_osm(-12.0968, -77.0353)
        assert result["latitude"] == -12.0968
        assert result["longitude"] == -77.0353
        assert "Coordenadas GPS" in result["address"]


@pytest.mark.asyncio
async def test_search_address_osm_fallback_on_error() -> None:
    with patch(
        "restaurant_app.modules.m07_fulfillment.delivery_zones._http_get_json",
        side_effect=Exception("Connection refused"),
    ):
        results = await search_address_osm("Begonias San Isidro")
        assert results == []
