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

1. After the customer selects a vehicle, the FleetShare UI submits the reserve request to `POST /process-booking/reserve` through Kong.
2. Kong routes the request to `Process Booking Service`.
3. `Process Booking Service` validates that the requested end time is later than the start time.
4. `Process Booking Service` checks operational readiness again through the vehicle gRPC adapter to confirm that the vehicle is still available to be reserved.
5. `Process Booking Service` calls `Booking Service` at `GET /bookings/availability` to confirm that the requested time slot is still free for that vehicle.
6. `Process Booking Service` requests the current booking quote from `Pricing Service` at `GET /pricing/quote`.
7. `Process Booking Service` creates the booking through `Booking Service` at `POST /booking` with the quoted price snapshot, `crossCycleBooking`, and `refundPendingOnRenewal` flags, and the booking is stored as `PAYMENT_PENDING`.
8. `Process Booking Service` returns the provisional booking result to the UI, including the `bookingId`, `PAYMENT_PENDING` status, and the pricing summary to be charged.
9. The FleetShare UI then submits payment to `POST /process-booking/pay` through Kong.
10. `Process Booking Service` loads the booking from `Booking Service` and determines the amount to charge from the explicit payment request or the booking's `displayedPrice`.
11. `Process Booking Service` submits the charge to `Payment Service` at `POST /payments`.
12. On the implemented successful path, `Process Booking Service` immediately processes the returned payment result and patches the booking through `Booking Service` at `PATCH /booking/{bookingId}/status` to `CONFIRMED`.
13. `Process Booking Service` returns the confirmed payment result back through Kong to the UI.
