"""HTTP endpoints for delivery zones, coordinate validation, and geocoding."""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from restaurant_app.modules.m07_fulfillment.delivery_zones import (
    KAIRO_ADDRESS,
    KAIRO_LATITUDE,
    KAIRO_LONGITUDE,
    KAIRO_NAME,
    evaluate_delivery_zone,
    reverse_geocode_osm,
    search_address_osm,
)

delivery_router = APIRouter(prefix="/delivery", tags=["Delivery & Geocoding"])


class CheckZoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)


class DeliveryZoneResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_covered: bool
    distance_km: float
    zone_code: str | None = None
    zone_name: str | None = None
    delivery_fee: str | None = None
    estimated_min_minutes: int | None = None
    estimated_max_minutes: int | None = None
    message: str | None = None
    restaurant_name: str = KAIRO_NAME
    restaurant_address: str = KAIRO_ADDRESS
    restaurant_latitude: float = KAIRO_LATITUDE
    restaurant_longitude: float = KAIRO_LONGITUDE


class GeocodeResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    display_name: str
    address: str
    district: str | None = None
    city: str | None = None
    latitude: float
    longitude: float


@delivery_router.post(
    "/check-zone",
    response_model=DeliveryZoneResponse,
    summary="Validate GPS coordinates and quote delivery zone / fee",
)
async def check_delivery_zone(payload: CheckZoneRequest) -> DeliveryZoneResponse:
    quote = evaluate_delivery_zone(payload.latitude, payload.longitude)
    return DeliveryZoneResponse(
        is_covered=quote.is_covered,
        distance_km=quote.distance_km,
        zone_code=quote.zone_code,
        zone_name=quote.zone_name,
        delivery_fee=quote.delivery_fee,
        estimated_min_minutes=quote.estimated_min_minutes,
        estimated_max_minutes=quote.estimated_max_minutes,
        message=quote.message,
        restaurant_name=quote.restaurant_name,
        restaurant_address=quote.restaurant_address,
        restaurant_latitude=quote.restaurant_latitude,
        restaurant_longitude=quote.restaurant_longitude,
    )


@delivery_router.get(
    "/zones",
    summary="List available delivery zones and operational parameters",
)
async def list_delivery_zones() -> dict[str, Any]:
    return {
        "restaurant": {
            "name": KAIRO_NAME,
            "address": KAIRO_ADDRESS,
            "latitude": KAIRO_LATITUDE,
            "longitude": KAIRO_LONGITUDE,
        },
        "zones": [
            {
                "code": "ZONE_1",
                "name": "Zona 1 - San Isidro / Lince / Miraflores Cercano",
                "max_distance_km": 3.0,
                "fee": "5.00",
                "estimated_minutes": "20 - 35 min",
            },
            {
                "code": "ZONE_2",
                "name": "Zona 2 - Miraflores / San Borja / Surquillo / Jesús María",
                "max_distance_km": 7.0,
                "fee": "8.00",
                "estimated_minutes": "35 - 50 min",
            },
            {
                "code": "ZONE_3",
                "name": "Zona 3 - Santiago de Surco / Barranco / Magdalena / Pueblo Libre",
                "max_distance_km": 12.0,
                "fee": "12.00",
                "estimated_minutes": "45 - 65 min",
            },
        ],
        "max_coverage_km": 12.0,
    }


@delivery_router.get(
    "/geocode/reverse",
    response_model=GeocodeResultResponse,
    summary="Reverse geocode GPS coordinates to readable address (OpenStreetMap proxy)",
)
async def reverse_geocode(
    latitude: float = Query(..., ge=-90.0, le=90.0),
    longitude: float = Query(..., ge=-180.0, le=180.0),
) -> GeocodeResultResponse:
    res = await reverse_geocode_osm(latitude, longitude)
    return GeocodeResultResponse(**res)


@delivery_router.get(
    "/geocode/search",
    response_model=list[GeocodeResultResponse],
    summary="Search addresses in Lima / Peru (OpenStreetMap proxy)",
)
async def search_address(
    query: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(5, ge=1, le=10),
) -> list[GeocodeResultResponse]:
    items = await search_address_osm(query, limit)
    return [GeocodeResultResponse(**item) for item in items]
