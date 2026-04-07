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
3. `Rental Execution Service` forwards the request to `Start Trip Service` at `POST /trips/start`.
4. `Start Trip Service` loads the booking from `Booking Service` and verifies that the requesting user owns it and that the booking is still `CONFIRMED`.
5. `Start Trip Service` queries `Record Service` for the latest `EXTERNAL_DAMAGE` inspection record and confirms that the inspection is already cleared.
6. `Start Trip Service` calls `Internal Damage Service` at `POST /internal-damage/validate`.
7. `Internal Damage Service` performs telemetry-backed internal validation and writes an `INTERNAL_FAULT` validation record to `Record Service`.
8. On the successful start path, `Internal Damage Service` returns `blocked=false` to `Start Trip Service`.
9. `Start Trip Service` unlocks the vehicle through the vehicle gRPC adapter.
10. `Start Trip Service` creates the trip through `Trip Service` at `POST /trips/start`.
11. `Start Trip Service` patches the booking status through `Booking Service` to `IN_PROGRESS` and stores the new `tripId`.
12. `Start Trip Service` returns `STARTED` to `Rental Execution Service`, which returns the final start result back through Kong to the UI.
