from __future__ import annotations

import httpx
from fastapi import HTTPException, Response
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.settings import get_settings

app = create_app("Ops Console Service", "Public operations console composite service.")


class TelemetryPayload(BaseModel):
    vehicleId: int
    batteryLevel: int = 100
    tirePressureOk: bool = True
    severity: str = "INFO"
    faultCode: str = ""


class VehicleStatusPayload(BaseModel):
    status: str


class RenewalPayload(BaseModel):
    userId: str
    subscriptionPlanId: str = "STANDARD_MONTHLY"
    newBillingCycleId: str = "next"
    renewalStatus: str = "SUCCESS"


def _vehicle_key(vehicle: dict) -> int | None:
    value = vehicle.get("vehicleId", vehicle.get("id"))
    return int(value) if value is not None else None


def _booking_code(booking_id: int | None) -> str | None:
    if booking_id is None:
        return None
    return f"B-{str(booking_id).zfill(6)}"


def _vehicle_name(vehicle: dict | None, fallback_vehicle_id: int | None = None) -> str | None:
    if not vehicle:
        return f"Vehicle {fallback_vehicle_id}" if fallback_vehicle_id is not None else None
    return vehicle.get("model") or vehicle.get("plateNumber") or f"Vehicle {_vehicle_key(vehicle) or fallback_vehicle_id}"


def _raw_payload() -> dict:
    settings = get_settings()
    vehicles = get_json(f"{settings.vehicle_service_url}/vehicles")
    customers = get_json(f"{settings.pricing_service_url}/pricing/customers")
    bookings = get_json(f"{settings.booking_service_url}/bookings")
    trips = get_json(f"{settings.trip_service_url}/trips")
    tickets = get_json(f"{settings.maintenance_service_url}/maintenance/tickets")
    records = get_json(f"{settings.record_service_url}/records")
    review_queue = get_json(f"{settings.record_service_url}/records/manual-review-queue")
    payments = get_json(f"{settings.payment_service_url}/payments")
    notifications = get_json(f"{settings.notification_service_url}/notifications")
    return {
        "vehicles": vehicles if isinstance(vehicles, list) else [],
        "customers": customers if isinstance(customers, list) else [],
        "bookings": bookings if isinstance(bookings, list) else [],
        "trips": trips if isinstance(trips, list) else [],
        "tickets": tickets if isinstance(tickets, list) else [],
        "records": records if isinstance(records, list) else [],
        "reviewQueue": review_queue if isinstance(review_queue, list) else [],
        "payments": payments if isinstance(payments, list) else [],
        "notifications": notifications if isinstance(notifications, list) else [],
    }


def _indexes(payload: dict) -> dict:
    vehicle_by_id = {
        vehicle_id: vehicle
        for vehicle in payload["vehicles"]
        for vehicle_id in [_vehicle_key(vehicle)]
        if vehicle_id is not None
    }
    customer_by_user_id = {
        customer["userId"]: customer
        for customer in payload["customers"]
        if customer.get("userId")
    }
    booking_by_id = {
        booking["bookingId"]: booking
        for booking in payload["bookings"]
        if booking.get("bookingId") is not None
    }
    trip_by_id = {
        trip["tripId"]: trip
        for trip in payload["trips"]
        if trip.get("tripId") is not None
    }
    record_by_id = {
        record["recordId"]: record
        for record in payload["records"]
        if record.get("recordId") is not None
    }
    return {
        "vehicleById": vehicle_by_id,
        "customerByUserId": customer_by_user_id,
        "bookingById": booking_by_id,
        "tripById": trip_by_id,
        "recordById": record_by_id,
    }


def _enrich_booking(booking: dict, indexes: dict) -> dict:
    vehicle = indexes["vehicleById"].get(booking.get("vehicleId"))
    customer = indexes["customerByUserId"].get(booking.get("userId"))
    return {
        **booking,
        "bookingCode": _booking_code(booking.get("bookingId")),
        "customerName": customer.get("displayName") if customer else booking.get("userId"),
        "vehicleName": _vehicle_name(vehicle, booking.get("vehicleId")),
        "stationName": vehicle.get("stationName") if vehicle else None,
        "stationAddress": vehicle.get("stationAddress") if vehicle else None,
        "zone": vehicle.get("zone") if vehicle else None,
    }


def _enrich_record(record: dict, indexes: dict) -> dict:
    trip = indexes["tripById"].get(record.get("tripId")) if record.get("tripId") is not None else None
    booking = indexes["bookingById"].get(record.get("bookingId")) if record.get("bookingId") is not None else None
    if booking is None and trip is not None:
        booking = indexes["bookingById"].get(trip.get("bookingId"))
    vehicle = indexes["vehicleById"].get(record.get("vehicleId"))
    customer = indexes["customerByUserId"].get(booking.get("userId")) if booking else None
    return {
        **record,
        "bookingCode": _booking_code(booking.get("bookingId")) if booking else None,
        "userId": booking.get("userId") if booking else None,
        "customerName": customer.get("displayName") if customer else None,
        "vehicleName": _vehicle_name(vehicle, record.get("vehicleId")),
        "stationName": vehicle.get("stationName") if vehicle else None,
        "stationAddress": vehicle.get("stationAddress") if vehicle else None,
        "zone": vehicle.get("zone") if vehicle else None,
        "evidenceCount": len(record.get("evidenceUrls") or []),
        "hasEvidence": bool(record.get("evidenceUrls")),
    }


def _enrich_ticket(ticket: dict, indexes: dict) -> dict:
    trip = indexes["tripById"].get(ticket.get("tripId")) if ticket.get("tripId") is not None else None
    booking = indexes["bookingById"].get(ticket.get("bookingId")) if ticket.get("bookingId") is not None else None
    if booking is None and trip is not None:
        booking = indexes["bookingById"].get(trip.get("bookingId"))
    record = indexes["recordById"].get(ticket.get("recordId")) if ticket.get("recordId") is not None else None
    vehicle = indexes["vehicleById"].get(ticket.get("vehicleId"))
    customer = indexes["customerByUserId"].get(booking.get("userId")) if booking else None
    return {
        **ticket,
        "bookingCode": _booking_code(booking.get("bookingId")) if booking else None,
        "userId": booking.get("userId") if booking else None,
        "customerName": customer.get("displayName") if customer else None,
        "vehicleName": _vehicle_name(vehicle, ticket.get("vehicleId")),
        "stationName": vehicle.get("stationName") if vehicle else None,
        "stationAddress": vehicle.get("stationAddress") if vehicle else None,
        "zone": vehicle.get("zone") if vehicle else None,
        "recordSummary": record.get("notes") if record else None,
        "evidenceCount": len(record.get("evidenceUrls") or []) if record else 0,
        "hasEvidence": bool(record and record.get("evidenceUrls")),
    }


def _enrich_notification(notification: dict, indexes: dict) -> dict:
    trip = indexes["tripById"].get(notification.get("tripId")) if notification.get("tripId") is not None else None
    booking = indexes["bookingById"].get(notification.get("bookingId")) if notification.get("bookingId") is not None else None
    if booking is None and trip is not None:
        booking = indexes["bookingById"].get(trip.get("bookingId"))
    vehicle_id = booking.get("vehicleId") if booking else trip.get("vehicleId") if trip else None
    vehicle = indexes["vehicleById"].get(vehicle_id) if vehicle_id is not None else None
    customer = indexes["customerByUserId"].get(booking.get("userId")) if booking else None
    return {
        **notification,
        "bookingCode": _booking_code(booking.get("bookingId")) if booking else _booking_code(notification.get("bookingId")),
        "customerName": customer.get("displayName") if customer else None,
        "vehicleId": vehicle_id,
        "vehicleName": _vehicle_name(vehicle, vehicle_id) if vehicle_id is not None else None,
        "stationName": vehicle.get("stationName") if vehicle else None,
        "stationAddress": vehicle.get("stationAddress") if vehicle else None,
        "zone": vehicle.get("zone") if vehicle else None,
        "severity": notification.get("payload", {}).get("severity"),
    }


def _ticket_evidence_links(ticket_id: int, record: dict | None) -> list[str]:
    evidence_urls = (record or {}).get("evidenceUrls") or []
    return [f"/ops-console/tickets/{ticket_id}/evidence/{index}" for index in range(len(evidence_urls))]


def _enriched_payload() -> dict:
    payload = _raw_payload()
    indexes = _indexes(payload)
    return {
        "vehicles": payload["vehicles"],
        "customers": payload["customers"],
        "bookings": [_enrich_booking(booking, indexes) for booking in payload["bookings"]],
        "trips": payload["trips"],
        "tickets": [_enrich_ticket(ticket, indexes) for ticket in payload["tickets"]],
        "records": [_enrich_record(record, indexes) for record in payload["records"]],
        "reviewQueue": [_enrich_record(record, indexes) for record in payload["reviewQueue"]],
        "payments": payload["payments"],
        "notifications": [_enrich_notification(notification, indexes) for notification in payload["notifications"]],
    }


@app.get("/ops-console/dashboard")
def get_dashboard():
    return _enriched_payload()


@app.get("/ops-console/incidents")
def get_incidents():
    payload = _enriched_payload()
    return {
        "tickets": payload["tickets"],
        "records": payload["records"],
        "reviewQueue": payload["reviewQueue"],
    }


@app.get("/ops-console/billing")
def get_billing():
    payload = _enriched_payload()
    return {
        "customers": payload["customers"],
        "bookings": payload["bookings"],
        "trips": payload["trips"],
        "payments": payload["payments"],
    }


@app.get("/ops-console/inbox")
def get_inbox():
    payload = _enriched_payload()
    return {"notifications": payload["notifications"]}


@app.get("/ops-console/tickets/{ticket_id}")
def get_ticket_detail(ticket_id: int):
    settings = get_settings()
    payload = _raw_payload()
    indexes = _indexes(payload)
    ticket = get_json(f"{settings.maintenance_service_url}/maintenance/tickets/{ticket_id}")
    enriched_ticket = _enrich_ticket(ticket, indexes)
    trip = indexes["tripById"].get(ticket.get("tripId")) if ticket.get("tripId") is not None else None
    booking = indexes["bookingById"].get(ticket.get("bookingId")) if ticket.get("bookingId") is not None else None
    if booking is None and trip is not None:
        booking = indexes["bookingById"].get(trip.get("bookingId"))
    record = indexes["recordById"].get(ticket.get("recordId")) if ticket.get("recordId") is not None else None
    enriched_record = _enrich_record(record, indexes) if record else None
    vehicle = indexes["vehicleById"].get(ticket.get("vehicleId"))
    customer = indexes["customerByUserId"].get(booking.get("userId")) if booking else None
    return {
        "ticket": enriched_ticket,
        "vehicle": vehicle,
        "customer": customer,
        "booking": _enrich_booking(booking, indexes) if booking else None,
        "trip": trip,
        "record": enriched_record,
        "evidenceUrls": _ticket_evidence_links(ticket_id, record),
    }


@app.get("/ops-console/tickets/{ticket_id}/evidence/{index}")
def get_ticket_evidence(ticket_id: int, index: int):
    settings = get_settings()
    payload = _raw_payload()
    indexes = _indexes(payload)
    ticket = get_json(f"{settings.maintenance_service_url}/maintenance/tickets/{ticket_id}")
    record_id = ticket.get("recordId")
    if record_id is None:
        raise HTTPException(status_code=404, detail="No inspection record was linked to this ticket.")
    record = indexes["recordById"].get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection record not found for this ticket.")

    evidence_urls = record.get("evidenceUrls") or []
    if index < 0 or index >= len(evidence_urls):
        raise HTTPException(status_code=404, detail="Evidence item not found")

    response = httpx.get(f"{settings.record_service_url}/records/{record_id}/evidence/{index}", timeout=20.0)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc

    headers = {"Cache-Control": "no-store"}
    content_disposition = response.headers.get("content-disposition")
    if content_disposition:
        headers["Content-Disposition"] = content_disposition
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "application/octet-stream"),
        headers=headers,
    )


@app.post("/ops-console/fleet/telemetry")
def create_telemetry(payload: TelemetryPayload):
    settings = get_settings()
    return post_json(
        f"{settings.vehicle_service_url}/vehicles/telemetry",
        payload.model_dump(mode="json"),
    )


@app.patch("/ops-console/fleet/{vehicle_id}/status")
def update_vehicle_status(vehicle_id: int, payload: VehicleStatusPayload):
    settings = get_settings()
    return patch_json(
        f"{settings.vehicle_service_url}/vehicles/{vehicle_id}/status",
        payload.model_dump(mode="json"),
    )


@app.post("/ops-console/renewal/simulate")
def simulate_renewal(payload: RenewalPayload):
    settings = get_settings()
    return post_json(
        f"{settings.renewal_reconciliation_service_url}/renewal-reconciliation/simulate",
        payload.model_dump(mode="json"),
    )
