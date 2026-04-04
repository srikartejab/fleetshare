from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta, timezone

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
        request_json(session, "GET", "/process-booking/customer-profiles")
        yield session


def customer_home(client: httpx.Client, user_id: str) -> dict:
    return request_json(client, "GET", f"/process-booking/customers/{user_id}/home")


def customer_bookings(client: httpx.Client, user_id: str) -> list[dict]:
    return request_json(client, "GET", f"/process-booking/customers/{user_id}/bookings")["bookings"]


def customer_wallet(client: httpx.Client, user_id: str) -> dict:
    return request_json(client, "GET", f"/process-booking/customers/{user_id}/wallet")


def customer_account(client: httpx.Client, user_id: str) -> dict:
    return request_json(client, "GET", f"/process-booking/customers/{user_id}/account")


def trip_status(client: httpx.Client, user_id: str) -> dict:
    return request_json(client, "GET", f"/trip-experience/customers/{user_id}/status")


def ops_incidents(client: httpx.Client) -> dict:
    return request_json(client, "GET", "/ops-console/incidents")


def ops_inbox(client: httpx.Client) -> dict:
    return request_json(client, "GET", "/ops-console/inbox")


def reserve_and_confirm(
    client: httpx.Client,
    *,
    user_id: str,
    pickup_location: str,
    vehicle_type: str,
    start_time: datetime,
    end_time: datetime,
    preferred_vehicle_id: int | None = None,
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
    vehicle = next(
        (item for item in search["vehicleList"] if preferred_vehicle_id is not None and item["vehicleId"] == preferred_vehicle_id),
        search["vehicleList"][0],
    )
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

    booking_detail = request_json(client, "GET", f"/process-booking/bookings/{reserve['bookingId']}")
    return reserve, booking_detail["booking"], vehicle


def submit_minor_inspection(client: httpx.Client, *, booking_id: int, vehicle_id: int, user_id: str):
    inspection = request_json(
        client,
        "POST",
        "/trip-experience/pre-trip-inspection",
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
    summary = customer_home(client, user_id)["customerSummary"]
    singapore = timezone(timedelta(hours=8))
    renewal_date = datetime.fromisoformat(summary["renewalDate"]).replace(tzinfo=singapore)
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
    trips_before_start = trip_status(client, user_id)["trips"]
    assert trips_before_start == []
    log("inspection cleared; no trip created before unlock/start, as expected")

    started = request_json(
        client,
        "POST",
        "/trip-experience/start",
        json={"bookingId": reserve["bookingId"], "vehicleId": vehicle["vehicleId"], "userId": user_id, "notes": ""},
    )
    log(f"unlock command accepted and trip started; trip id {started['tripId']}")

    ended = request_json(
        client,
        "POST",
        "/trip-experience/end",
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
        "/ops-console/renewal/simulate",
        json={"userId": user_id, "newBillingCycleId": next_billing_cycle_id},
    )
    log(f"renewal event published for {user_id}; target cycle {next_billing_cycle_id}")

    reconciled_booking = poll_until(
        "booking reconciliation completed",
        lambda: next(
            (
                item
                for item in customer_bookings(client, user_id)
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
                for item in customer_wallet(client, user_id)["payments"]
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
                for item in customer_account(client, user_id)["notifications"]
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
        "/trip-experience/pre-trip-inspection",
        data={
            "bookingId": str(reserve["bookingId"]),
            "vehicleId": str(vehicle["vehicleId"]),
            "userId": user_id,
            "notes": "dent on bumper and broken light",
        },
        files={"photos": ("damage.jpg", b"fake-image-data", "image/jpeg")},
    )
    assert inspection["tripStatus"] == "BLOCKED"
    assert inspection["bookingCancelled"] is True
    assert inspection["bookingStatus"] == "CANCELLED"
    assert inspection["resolutionCompleted"] is True
    log(f"severe external damage detected; record id {inspection['recordId']}")

    cancelled_booking = next(
        (
            item
            for item in customer_bookings(client, user_id)
            if item["bookingId"] == reserve["bookingId"] and item["status"] == "CANCELLED"
        ),
        None,
    )
    assert cancelled_booking is not None
    log(f"booking cancelled; booking id {cancelled_booking['bookingId']}")

    ticket = poll_until(
        "maintenance ticket created after external damage",
        lambda: next(
            (
                item
                for item in ops_incidents(client)["tickets"]
                if item["vehicleId"] == vehicle["vehicleId"]
            ),
            None,
        ),
    )
    log(f"maintenance ticket created; ticket id {ticket['ticketId']}")

    refund = poll_until(
        "customer refund recorded after external damage",
        lambda: next(
            (
                item
                for item in customer_wallet(client, user_id)["payments"]
                if item["bookingId"] == reserve["bookingId"] and item["status"] == "REFUNDED"
            ),
            None,
        ),
    )
    log(f"refund created; payment id {refund['paymentId']} amount {refund['amount']}")

    credit = poll_until(
        "customer apology credit recorded after external damage",
        lambda: next(
            (
                item
                for item in customer_wallet(client, user_id)["payments"]
                if item["bookingId"] == reserve["bookingId"] and item["status"] == "ADJUSTED"
            ),
            None,
        ),
    )
    log(f"apology credit created; payment id {credit['paymentId']} amount {credit['amount']}")

    restored_hours = poll_until(
        "allowance restoration recorded after external damage",
        lambda: next(
            (
                item
                for item in customer_wallet(client, user_id)["ledgerEntries"]
                if item["bookingId"] == reserve["bookingId"] and item["restoredIncludedHours"] > 0
            ),
            None,
        ),
    )
    log(f"allowance restoration recorded; ledger id {restored_hours['ledgerId']} restored {restored_hours['restoredIncludedHours']}h")

    customer_notification = poll_until(
        "customer notified after external damage",
        lambda: next(
            (
                item
                for item in customer_account(client, user_id)["notifications"]
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
                for item in ops_inbox(client)["notifications"]
                if item["userId"] == "ops-maint-1" and item["bookingId"] == booking["bookingId"]
            ),
            None,
        ),
    )
    log(f"ops notified; notification id {ops_notification['notificationId']}")


def test_scenario_3_telemetry_fault_recovery_flow(client: httpx.Client):
    active_user_id = "user-1003"
    impacted_user_id = "user-1001"
    start_time = datetime.now(UTC) + timedelta(hours=14)
    end_time = start_time + timedelta(hours=3)

    reserve, booking, vehicle = reserve_and_confirm(
        client,
        user_id=active_user_id,
        pickup_location="TAMPINES",
        vehicle_type="SEDAN",
        start_time=start_time,
        end_time=end_time,
    )
    submit_minor_inspection(client, booking_id=reserve["bookingId"], vehicle_id=vehicle["vehicleId"], user_id=active_user_id)

    started = request_json(
        client,
        "POST",
        "/trip-experience/start",
        json={"bookingId": reserve["bookingId"], "vehicleId": vehicle["vehicleId"], "userId": active_user_id, "notes": "start trip"},
    )
    log(f"active trip started; trip id {started['tripId']}")

    impacted_start = end_time + timedelta(hours=2)
    impacted_end = impacted_start + timedelta(hours=2)
    impacted_reserve, _, _ = reserve_and_confirm(
        client,
        user_id=impacted_user_id,
        pickup_location="TAMPINES",
        vehicle_type="SEDAN",
        start_time=impacted_start,
        end_time=impacted_end,
        preferred_vehicle_id=vehicle["vehicleId"],
    )
    assert impacted_reserve["vehicleId"] == vehicle["vehicleId"]
    log(f"future booking confirmed on same vehicle; booking id {impacted_reserve['bookingId']}")

    request_json(
        client,
        "POST",
        "/ops-console/fleet/telemetry",
        json={
            "vehicleId": vehicle["vehicleId"],
            "batteryLevel": 12,
            "tirePressureOk": True,
            "severity": "CRITICAL",
            "faultCode": "LOW_BATTERY",
        },
    )
    log(f"telemetry injected; vehicle id {vehicle['vehicleId']}")

    ticket = poll_until(
        "maintenance ticket created after telemetry fault",
        lambda: next(
            (
                item
                for item in ops_incidents(client)["tickets"]
                if item["vehicleId"] == vehicle["vehicleId"]
            ),
            None,
        ),
    )
    log(f"maintenance ticket created; ticket id {ticket['ticketId']}")

    live_trip_advisory = poll_until(
        "active customer disruption advisory delivered",
        lambda: trip_status(client, active_user_id).get("liveTripAdvisory"),
    )
    assert live_trip_advisory["tripId"] == started["tripId"]
    assert live_trip_advisory["requiresImmediateEndTrip"] is True
    log(f"live trip advisory delivered; notification id {live_trip_advisory['notificationId']}")

    active_trip = poll_until(
        "active trip remains in progress after telemetry fault",
        lambda: next(
            (
                item
                for item in trip_status(client, active_user_id)["trips"]
                if item["tripId"] == started["tripId"] and item["status"] == "STARTED"
            ),
            None,
        ),
    )
    log(f"active trip still running; trip id {active_trip['tripId']}")

    cancelled_booking = poll_until(
        "future booking cancelled after telemetry fault",
        lambda: next(
            (
                item
                for item in customer_bookings(client, impacted_user_id)
                if item["bookingId"] == impacted_reserve["bookingId"] and item["status"] == "CANCELLED"
            ),
            None,
        ),
    )
    log(f"future booking cancelled after telemetry fault; booking id {cancelled_booking['bookingId']}")

    refund = poll_until(
        "refund recorded after telemetry fault",
        lambda: next(
            (
                item
                for item in customer_wallet(client, impacted_user_id)["payments"]
                if item["bookingId"] == impacted_reserve["bookingId"] and item["status"] == "REFUNDED"
            ),
            None,
        ),
    )
    log(f"refund created after telemetry fault; payment id {refund['paymentId']} amount {refund['amount']}")

    credit = poll_until(
        "apology credit recorded after telemetry fault",
        lambda: next(
            (
                item
                for item in customer_wallet(client, impacted_user_id)["payments"]
                if item["bookingId"] == impacted_reserve["bookingId"] and item["status"] == "ADJUSTED"
            ),
            None,
        ),
    )
    log(f"apology credit created after telemetry fault; payment id {credit['paymentId']} amount {credit['amount']}")

    customer_notification = poll_until(
        "customer notified after telemetry fault",
        lambda: next(
            (
                item
                for item in customer_account(client, impacted_user_id)["notifications"]
                if item["bookingId"] == impacted_reserve["bookingId"] and "cancelled" in item["message"].lower()
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
                for item in ops_inbox(client)["notifications"]
                if item["userId"] == "ops-maint-1" and item["bookingId"] == booking["bookingId"]
            ),
            None,
        ),
    )
    log(f"ops notified after telemetry fault; notification id {ops_notification['notificationId']}")
