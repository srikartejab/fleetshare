# US2C In-Trip Internal Damage / Fault Detection

## Verification Result

This flow was re-verified against the telemetry-driven entry path into `Internal Damage Service`: publication and consumption of `vehicle.telemetry_alert`. The severe path, duplicate-suppression behavior, demo telemetry proxy, and RabbitMQ topology were cross-checked against the service code, Docker runtime, and the telemetry e2e scenario. A separate manual fault-report path still exists through `Rental Execution Service`, but it is not expanded in this diagram.

## Scope / Boundary

This diagram covers severe in-trip internal fault detection only.

It includes:

- telemetry-triggered entry path
- active trip context resolution
- internal fault assessment
- record creation
- vehicle severe-status update
- duplicate suppression against maintenance tickets and recent fault cache
- incident publication
- trip disruption notification publication

It does not include:

- downstream maintenance-ticket creation and handle-damage recovery internals
- end-trip processing internals

Those belong to `us3a-handle-damage-recovery` and `us2d-end-trip`.

This report refers to one RabbitMQ deployment only. `docker-compose.yml` defines a single `rabbitmq` service, and the current runtime shows one RabbitMQ container: `fleetshare-rabbitmq-1`.

This diagram shows only the telemetry-triggered path, including telemetry injected via `POST /ops-console/fleet/telemetry` in demo/e2e flows. A manual reporting path also exists through `POST /rental-execution/report-fault`, but that path is intentionally left out of this visual to keep the flow focused.

## Severe-Path Textual Flow

1. `Vehicle Service` accepts `POST /vehicles/telemetry` and publishes `vehicle.telemetry_alert` when the incoming snapshot requires attention.
2. In demo and e2e flows, telemetry can also be injected through `POST /ops-console/fleet/telemetry`, which only proxies the request to `Vehicle Service`; it is not a separate production fault-detection path.
3. `Internal Damage Service` consumes `vehicle.telemetry_alert` from RabbitMQ. This is an asynchronous consumer path with no direct UI response.
4. `Internal Damage Service` resolves the active trip context through `Booking Service` at `GET /bookings/vehicle/{vehicleId}/active`.
5. `Internal Damage Service` uses the consumed telemetry event payload as the snapshot for assessment.
6. `Internal Damage Service` runs the internal fault assessment and normalizes the fault family. The telemetry event itself is not automatically severe; severity is decided here.
7. `Internal Damage Service` creates an `INTERNAL_FAULT` record through `Record Service` at `POST /records`.
8. On the severe path, `Internal Damage Service` updates the vehicle status to `MAINTENANCE_REQUIRED` through the vehicle gRPC adapter.
9. `Internal Damage Service` checks duplicate suppression against recent in-memory faults and existing open tickets from `Maintenance Service` at `GET /maintenance/tickets`.
10. If the severe incident is not suppressed as a duplicate, `Internal Damage Service` publishes `incident.internal_fault_detected` to RabbitMQ.
11. If the severe incident is not suppressed and trip context is available, `Internal Damage Service` also publishes `booking.disruption_notification` to RabbitMQ so the customer and ops receive the in-trip stop / end-trip advisory.
12. The telemetry path then completes asynchronously. A separate manual reporting path still exists through `POST /rental-execution/report-fault`, but it is outside this diagram.

## Key Code References

- [internal_damage_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/internal_damage_service.py#L35)
- [internal_damage_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/internal_damage_service.py#L164)
- [internal_damage_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/internal_damage_service.py#L248)
- [booking_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/booking_service.py#L141)
- [maintenance_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/maintenance_service.py#L289)
- [record_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/record_service.py#L156)
- [vehicle_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/vehicle_service.py#L60)
- [vehicle_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/vehicle_service.py#L230)
- [vehicle_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/vehicle_service.py#L261)
- [vehicle_grpc.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/vehicle_grpc.py#L34)
- [messaging.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/messaging.py#L28)
- [ops_console_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/ops_console_service.py#L303)
- [rental_execution_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/packages/common/src/fleetshare_common/apps/rental_execution_service.py#L337)
- [docker-compose.yml](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/docker-compose.yml#L67)
- [test_internal_damage_service.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/tests/test_internal_damage_service.py#L8)
- [test_scenarios_e2e.py](c:/Users/srika/My%20Drive/SMU/esd/fleetshare/tests/test_scenarios_e2e.py#L389)
