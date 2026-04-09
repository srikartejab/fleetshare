# US2B Start Trip


## Scope / Boundary

This diagram covers the successful trip-start path after a cleared pre-trip inspection.

It stays on the successful `blocked=false` path after the internal validation call.

It includes:

- UI entry through Kong
- `Rental Execution Service` handoff to `Start Trip Service`
- booking ownership and status validation
- latest inspection re-check
- internal damage validation
- vehicle unlock through gRPC
- trip creation
- booking status update to `IN_PROGRESS`

It does not include:

- pre-trip inspection creation
- internal fault severe downstream recovery or incident publication
- end-trip processing

## Textual Flow

1. The customer submits the unlock / start request from the FleetShare UI to `POST /rental-execution/start` through Kong.
2. Kong routes the request to `Rental Execution Service`.
3. `Rental Execution Service` forwards the request payload unchanged to `Start Trip Service` at `POST /trips/start`.
4. `Start Trip Service` loads the booking from `Booking Service` using `GET /booking/{bookingId}`.
5. `Start Trip Service` verifies that the booking belongs to the requesting user, that the booking vehicle matches the requested `vehicleId`, and that the booking status is still `CONFIRMED`.
6. `Start Trip Service` queries `Record Service` using `GET /records?bookingId={bookingId}&recordType=EXTERNAL_DAMAGE` and uses the latest returned record.
7. `Start Trip Service` blocks the start unless a latest inspection record exists, the inspection `reviewState` is already cleared, and the inspection severity is not `SEVERE`.
8. `Start Trip Service` calls `Internal Damage Service` at `POST /internal-damage/validate` with `bookingId`, `vehicleId`, `userId`, and `notes`.
9. `Internal Damage Service` retrieves the latest telemetry snapshot for the vehicle, assesses the fault condition, and writes an `INTERNAL_FAULT` record to `Record Service` with `reviewState=INTERNAL_ASSESSED`.
10. On the successful start path, `Internal Damage Service` returns `blocked=false` to `Start Trip Service`.
11. `Start Trip Service` unlocks the vehicle through the vehicle gRPC adapter using `UnlockVehicle(vehicle_id, booking_id, user_id)`.
12. `Start Trip Service` creates the trip through `Trip Service` at `POST /trips/start`, passing `bookingId`, `vehicleId`, `userId`, `startedAt=booking.startTime`, and the subscription snapshot.
13. `Start Trip Service` patches the booking through `Booking Service` at `PATCH /booking/{bookingId}/status` with `status=IN_PROGRESS` and the new `tripId`.
14. `Start Trip Service` returns `{tripId, status=STARTED, unlockCommandSent=true}` to `Rental Execution Service`.
15. `Rental Execution Service` returns that same start response back through Kong to the UI.
