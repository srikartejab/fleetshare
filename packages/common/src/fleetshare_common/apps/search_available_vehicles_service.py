from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException, Query

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json
from fleetshare_common.settings import get_settings
from fleetshare_common.station_catalog import get_station, haversine_km, resolve_location
from fleetshare_common.vehicle_grpc import check_availability

app = create_app("Search Available Vehicles Service", "Composite vehicle search workflow.")


def validate_booking_window(start_time: datetime, end_time: datetime) -> None:
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="endTime must be later than startTime")


@app.get("/search-vehicles/search")
def search_available_vehicles(
    userId: str = Query(...),
    startTime: datetime = Query(...),
    endTime: datetime = Query(...),
    pickupLocation: str = Query(...),
    vehicleType: str | None = None,
    subscriptionPlanId: str = "STANDARD_MONTHLY",
):
    validate_booking_window(startTime, endTime)
    settings = get_settings()
    stations = get_json(f"{settings.vehicle_service_url}/vehicles/stations")
    vehicles = get_json(f"{settings.vehicle_service_url}/vehicles/availability")
    requested_station = resolve_location(pickupLocation)
    selected_station_id = requested_station["id"] if requested_station else (stations[0]["stationId"] if stations else pickupLocation)
    selected_station = next((station for station in stations if station["stationId"] == selected_station_id), None) or get_station(selected_station_id)

    operational_candidates = []
    for vehicle in vehicles:
        if vehicleType and vehicle["vehicleType"] != vehicleType:
            continue
        grpc_status = check_availability(vehicle["vehicleId"])
        if not grpc_status["available"]:
            continue
        operational_candidates.append(vehicle)

    availability_lookup = {"availableVehicleIds": []}
    if operational_candidates:
        availability_lookup = get_json(
            f"{settings.booking_service_url}/bookings/availability",
            {
                "vehicleIds": ",".join(str(vehicle["vehicleId"]) for vehicle in operational_candidates),
                "startTime": startTime.isoformat(),
                "endTime": endTime.isoformat(),
            },
        )

    available_vehicle_ids = set(availability_lookup.get("availableVehicleIds", []))
    filtered = []
    for vehicle in operational_candidates:
        if vehicle["vehicleId"] not in available_vehicle_ids:
            continue
        quote = get_json(
            f"{settings.pricing_service_url}/pricing/quote",
            {
                "userId": userId,
                "vehicleId": vehicle["vehicleId"],
                "startTime": startTime.isoformat(),
                "endTime": endTime.isoformat(),
                "subscriptionPlanId": subscriptionPlanId,
            },
        )
        distance_km = haversine_km(
            latitude_a=selected_station["latitude"],
            longitude_a=selected_station["longitude"],
            latitude_b=vehicle["latitude"],
            longitude_b=vehicle["longitude"],
        )
        filtered.append(
            {
                **vehicle,
                "distanceKm": round(distance_km, 2),
                "estimatedPrice": quote["estimatedPrice"],
                "allowanceStatus": quote["allowanceStatus"],
                "crossCycleBooking": quote["crossCycleBooking"],
                "hourlyRate": quote["hourlyRate"],
                "totalHours": quote["totalHours"],
                "currentCycleHours": quote["currentCycleHours"],
                "includedHoursApplied": quote["includedHoursApplied"],
                "includedHoursRemainingBefore": quote["includedHoursRemainingBefore"],
                "includedHoursRemainingAfter": quote["includedHoursRemainingAfter"],
                "billableHours": quote["billableHours"],
                "provisionalPostMidnightHours": quote["provisionalPostMidnightHours"],
                "provisionalCharge": quote["provisionalCharge"],
                "renewalDate": quote["renewalDate"],
            }
        )

    filtered.sort(
        key=lambda vehicle: (
            0 if vehicle["stationId"] == selected_station_id else 1,
            vehicle["distanceKm"],
            vehicle["estimatedPrice"],
            vehicle["vehicleId"],
        )
    )

    station_buckets: dict[str, dict] = {}
    vehicle_groups: dict[str, list[dict]] = defaultdict(list)
    for vehicle in filtered:
        vehicle_groups[vehicle["stationId"]].append(vehicle)

    for station in stations:
        station_id = station["stationId"]
        grouped_vehicles = vehicle_groups.get(station_id, [])
        distance_km = haversine_km(
            latitude_a=selected_station["latitude"],
            longitude_a=selected_station["longitude"],
            latitude_b=station["latitude"],
            longitude_b=station["longitude"],
        )
        station_buckets[station_id] = {
            **station,
            "distanceKm": round(distance_km, 2),
            "availableVehicleCount": len(grouped_vehicles),
            "availableVehicleTypes": sorted({vehicle["vehicleType"] for vehicle in grouped_vehicles}),
            "minEstimatedPrice": min((vehicle["estimatedPrice"] for vehicle in grouped_vehicles), default=None),
            "vehicleList": grouped_vehicles,
            "featuredVehicle": grouped_vehicles[0] if grouped_vehicles else None,
        }

    station_list = sorted(
        station_buckets.values(),
        key=lambda station: (
            0 if station["stationId"] == selected_station_id else 1,
            0 if station["availableVehicleCount"] > 0 else 1,
            station["distanceKm"],
            station["stationName"],
        ),
    )

    return {
        "vehicleList": filtered,
        "estimatedPrice": filtered[0]["estimatedPrice"] if filtered else 0.0,
        "availabilitySummary": f"{len(filtered)} vehicle(s) available",
        "selectedStationId": selected_station_id,
        "mapCenter": {
            "latitude": selected_station["latitude"],
            "longitude": selected_station["longitude"],
        },
        "stationList": station_list,
    }
