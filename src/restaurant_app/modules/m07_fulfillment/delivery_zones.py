"""Delivery zones evaluation, distance computation and Nominatim geocoding proxy."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
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


# In-memory caching for reverse geocoding and Photon search (TTL: 15 minutes)
_CACHE_TTL_SECONDS = 900.0
_MAX_CACHE_SIZE = 1000
_REVERSE_GEOCODE_CACHE: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
_SEARCH_CACHE: dict[tuple[str, int], tuple[float, list[dict[str, Any]]]] = {}


def _http_get_json(url: str, timeout: float = 4.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "KairoRestaurantApp/2.0 (soporte@kairo.pe)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read().decode("utf-8")
        return json.loads(data)


async def reverse_geocode_osm(lat: float, lon: float) -> dict[str, Any]:
    """Reverse geocode GPS coordinates using Nominatim with caching and structured address parts.

    Respects OSM policies: rate-limiting via cache, proper User-Agent, and does not invent
    street names or house numbers if not provided by OpenStreetMap.
    """
    cache_key = (round(lat, 4), round(lon, 4))
    now = time.monotonic()
    if cache_key in _REVERSE_GEOCODE_CACHE:
        cached_time, cached_val = _REVERSE_GEOCODE_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            return cached_val

    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}&addressdetails=1"
    try:
        data = await asyncio.to_thread(_http_get_json, url, 4.0)
        display_name = data.get("display_name", "")
        address_dict = data.get("address", {})

        # Extract genuine cartographic components without inventing nonexistent data
        road = (
            address_dict.get("road")
            or address_dict.get("pedestrian")
            or address_dict.get("footway")
            or address_dict.get("path")
            or None
        )
        house_number = address_dict.get("house_number") or None
        neighbourhood = (
            address_dict.get("suburb")
            or address_dict.get("neighbourhood")
            or address_dict.get("residential")
            or address_dict.get("quarter")
            or None
        )
        district = (
            address_dict.get("city_district")
            or address_dict.get("district")
            or neighbourhood
            or None
        )
        province = (
            address_dict.get("county")
            or address_dict.get("city")
            or address_dict.get("town")
            or "Lima"
        )
        department = address_dict.get("state") or address_dict.get("region") or "Lima"

        # Build clean, legible street line and area line
        street_part = ""
        if road:
            street_part = f"{road} {house_number}".strip() if house_number else road

        area_parts: list[str] = []
        if district:
            area_parts.append(district)
        if province and province not in area_parts:
            area_parts.append(province)
        if department and department not in area_parts:
            area_parts.append(department)

        area_summary = ", ".join(area_parts)

        # Formulate readable address
        if street_part and area_summary:
            readable_address = f"{street_part}, {area_summary}"
        elif street_part:
            readable_address = street_part
        elif area_summary:
            readable_address = area_summary
        else:
            readable_address = display_name or f"Ubicación ({lat:.4f}, {lon:.4f})"

        result = {
            "display_name": display_name or readable_address,
            "address": readable_address,
            "street": road,
            "house_number": house_number,
            "district": district,
            "province": province,
            "department": department,
            "latitude": lat,
            "longitude": lon,
        }

        # Store in cache
        if len(_REVERSE_GEOCODE_CACHE) > _MAX_CACHE_SIZE:
            _REVERSE_GEOCODE_CACHE.pop(next(iter(_REVERSE_GEOCODE_CACHE)))
        _REVERSE_GEOCODE_CACHE[cache_key] = (now, result)

        return result
    except Exception as exc:
        logger.warning("Reverse geocoding OSM failed (%s), using coordinate fallback: %s", url, exc)
        return {
            "display_name": f"Ubicación en Lima ({lat:.4f}, {lon:.4f})",
            "address": f"Coordenadas GPS: {lat:.5f}, {lon:.5f}",
            "street": None,
            "house_number": None,
            "district": "Lima Metropolitana",
            "province": "Lima",
            "department": "Lima",
            "latitude": lat,
            "longitude": lon,
        }


async def search_address_photon(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Predictive address search / autocomplete using Photon (Komoot OSM Geocoder).

    Photon is explicitly designed for search-as-you-type and autocomplete on OpenStreetMap data.
    Biased around KAIRO HQ in San Isidro, Lima with caching to avoid rate-limit issues.
    """
    clean_query = query.strip()
    if len(clean_query) < 2:
        return []

    cache_key = (clean_query.lower(), limit)
    now = time.monotonic()
    if cache_key in _SEARCH_CACHE:
        cached_time, cached_val = _SEARCH_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            return cached_val

    encoded_query = urllib.parse.quote(clean_query)
    # Lima bounding box to prioritize local results: minLon, minLat, maxLon, maxLat
    url_with_bbox = (
        f"https://photon.komoot.io/api/?q={encoded_query}&lat={KAIRO_LATITUDE}&lon={KAIRO_LONGITUDE}"
        f"&limit={limit}&bbox=-77.30,-12.35,-76.70,-11.75"
    )

    try:
        data = await asyncio.to_thread(_http_get_json, url_with_bbox, 4.0)

        # Support both Photon GeoJSON {"features": [...]} and list responses
        if isinstance(data, list):
            output_list: list[dict[str, Any]] = []
            for item in data:
                addr = item.get("address", {})
                road = addr.get("road") or addr.get("pedestrian") or ""
                house_no = addr.get("house_number") or None
                dist = addr.get("city_district") or addr.get("district") or addr.get("suburb") or None
                cty = addr.get("city") or "Lima"
                output_list.append(
                    {
                        "display_name": item.get("display_name", ""),
                        "address": f"{road} {house_no}".strip() if house_no else road or item.get("display_name", ""),
                        "street": road or None,
                        "house_number": house_no,
                        "district": dist,
                        "province": cty,
                        "department": "Lima",
                        "latitude": float(item.get("lat", 0.0)),
                        "longitude": float(item.get("lon", 0.0)),
                    }
                )
            if output_list:
                return output_list

        features = data.get("features", []) if isinstance(data, dict) else []

        # If no results within bbox, retry without bbox restriction (biased by lat/lon)
        if not features:
            url_no_bbox = (
                f"https://photon.komoot.io/api/?q={encoded_query}&lat={KAIRO_LATITUDE}"
                f"&lon={KAIRO_LONGITUDE}&limit={limit}"
            )
            data = await asyncio.to_thread(_http_get_json, url_no_bbox, 4.0)
            if isinstance(data, list):
                features = []
            else:
                features = data.get("features", []) if isinstance(data, dict) else []

        output: list[dict[str, Any]] = []
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0])
            lon = float(coords[0]) if len(coords) > 0 else 0.0
            lat = float(coords[1]) if len(coords) > 1 else 0.0

            name = props.get("name") or ""
            street = props.get("street") or (name if props.get("type") == "street" else "")
            house_number = props.get("housenumber") or None
            district = props.get("district") or props.get("locality") or props.get("city") or None
            province = props.get("county") or props.get("city") or "Lima"
            department = props.get("state") or "Lima"

            # Formulate main street line (never inventing house numbers)
            main_line = ""
            if street:
                main_line = f"{street} {house_number}".strip() if house_number else street
            elif name:
                main_line = f"{name} {house_number}".strip() if house_number else name

            # Formulate area line
            area_items: list[str] = []
            if district:
                area_items.append(district)
            if province and province not in area_items:
                area_items.append(province)
            if department and department not in area_items:
                area_items.append(department)

            area_str = ", ".join(area_items)

            if main_line and area_str:
                formatted_address = f"{main_line}, {area_str}"
            elif main_line:
                formatted_address = main_line
            elif area_str:
                formatted_address = area_str
            else:
                formatted_address = f"Ubicación ({lat:.4f}, {lon:.4f})"

            output.append(
                {
                    "display_name": formatted_address,
                    "address": formatted_address,
                    "street": street or name or None,
                    "house_number": house_number,
                    "district": district,
                    "province": province,
                    "department": department,
                    "latitude": lat,
                    "longitude": lon,
                }
            )

        # Store in cache
        if len(_SEARCH_CACHE) > _MAX_CACHE_SIZE:
            _SEARCH_CACHE.pop(next(iter(_SEARCH_CACHE)))
        _SEARCH_CACHE[cache_key] = (now, output)

        return output
    except Exception as exc:
        logger.warning("Search address with Photon failed (%s): %s", clean_query, exc)
        return []


async def search_address_osm(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Alias for search_address_photon to preserve compatibility."""
    return await search_address_photon(query, limit)
