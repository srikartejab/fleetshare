# US2A Pre-Trip External Damage



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

Those belong to `us3a-handle-damage-recovery`.

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

