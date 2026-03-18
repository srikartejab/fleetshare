from __future__ import annotations

from datetime import datetime

from fastapi import Query

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import check_availability

app = create_app("Search Available Vehicles Service", "Composite vehicle search workflow.")


@app.get("/search-vehicles/search")
def search_available_vehicles(
    userId: str = Query(...),
    startTime: datetime = Query(...),
    endTime: datetime = Query(...),
    pickupLocation: str = Query(...),
    vehicleType: str | None = None,
    subscriptionPlanId: str = "STANDARD_MONTHLY",
):
    settings = get_settings()
    vehicles = get_json(f"{settings.vehicle_service_url}/vehicles/availability", {"zone": pickupLocation})
    filtered = []
    for vehicle in vehicles:
        if vehicleType and vehicle["vehicleType"] != vehicleType:
            continue
        grpc_status = check_availability(vehicle["vehicleId"])
        if not grpc_status["available"]:
            continue
        availability = get_json(
            f"{settings.booking_service_url}/bookings/availability",
            {
                "vehicleId": vehicle["vehicleId"],
                "startTime": startTime.isoformat(),
                "endTime": endTime.isoformat(),
            },
        )
        if not availability["slotAvailable"]:
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
        filtered.append(
            {
                **vehicle,
                "estimatedPrice": quote["estimatedPrice"],
                "allowanceStatus": quote["allowanceStatus"],
                "hourlyRate": quote["hourlyRate"],
                "includedHoursApplied": quote["includedHoursApplied"],
                "includedHoursRemainingBefore": quote["includedHoursRemainingBefore"],
                "includedHoursRemainingAfter": quote["includedHoursRemainingAfter"],
                "billableHours": quote["billableHours"],
                "provisionalPostMidnightHours": quote["provisionalPostMidnightHours"],
                "provisionalCharge": quote["provisionalCharge"],
                "renewalDate": quote["renewalDate"],
            }
        )
    return {
        "vehicleList": filtered,
        "estimatedPrice": filtered[0]["estimatedPrice"] if filtered else 0.0,
        "availabilitySummary": f"{len(filtered)} vehicle(s) available",
    }
