from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest


RUN_E2E = os.getenv("RUN_E2E") == "1"
BASE_URL = os.getenv("FLEETSHARE_BASE_URL", "http://localhost:8000")

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not RUN_E2E, reason="Set RUN_E2E=1 to run end-to-end scenario tests."),
]


def log(message: str):
    print(f"[fleetshare-e2e] {message}")


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    expected_status: int = 200,
    **kwargs,
):
    response = client.request(method, path, **kwargs)
    if response.status_code != expected_status:
        raise AssertionError(f"{method} {path} -> {response.status_code}: {response.text}")
    if not response.content:
        return {}
    return response.json()


def poll_until(description: str, predicate, *, timeout: float = 40.0, interval: float = 1.0):
    deadline = time.time() + timeout
    last_value = None
    while time.time() < deadline:
        last_value = predicate()
        if last_value:
            log(f"{description}: OK")
            return last_value
        time.sleep(interval)
    raise AssertionError(f"Timed out waiting for {description}. Last value: {last_value}")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as session:
        request_json(session, "GET", "/vehicles")
        yield session


def reserve_and_confirm(
    client: httpx.Client,
    *,
    user_id: str,
    pickup_location: str,
    vehicle_type: str,
    start_time: datetime,
    end_time: datetime,
):
    search = request_json(
        client,
        "GET",
        "/process-booking/search",
        params={
            "userId": user_id,
            "pickupLocation": pickup_location,
            "vehicleType": vehicle_type,
            "startTime": iso_utc(start_time),
            "endTime": iso_utc(end_time),
            "subscriptionPlanId": "STANDARD_MONTHLY",
        },
    )
    assert search["vehicleList"], f"No vehicles found for {user_id}"
    vehicle = search["vehicleList"][0]
    log(f"search completed for {user_id}; vehicle selected {vehicle['vehicleId']} in {pickup_location}")

    reserve = request_json(
        client,
        "POST",
        "/process-booking/reserve",
        json={
            "userId": user_id,
            "vehicleId": vehicle["vehicleId"],
            "pickupLocation": pickup_location,
            "startTime": iso_utc(start_time),
            "endTime": iso_utc(end_time),
            "displayedPrice": vehicle["estimatedPrice"],
            "subscriptionPlanId": "STANDARD_MONTHLY",
        },
    )
    assert reserve["status"] == "PAYMENT_PENDING"
    log(f"booking created in PAYMENT_PENDING; booking id {reserve['bookingId']}")

    payment = request_json(
        client,
        "POST",
        "/process-booking/pay",
        json={
            "bookingId": reserve["bookingId"],
            "userId": user_id,
        },
    )
    assert payment["status"] == "CONFIRMED"
    log(f"booking confirmed; booking id {reserve['bookingId']}, payment id {payment['paymentId']}")

    booking = request_json(client, "GET", f"/booking/{reserve['bookingId']}")
    return reserve, booking, vehicle


def submit_minor_inspection(client: httpx.Client, *, booking_id: int, vehicle_id: int, user_id: str):
    inspection = request_json(
        client,
        "POST",
        "/damage-assessment/external",
        data={
            "bookingId": str(booking_id),
            "vehicleId": str(vehicle_id),
            "userId": user_id,
            "notes": "light scratch on door",
        },
        files={"photos": ("inspection.jpg", b"fake-image-data", "image/jpeg")},
    )
    assert inspection["tripStatus"] == "CLEARED"
    log(f"external inspection cleared; record id {inspection['recordId']}")
    return inspection


def test_scenario_1_booking_trip_and_renewal_reconciliation(client: httpx.Client):
    user_id = "user-1001"
    summary = request_json(client, "GET", f"/pricing/customers/{user_id}/summary")
    renewal_date = datetime.fromisoformat(summary["renewalDate"]).replace(tzinfo=UTC)
    start_time = renewal_date.replace(hour=23, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=3)

    reserve, booking, vehicle = reserve_and_confirm(
        client,
        user_id=user_id,
        pickup_location="SMU",
        vehicle_type="SEDAN",
        start_time=start_time,
        end_time=end_time,
    )
    assert booking["refundPendingOnRenewal"] is True
    submit_minor_inspection(client, booking_id=reserve["bookingId"], vehicle_id=vehicle["vehicleId"], user_id=user_id)
    trips_before_start = request_json(client, "GET", "/trips", params={"userId": user_id})
    assert trips_before_start == []
    log("inspection cleared; no trip created before unlock/start, as expected")

    started = request_json(
        client,
        "POST",
        "/trips/start",
        json={"bookingId": reserve["bookingId"], "vehicleId": vehicle["vehicleId"], "userId": user_id, "notes": ""},
    )
    log(f"unlock command accepted and trip started; trip id {started['tripId']}")

    ended = request_json(
        client,
        "POST",
        "/end-trip/request",
        json={
            "tripId": started["tripId"],
            "bookingId": reserve["bookingId"],
            "vehicleId": vehicle["vehicleId"],
            "userId": user_id,
            "endReason": "USER_COMPLETED",
        },
    )
    assert ended["tripStatus"] == "ENDED"
    log(f"trip ended; final fare {ended['adjustedFare']}")

    next_billing_cycle_id = booking["pricingSnapshot"]["nextBillingCycleId"]
    request_json(
        client,
        "POST",
        "/renewal-reconciliation/simulate",
        json={"userId": user_id, "newBillingCycleId": next_billing_cycle_id},
    )
    log(f"renewal event published for {user_id}; target cycle {next_billing_cycle_id}")

    reconciled_booking = poll_until(
        "booking reconciliation completed",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/bookings", params={"userId": user_id})
                if item["bookingId"] == reserve["bookingId"] and item["status"] == "RECONCILED"
            ),
            None,
        ),
    )
    assert reconciled_booking["reconciliationStatus"] == "COMPLETED"
    log(f"booking reconciled; booking id {reconciled_booking['bookingId']}")

    refund = poll_until(
        "renewal refund recorded",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/payments", params={"userId": user_id})
                if item["status"] == "REFUNDED" and item["bookingId"] == reserve["bookingId"]
            ),
            None,
        ),
    )
    log(f"refund created; payment id {refund['paymentId']} amount {refund['amount']}")

    customer_notification = poll_until(
        "customer adjustment notification delivered",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/notifications", params={"userId": user_id})
                if item["bookingId"] == reserve["bookingId"] and "Billing adjustment completed" in item["subject"]
            ),
            None,
        ),
    )
    log(f"customer notified about billing adjustment; notification id {customer_notification['notificationId']}")


def test_scenario_2_external_damage_recovery_flow(client: httpx.Client):
    user_id = "user-1002"
    start_time = datetime.now(UTC) + timedelta(hours=8)
    end_time = start_time + timedelta(hours=2)

    reserve, booking, vehicle = reserve_and_confirm(
        client,
        user_id=user_id,
        pickup_location="CHANGI",
        vehicle_type="SUV",
        start_time=start_time,
        end_time=end_time,
    )

    inspection = request_json(
        client,
        "POST",
        "/damage-assessment/external",
        data={
            "bookingId": str(reserve["bookingId"]),
            "vehicleId": str(vehicle["vehicleId"]),
            "userId": user_id,
            "notes": "dent on bumper and broken light",
        },
        files={"photos": ("damage.jpg", b"fake-image-data", "image/jpeg")},
    )
    assert inspection["tripStatus"] == "BLOCKED"
    log(f"severe external damage detected; record id {inspection['recordId']}")

    cancelled_booking = poll_until(
        "affected booking cancelled after external damage",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/bookings", params={"userId": user_id})
                if item["bookingId"] == reserve["bookingId"] and item["status"] == "CANCELLED"
            ),
            None,
        ),
    )
    log(f"booking cancelled; booking id {cancelled_booking['bookingId']}")

    ticket = poll_until(
        "maintenance ticket created after external damage",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/maintenance/tickets")
                if item["vehicleId"] == vehicle["vehicleId"]
            ),
            None,
        ),
    )
    log(f"maintenance ticket created; ticket id {ticket['ticketId']}")

    payment = poll_until(
        "customer compensation recorded after external damage",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/payments", params={"userId": user_id})
                if item["bookingId"] == reserve["bookingId"] and item["status"] == "ADJUSTED"
            ),
            None,
        ),
    )
    log(f"payment adjustment created; payment id {payment['paymentId']} amount {payment['amount']}")

    customer_notification = poll_until(
        "customer notified after external damage",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/notifications", params={"userId": user_id})
                if item["bookingId"] == reserve["bookingId"] and "cancelled" in item["message"].lower()
            ),
            None,
        ),
    )
    log(f"customer notified; notification id {customer_notification['notificationId']}")

    ops_notification = poll_until(
        "ops notified after external damage",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/notifications", params={"userId": "ops-maint-1"})
                if item["bookingId"] == booking["bookingId"]
            ),
            None,
        ),
    )
    log(f"ops notified; notification id {ops_notification['notificationId']}")


def test_scenario_3_telemetry_fault_recovery_flow(client: httpx.Client):
    user_id = "user-1003"
    start_time = datetime.now(UTC) + timedelta(hours=14)
    end_time = start_time + timedelta(hours=3)

    reserve, booking, vehicle = reserve_and_confirm(
        client,
        user_id=user_id,
        pickup_location="TAMPINES",
        vehicle_type="SEDAN",
        start_time=start_time,
        end_time=end_time,
    )
    submit_minor_inspection(client, booking_id=reserve["bookingId"], vehicle_id=vehicle["vehicleId"], user_id=user_id)

    request_json(
        client,
        "POST",
        "/vehicles/telemetry",
        json={
            "vehicleId": vehicle["vehicleId"],
            "batteryLevel": 12,
            "tirePressureOk": True,
            "severity": "CRITICAL",
            "faultCode": "LOW_BATTERY",
        },
    )
    log(f"telemetry injected; vehicle id {vehicle['vehicleId']}")

    blocked = client.post(
        "/trips/start",
        json={"bookingId": reserve["bookingId"], "vehicleId": vehicle["vehicleId"], "userId": user_id, "notes": "battery warning"},
    )
    assert blocked.status_code == 409, blocked.text
    log(f"trip start blocked as expected; response {blocked.text}")

    ticket = poll_until(
        "maintenance ticket created after telemetry fault",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/maintenance/tickets")
                if item["vehicleId"] == vehicle["vehicleId"]
            ),
            None,
        ),
    )
    log(f"maintenance ticket created; ticket id {ticket['ticketId']}")

    cancelled_booking = poll_until(
        "booking cancelled after telemetry fault",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/bookings", params={"userId": user_id})
                if item["bookingId"] == reserve["bookingId"] and item["status"] == "CANCELLED"
            ),
            None,
        ),
    )
    log(f"booking cancelled after telemetry fault; booking id {cancelled_booking['bookingId']}")

    payment = poll_until(
        "compensation recorded after telemetry fault",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/payments", params={"userId": user_id})
                if item["bookingId"] == reserve["bookingId"] and item["status"] == "ADJUSTED"
            ),
            None,
        ),
    )
    log(f"payment adjustment created; payment id {payment['paymentId']} amount {payment['amount']}")

    customer_notification = poll_until(
        "customer notified after telemetry fault",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/notifications", params={"userId": user_id})
                if item["bookingId"] == reserve["bookingId"] and "cancelled" in item["message"].lower()
            ),
            None,
        ),
    )
    log(f"customer notified after telemetry fault; notification id {customer_notification['notificationId']}")

    ops_notification = poll_until(
        "ops notified after telemetry fault",
        lambda: next(
            (
                item
                for item in request_json(client, "GET", "/notifications", params={"userId": "ops-maint-1"})
                if item["bookingId"] == booking["bookingId"]
            ),
            None,
        ),
    )
    log(f"ops notified after telemetry fault; notification id {ops_notification['notificationId']}")
