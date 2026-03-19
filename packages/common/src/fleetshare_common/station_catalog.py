from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any


STATION_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "PASIR_RIS_BLK_152",
        "name": "Block 152 Pasir Ris St 13",
        "address": "Block 152 Pasir Ris St 13",
        "area": "Pasir Ris",
        "latitude": 1.3725,
        "longitude": 103.9622,
        "nextAvailableTiming": "19 Mar, 18:00 - 19 Mar, 19:00",
    },
    {
        "id": "PASIR_RIS_BLK_149A",
        "name": "Pasir Ris St 13 - Blk 149A",
        "address": "Pasir Ris St 13 - Blk 149A",
        "area": "Pasir Ris",
        "latitude": 1.3716,
        "longitude": 103.9641,
        "nextAvailableTiming": "19 Mar, 18:00 - 19 Mar, 19:00",
    },
    {
        "id": "PASIR_RIS_ST_11",
        "name": "Pasir Ris Street 11",
        "address": "Pasir Ris Street 11",
        "area": "Pasir Ris",
        "latitude": 1.3708,
        "longitude": 103.9601,
        "nextAvailableTiming": "19 Mar, 20:00 - 19 Mar, 21:00",
    },
    {
        "id": "LOYANG_AVE",
        "name": "Loyang Avenue",
        "address": "Loyang Avenue",
        "area": "Loyang",
        "latitude": 1.3705,
        "longitude": 103.9687,
        "nextAvailableTiming": "19 Mar, 19:30 - 19 Mar, 20:30",
    },
    {
        "id": "FLORA_DR",
        "name": "Flora Drive",
        "address": "Flora Drive",
        "area": "Loyang",
        "latitude": 1.3574,
        "longitude": 103.9692,
        "nextAvailableTiming": "19 Mar, 21:00 - 19 Mar, 22:00",
    },
    {
        "id": "TAMPINES_ST_45",
        "name": "Tampines Street 45",
        "address": "Tampines Street 45",
        "area": "Tampines",
        "latitude": 1.3561,
        "longitude": 103.9518,
        "nextAvailableTiming": "20 Mar, 08:00 - 20 Mar, 09:00",
    },
    {
        "id": "TAMPINES_ST_34",
        "name": "Tampines Street 34",
        "address": "Tampines Street 34",
        "area": "Tampines",
        "latitude": 1.3598,
        "longitude": 103.9455,
        "nextAvailableTiming": "20 Mar, 10:00 - 20 Mar, 11:00",
    },
    {
        "id": "SMU",
        "name": "SMU Campus Green",
        "address": "81 Victoria Street",
        "area": "City",
        "latitude": 1.2966,
        "longitude": 103.8502,
        "nextAvailableTiming": "19 Mar, 17:00 - 19 Mar, 18:00",
    },
    {
        "id": "ORCHARD",
        "name": "Orchard Gateway",
        "address": "277 Orchard Road",
        "area": "Orchard",
        "latitude": 1.3008,
        "longitude": 103.8393,
        "nextAvailableTiming": "19 Mar, 20:00 - 19 Mar, 21:00",
    },
    {
        "id": "CHANGI",
        "name": "Changi Business Park",
        "address": "6 Changi Business Park Avenue 1",
        "area": "Changi",
        "latitude": 1.3333,
        "longitude": 103.9626,
        "nextAvailableTiming": "19 Mar, 18:30 - 19 Mar, 19:30",
    },
    {
        "id": "WOODLANDS",
        "name": "Woods Square",
        "address": "6 Woodlands Square",
        "area": "Woodlands",
        "latitude": 1.4369,
        "longitude": 103.7865,
        "nextAvailableTiming": "20 Mar, 09:00 - 20 Mar, 10:00",
    },
)

STATION_BY_ID = {station["id"]: station for station in STATION_CATALOG}


def get_station(zone: str) -> dict[str, Any]:
    station = STATION_BY_ID.get(zone)
    if station:
        return station
    return {
        "id": zone,
        "name": zone.replace("_", " ").title(),
        "address": zone.replace("_", " ").title(),
        "area": zone.replace("_", " ").title(),
        "latitude": 1.3521,
        "longitude": 103.8198,
        "nextAvailableTiming": "20 Mar, 09:00 - 20 Mar, 10:00",
    }


def resolve_location(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    normalized = _normalize(value)
    for station in STATION_CATALOG:
        aliases = {
            _normalize(station["id"]),
            _normalize(station["name"]),
            _normalize(station["address"]),
            _normalize(station["area"]),
        }
        if normalized in aliases:
            return station
    return None


def haversine_km(*, latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    radius_km = 6371.0
    delta_lat = radians(latitude_b - latitude_a)
    delta_lng = radians(longitude_b - longitude_a)
    lat_a = radians(latitude_a)
    lat_b = radians(latitude_b)
    inner = sin(delta_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(delta_lng / 2) ** 2
    return 2 * radius_km * asin(sqrt(inner))


def _normalize(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())
