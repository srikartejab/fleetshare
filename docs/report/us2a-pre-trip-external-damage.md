# US2A Pre-Trip External Damage

## Verification Result

This flow was re-verified against the implemented pre-trip inspection path, the external damage service behavior, and the severe pre-trip test and e2e scenario coverage.

## Scope / Boundary

This diagram stops at the severe-path handoff from `Rental Execution Service` to `Handle Damage Service`.

It includes:

- UI entry through Kong
- pre-trip inspection orchestration
- record creation and evidence storage
- AI damage assessment
- severe vehicle status update
- synchronous handoff to `Handle Damage Service`

It does not include:

- maintenance ticket creation
- booking cancellation internals
- compensation calculation internals
- payment or notification consumer internals

Those belong to `3a-handle-damage-recovery`.

## Severe-Path Textual Flow

1. The customer submits the pre-trip inspection from the FleetShare UI to `POST /rental-execution/pre-trip-inspection` through Kong.
2. Kong routes the request to `Rental Execution Service`.
3. `Rental Execution Service` forwards the multipart form to `External Damage Service` at `POST /damage-assessment/external`.
4. `External Damage Service` creates an `EXTERNAL_DAMAGE` record through `Record Service` at `POST /records/ingest`.
5. `Record Service` stores the uploaded evidence in object storage and persists the pending record metadata.
6. `External Damage Service` runs `assess_damage(...)` and determines the inspection result.
7. `External Damage Service` patches the record through `PATCH /records/{recordId}` with the final `severity`, `reviewState`, `confidence`, and `detectedDamage`.
8. On the severe path, `External Damage Service` updates the vehicle status to `UNDER_INSPECTION` through the vehicle gRPC adapter.
9. `External Damage Service` returns the blocked severe assessment result to `Rental Execution Service`.
10. `Rental Execution Service` synchronously calls `Handle Damage Service` at `POST /handle-damage/external/pre-trip-resolution`.
11. `Handle Damage Service` returns a recovery summary to `Rental Execution Service`.
12. `Rental Execution Service` returns the final severe inspection response through Kong.
13. Kong returns the final severe inspection response to the UI.

## Key Code References

- [rental_execution_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/rental_execution_service.py#L156)
- [rental_execution_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/rental_execution_service.py#L252)
- [external_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/external_damage_service.py#L36)
- [external_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/external_damage_service.py#L63)
- [record_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/record_service.py#L175)
- [record_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/record_service.py#L241)
- [vehicle_grpc.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/vehicle_grpc.py#L35)
- [test_rental_execution_service.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_rental_execution_service.py#L91)
- [test_external_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_external_damage_service.py#L328)
- [test_scenarios_e2e.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_scenarios_e2e.py#L252)
