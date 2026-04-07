# US2C In-Trip Internal Damage / Fault Detection

## Verification Result

This flow was re-verified against both implemented entry paths into `Internal Damage Service`: telemetry-driven consumption from `vehicle.telemetry_alert` and manual fault reporting through `Rental Execution Service`. The severe path and duplicate-suppression behavior were cross-checked against the internal damage tests and the telemetry e2e scenario.

## Scope / Boundary

This diagram covers severe in-trip internal fault detection only.

It includes:

- telemetry-triggered and manual-report entry paths
- internal fault assessment
- record creation
- vehicle severe-status update
- incident publication
- trip disruption notification publication

It does not include:

- handle-damage downstream recovery internals
- end-trip processing internals

Those belong to `3a-handle-damage-recovery` and `us2d-end-trip`.

## Severe-Path Textual Flow

1. A severe internal issue enters through one of two implemented paths:
   - telemetry path: `Vehicle Service` receives telemetry and publishes `vehicle.telemetry_alert`
   - manual path: the user reports a fault through `POST /rental-execution/report-fault`, and `Rental Execution Service` forwards it to `POST /internal-damage/fault-alert`
2. `Internal Damage Service` resolves the active trip context and determines the latest snapshot data needed for assessment.
3. `Internal Damage Service` runs the internal fault assessment and normalizes the fault family.
4. `Internal Damage Service` creates an `INTERNAL_FAULT` record through `Record Service` at `POST /records`.
5. On the severe path, `Internal Damage Service` updates the vehicle status to `MAINTENANCE_REQUIRED` through the vehicle gRPC adapter.
6. `Internal Damage Service` checks duplicate suppression against recent faults and existing open tickets.
7. If the severe incident is not suppressed as a duplicate, `Internal Damage Service` publishes `incident.internal_fault_detected` to RabbitMQ.
8. If the trip context is available, `Internal Damage Service` also publishes `booking.disruption_notification` to RabbitMQ so the customer and ops receive the in-trip stop / end-trip advisory.
9. The service returns the severe blocked result to the direct caller for the manual-report path, or completes consumer processing for the telemetry path.

## Key Code References

- [rental_execution_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/rental_execution_service.py#L337)
- [internal_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/internal_damage_service.py#L37)
- [internal_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/internal_damage_service.py#L151)
- [internal_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/internal_damage_service.py#L255)
- [internal_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/internal_damage_service.py#L260)
- [record_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/record_service.py#L133)
- [vehicle_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/vehicle_service.py#L229)
- [vehicle_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/vehicle_service.py#L248)
- [vehicle_grpc.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/vehicle_grpc.py#L35)
- [test_internal_damage_service.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_internal_damage_service.py#L8)
- [test_scenarios_e2e.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_scenarios_e2e.py#L366)
