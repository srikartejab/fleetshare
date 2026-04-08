# US2C Telemetry-Driven Internal Fault Detection

## Scope / Boundary

This diagram covers telemetry-driven internal fault detection for both active trips and idle / parked vehicles.

It includes:

- telemetry-triggered entry path
- optional active trip context resolution
- internal fault assessment
- record creation
- vehicle severe-status update
- duplicate suppression against maintenance tickets and recent fault cache
- incident publication
- active-trip disruption notification publication

It does not include:

- downstream maintenance-ticket creation and handle-damage recovery internals
- end-trip processing internals

Those belong to `us3a-handle-damage-recovery` and `us2d-end-trip`.


This diagram shows only the telemetry-triggered path. In demo and e2e flows, `POST /ops-console/fleet/telemetry` is only a proxy into `Vehicle Service`; it is not a separate core detection step. A manual reporting path also exists through `POST /rental-execution/report-fault`, but that path is intentionally left out of this visual to keep the flow focused.

## Code-Verified High-Level Flow

Diagram source: [us2c-in-trip-internal-damage-fault-detection.drawio]

1. `Vehicle Service` accepts `POST /vehicles/telemetry`, persists the telemetry snapshot, and only publishes `vehicle.telemetry_alert` when `telemetry_requires_attention(...)` returns true.
2. `Internal Damage Service` consumes `vehicle.telemetry_alert` asynchronously from RabbitMQ.
3. `Internal Damage Service` attempts to resolve active trip context through `Booking Service` at `GET /bookings/vehicle/{vehicleId}/active`.
4. If no active in-progress booking exists for that vehicle, processing continues with vehicle-only context. The alert still counts and is not dropped.
5. `Internal Damage Service` uses the consumed event payload directly as the snapshot for assessment, including the persisted telemetry timestamp carried in the event. It does not re-fetch telemetry on this path.
6. `Internal Damage Service` assesses severity and normalizes the fault family.
7. `Internal Damage Service` creates an `INTERNAL_FAULT` record through `Record Service` at `POST /records`, even when there is no active booking or trip.
8. Only when the assessment is `SEVERE`, `Internal Damage Service` updates the vehicle status to `MAINTENANCE_REQUIRED` through the vehicle gRPC adapter.
9. Still on the severe path, `Internal Damage Service` checks duplicate suppression against both the recent in-memory fault cache and filtered open maintenance tickets from `Maintenance Service`.
10. If the severe incident is not suppressed as a duplicate, `Internal Damage Service` publishes `incident.internal_fault_detected` to RabbitMQ, including the original telemetry incident timestamp.
11. If active trip context exists and the severe incident is not suppressed, `Internal Damage Service` also publishes `booking.disruption_notification` so the active customer and ops receive the in-trip stop / end-trip advisory.
12. The telemetry-triggered detection path then completes asynchronously. Downstream maintenance-ticket creation and future-booking cancellation happen later in `Handle Damage Service` after it consumes `incident.internal_fault_detected`, even for severe alerts that started while the vehicle was idle.
