# US2B Start Trip

## Verification Result

This flow was re-verified against the implemented start-trip orchestration, the pre-start validation calls, and the end-to-end trip start behavior used in the scenario tests.

## Scope / Boundary

This diagram covers the successful trip-start path after a cleared pre-trip inspection.

It includes:

- UI entry through Kong
- `Rental Execution Service` handoff to `Start Trip Service`
- latest inspection re-check
- internal damage validation
- vehicle unlock through gRPC
- trip creation
- booking status update to `IN_PROGRESS`

It does not include:

- pre-trip inspection creation
- internal fault severe downstream recovery
- end-trip processing

## Textual Flow

1. The customer submits the unlock / start request from the FleetShare UI to `POST /rental-execution/start` through Kong.
2. Kong routes the request to `Rental Execution Service`.
3. `Rental Execution Service` forwards the request to `Start Trip Service` at `POST /trips/start`.
4. `Start Trip Service` loads the booking and verifies that the requesting user owns it and that the booking is still `CONFIRMED`.
5. `Start Trip Service` queries `Record Service` for the latest `EXTERNAL_DAMAGE` inspection record and confirms that the inspection is already cleared.
6. `Start Trip Service` calls `Internal Damage Service` at `POST /internal-damage/validate`.
7. `Internal Damage Service` validates the current internal condition and records the validation result in `Record Service`.
8. On the successful start path, `Internal Damage Service` returns `blocked=false` to `Start Trip Service`.
9. `Start Trip Service` unlocks the vehicle through the vehicle gRPC adapter.
10. `Start Trip Service` creates the trip through `Trip Service` at `POST /trips/start`.
11. `Start Trip Service` patches the booking status through `Booking Service` to `IN_PROGRESS` and stores the new `tripId`.
12. `Start Trip Service` returns `STARTED` to `Rental Execution Service`, which returns the final start result to the UI.

## Key Code References

- [rental_execution_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/rental_execution_service.py#L328)
- [start_trip_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/start_trip_service.py#L21)
- [start_trip_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/start_trip_service.py#L43)
- [internal_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/internal_damage_service.py#L151)
- [record_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/record_service.py#L133)
- [vehicle_grpc.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/vehicle_grpc.py#L21)
- [trip_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/trip_service.py#L97)
- [test_scenarios_e2e.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_scenarios_e2e.py#L172)
- [test_scenarios_e2e.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_scenarios_e2e.py#L366)
