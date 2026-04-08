# US2D End Trip

## Verification Result

This flow was re-verified against the implemented end-trip orchestration, the pricing finalization path, the conditional refund / discount event publication, and the end-trip tests plus scenario coverage.

## Scope / Boundary

This diagram covers the implemented end-trip processing path in `Rental Execution Service` and `End Trip Service`.

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

1. The customer triggers end trip from the FleetShare UI through `POST /rental-execution/end` via Kong.
2. Kong routes the request to `Rental Execution Service`.
3. `Rental Execution Service` forwards the request to `End Trip Service` at `POST /end-trip/request`.
4. `End Trip Service` loads the booking and trip state.
5. If the trip is not already ended, `End Trip Service` locks the vehicle through the vehicle gRPC adapter.
6. `End Trip Service` patches the trip status through `Trip Service` to `ENDED`, including `endReason` and `disruptionReason` when applicable.
7. As part of the trip status patch, `Trip Service` publishes the `trip.ended` event. That downstream renewal flow is not expanded in this diagram.
8. `End Trip Service` requests final pricing through `Pricing Service` at `POST /pricing/finalize-trip`.
9. `End Trip Service` patches `Booking Service` with final price, reconciliation status, and final booking status (`COMPLETED` or `DISRUPTED`).
10. If the pricing result contains a refund, `End Trip Service` publishes `payment.refund_required` to RabbitMQ.
11. If the pricing result contains a discount, `End Trip Service` publishes `payment.adjustment_required` to RabbitMQ.
12. If either refund or discount is present, `End Trip Service` also publishes `booking.disruption_notification` to RabbitMQ.
13. `End Trip Service` returns the final end-trip result to `Rental Execution Service`, which returns it to the UI.

