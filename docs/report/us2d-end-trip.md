# US2D End Trip

## Verification Result

This flow was re-verified against the implemented end-trip orchestration, the pricing finalization path, the conditional refund / discount event publication, and the end-trip tests plus scenario coverage.

## Scope / Boundary

This diagram covers the implemented end-trip processing path in `Trip Experience Service` and `End Trip Service`.

It includes:

- UI entry through Kong
- end-trip orchestration
- vehicle lock
- trip status patch
- pricing finalization
- booking financial and status updates
- conditional payment / notification event publication

It does not expand:

- downstream payment consumer behavior
- downstream notification consumer behavior
- renewal reconciliation behavior from `trip.ended`

## Textual Flow

1. The customer triggers end trip from the FleetShare UI through `POST /trip-experience/end` via Kong.
2. Kong routes the request to `Trip Experience Service`.
3. `Trip Experience Service` forwards the request to `End Trip Service` at `POST /end-trip/request`.
4. `End Trip Service` loads the booking and trip state.
5. If the trip is not already ended, `End Trip Service` locks the vehicle through the vehicle gRPC adapter.
6. `End Trip Service` patches the trip status through `Trip Service` to `ENDED`, including `endReason` and `disruptionReason` when applicable.
7. As part of the trip status patch, `Trip Service` publishes the `trip.ended` event. That downstream renewal flow is not expanded in this diagram.
8. `End Trip Service` requests final pricing through `Pricing Service` at `POST /pricing/finalize-trip`.
9. `End Trip Service` patches `Booking Service` with final price, reconciliation status, and final booking status (`COMPLETED` or `DISRUPTED`).
10. If the pricing result contains a refund, `End Trip Service` publishes `payment.refund_required` to RabbitMQ.
11. If the pricing result contains a discount, `End Trip Service` publishes `payment.adjustment_required` to RabbitMQ.
12. If either refund or discount is present, `End Trip Service` also publishes `booking.disruption_notification` to RabbitMQ.
13. `End Trip Service` returns the final end-trip result to `Trip Experience Service`, which returns it to the UI.

## Key Code References

- [trip_experience_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/trip_experience_service.py#L369)
- [end_trip_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/end_trip_service.py#L24)
- [end_trip_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/end_trip_service.py#L123)
- [vehicle_grpc.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/vehicle_grpc.py#L28)
- [trip_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/trip_service.py#L114)
- [pricing_service.py](c:/Users/srika/Documents/esd/fleetshare/packages/common/src/fleetshare_common/apps/pricing_service.py#L363)
- [test_end_trip_service.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_end_trip_service.py#L6)
- [test_end_trip_service.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_end_trip_service.py#L62)
- [test_scenarios_e2e.py](c:/Users/srika/Documents/esd/fleetshare/tests/test_scenarios_e2e.py#L172)
