"""Delivery zones evaluation, distance computation and Nominatim geocoding proxy."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

logger = logging.getLogger("restaurant_app.delivery_zones")

# KAIRO Restaurant HQ Location (Av. Las Begonias 123, San Isidro, Lima, Peru)
KAIRO_LATITUDE = -12.0968
KAIRO_LONGITUDE = -77.0353
KAIRO_NAME = "KAIRO - Alta Cocina Asiática"
KAIRO_ADDRESS = "Av. Las Begonias 123, San Isidro, Lima"
MAX_DELIVERY_DISTANCE_KM = 12.0


@dataclass(frozen=True, slots=True)
class DeliveryZoneQuote:
    is_covered: bool
    distance_km: float
    zone_code: str | None
    zone_name: str | None
    delivery_fee: str | None
    estimated_min_minutes: int | None
    estimated_max_minutes: int | None
    message: str | None
    restaurant_name: str = KAIRO_NAME
    restaurant_address: str = KAIRO_ADDRESS
    restaurant_latitude: float = KAIRO_LATITUDE
    restaurant_longitude: float = KAIRO_LONGITUDE


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates in kilometers."""
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(radius_km * c, 2)


def evaluate_delivery_zone(
    latitude: float | Decimal, longitude: float | Decimal
) -> DeliveryZoneQuote:
    """Evaluate if coordinates are within KAIRO's delivery zones and return quote."""
    lat = float(latitude)
    lon = float(longitude)

    # Basic coordinate bounds validation
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return DeliveryZoneQuote(
            is_covered=False,
            distance_km=0.0,
            zone_code=None,
            zone_name=None,
            delivery_fee=None,
            estimated_min_minutes=None,
            estimated_max_minutes=None,
            message="Coordenadas geográficas inválidas.",
        )

    distance = haversine_distance_km(KAIRO_LATITUDE, KAIRO_LONGITUDE, lat, lon)

    if distance <= 3.0:
        return DeliveryZoneQuote(
            is_covered=True,
            distance_km=distance,
            zone_code="ZONE_1",
            zone_name="Zona 1 - San Isidro / Lince / Miraflores Cercano",
            delivery_fee="5.00",
            estimated_min_minutes=20,
            estimated_max_minutes=35,
            message="¡Estás dentro de la zona exprés de KAIRO!",
        )
    elif distance <= 7.0:
        return DeliveryZoneQuote(
            is_covered=True,
            distance_km=distance,
            zone_code="ZONE_2",
            zone_name="Zona 2 - Miraflores / San Borja / Surquillo / Jesús María",
            delivery_fee="8.00",
            estimated_min_minutes=35,
            estimated_max_minutes=50,
            message="Entrega estándar disponible.",
        )
    elif distance <= MAX_DELIVERY_DISTANCE_KM:
        return DeliveryZoneQuote(
            is_covered=True,
            distance_km=distance,
            zone_code="ZONE_3",
            zone_name="Zona 3 - Santiago de Surco / Barranco / Magdalena / Pueblo Libre",
            delivery_fee="12.00",
            estimated_min_minutes=45,
            estimated_max_minutes=65,
            message="Zona extendida disponible para pedidos.",
        )
    else:
        return DeliveryZoneQuote(
            is_covered=False,
            distance_km=distance,
            zone_code=None,
            zone_name=None,
            delivery_fee=None,
            estimated_min_minutes=None,
            estimated_max_minutes=None,
            message=(
                f"La ubicación se encuentra a {distance:.1f} km, fuera de nuestra zona de reparto "
                f"(máximo {MAX_DELIVERY_DISTANCE_KM:.0f} km desde San Isidro)."
            ),
        )


def _http_get_json(url: str, timeout: float = 4.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "KairoRestaurantApp/1.0 (contacto@kairo.pe)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read().decode("utf-8")
        return json.loads(data)


async def reverse_geocode_osm(lat: float, lon: float) -> dict[str, Any]:
    """Reverse geocode GPS coordinates to a formatted address using Nominatim with fallback."""
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}&addressdetails=1"
    try:
        data = await asyncio.to_thread(_http_get_json, url, 4.0)
        display_name = data.get("display_name", "")
        address_dict = data.get("address", {})

        road = address_dict.get("road") or address_dict.get("pedestrian") or ""
        house_number = address_dict.get("house_number", "")
        neighbourhood = (
            address_dict.get("suburb")
            or address_dict.get("neighbourhood")
            or address_dict.get("residential")
            or ""
        )
        city_district = address_dict.get("city_district") or address_dict.get("district") or ""
        city = address_dict.get("city") or address_dict.get("town") or "Lima"

        parts: list[str] = []
        if road:
            parts.append(f"{road} {house_number}".strip())
        if neighbourhood:
            parts.append(neighbourhood)
        if city_district and city_district not in parts:
            parts.append(city_district)

        readable_address = ", ".join(parts) if parts else display_name

        return {
            "display_name": display_name or f"Ubicación ({lat:.4f}, {lon:.4f})",
            "address": readable_address or display_name or f"Coordenadas: {lat:.5f}, {lon:.5f}",
            "district": city_district or neighbourhood or None,
            "city": city,
            "latitude": lat,
            "longitude": lon,
        }
    except Exception as exc:
        logger.warning("Reverse geocoding OSM failed (%s), using coordinate fallback: %s", url, exc)
        return {
            "display_name": f"Ubicación en Lima ({lat:.4f}, {lon:.4f})",
            "address": f"Coordenadas GPS: {lat:.5f}, {lon:.5f}",
            "district": "Lima Metropolitana",
            "city": "Lima",
            "latitude": lat,
            "longitude": lon,
        }


async def search_address_osm(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search addresses in Peru / Lima using Nominatim with fallback."""
    encoded_query = urllib.parse.quote(query)
    url = (
        f"https://nominatim.openstreetmap.org/search?format=jsonv2&q={encoded_query}"
        f"&countrycodes=pe&addressdetails=1&limit={limit}"
    )
    try:
        results = await asyncio.to_thread(_http_get_json, url, 4.0)
        output: list[dict[str, Any]] = []
        for item in results:
            addr = item.get("address", {})
            road = addr.get("road") or addr.get("pedestrian") or ""
            house_number = addr.get("house_number", "")
            suburb = addr.get("suburb") or addr.get("neighbourhood") or ""
            district = addr.get("city_district") or addr.get("district") or ""
            city = addr.get("city") or addr.get("town") or "Lima"

            parts: list[str] = []
            if road:
                parts.append(f"{road} {house_number}".strip())
            if suburb:
                parts.append(suburb)
            if district and district not in parts:
                parts.append(district)

            formatted_short = ", ".join(parts) if parts else item.get("display_name", "")

            output.append(
                {
                    "display_name": item.get("display_name", ""),
                    "address": formatted_short,
                    "district": district or suburb or None,
                    "city": city,
                    "latitude": float(item.get("lat", 0.0)),
                    "longitude": float(item.get("lon", 0.0)),
                }
            )
        return output
    except Exception as exc:
        logger.warning("Search address OSM failed (%s): %s", query, exc)
        return []
