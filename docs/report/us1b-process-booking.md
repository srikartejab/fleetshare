# US1B Process Booking

## Scope / Boundary

This diagram covers the successful reserve-and-pay booking path.

It includes:

- UI entry through Kong
- `Process Booking Service` orchestration
- operational availability re-check
- booking-slot re-check
- final quote retrieval
- booking creation in `PAYMENT_PENDING`
- payment submission
- booking confirmation after successful payment

It does not include:

- renewal reconciliation after subscription rollover
- payment refund or adjustment consumers
- trip start

## Textual Flow

# US1B Process Booking

## Scope / Boundary

This diagram covers the successful reserve-and-pay booking path.

It includes:

- UI entry through Kong
- `Process Booking Service` orchestration
- booking window validation
- explicit vehicle existence lookup
- operational eligibility re-check through gRPC
- booking-slot overlap re-check
- final quote retrieval
- booking creation in `PAYMENT_PENDING`
- synchronous payment submission
- booking confirmation after successful payment

It does not include:

- renewal reconciliation after subscription rollover
- refund and payment-adjustment consumers
- trip start

## Textual Flow

1. After the customer selects a vehicle, the FleetShare UI submits the reserve request to `POST /process-booking/reserve` through Kong.
2. Kong routes the reserve request to `Process Booking Service`.
3. `Process Booking Service` validates that `endTime` is later than `startTime`.
4. `Process Booking Service` loads the selected vehicle from `Vehicle Service` at `GET /vehicles/{vehicleId}` to confirm that the vehicle exists.
5. `Process Booking Service` checks operational eligibility again through the vehicle gRPC adapter. This verifies that the vehicle is not operationally blocked, such as for maintenance or inspection.
6. `Process Booking Service` calls `Booking Service` at `GET /bookings/availability` to verify that the requested time slot is still free for that vehicle.
7. `Process Booking Service` requests the latest quote from `Pricing Service` at `GET /pricing/quote`.
8. `Process Booking Service` creates the booking through `Booking Service` at `POST /booking`, storing the refreshed pricing snapshot and creating the booking with status `PAYMENT_PENDING`. If the quote indicates a cross-cycle booking, it also sets `refundPendingOnRenewal=true`.
9. `Process Booking Service` returns the provisional booking result to Kong with `bookingId`, `status=PAYMENT_PENDING`, `paymentStatus=REQUIRED`, the refreshed pricing payload, and the updated customer summary.
10. Kong returns the reserve result to the UI so that the customer can proceed to payment.
11. The UI then submits the payment request to `POST /process-booking/pay` through Kong.
12. Kong routes the payment request to `Process Booking Service`.
13. `Process Booking Service` loads the booking from `Booking Service` at `GET /booking/{bookingId}` and determines the amount to charge from the explicit payment request or the booking’s stored `displayedPrice`.
14. `Process Booking Service` submits the payment to `Payment Service` at `POST /payments`.
15. On the implemented successful path, `Process Booking Service` immediately processes the returned payment result through its internal `payment_result(...)` handler and patches the booking through `Booking Service` at `PATCH /booking/{bookingId}/status` with `status=CONFIRMED`.
16. `Process Booking Service` returns the final payment result to Kong with `bookingId`, `paymentId`, echoed `paymentMethod`, `status=CONFIRMED`, and `paymentStatus=SUCCESS`.
17. Kong returns the confirmed booking response to the UI.
