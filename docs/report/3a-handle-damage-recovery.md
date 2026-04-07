# 3A Handle Damage Recovery



## Scope / Boundary

This diagram covers the generic recovery work performed by `Handle Damage Service`.

It includes:

- sync and async ingress into `Handle Damage Service`
- sync return to `Trip Experience Service` on the pre-trip severe path
- maintenance ticket creation through the wrapper service
- cancellation of affected bookings
- pre-trip compensation calculation
- refund / adjustment event publication
- disruption notification event publication

It does not include:

- notification consumer internals
- payment consumer internals

## Textual Flow

1. `Handle Damage Service` receives the recovery input through one of two implemented paths:
   - synchronous path: `POST /handle-damage/external/pre-trip-resolution`
   - asynchronous path: consume `incident.external_damage_detected` or `incident.internal_fault_detected` from RabbitMQ
2. `Handle Damage Service` resolves the incident time and a stable source event id for idempotent downstream publication.
3. `Handle Damage Service` creates a maintenance ticket through `Maintenance Service` at `POST /maintenance/tickets`.
4. In the repo's default configuration, `Maintenance Service` forwards that ticket request to the OutSystems maintenance REST API.
5. `Handle Damage Service` cancels the affected booking set through `Booking Service` at `PUT /bookings/cancel-affected`.
6. If affected bookings exist, `Handle Damage Service` requests compensation from `Pricing Service` at `POST /pricing/pre-trip-cancellation-compensation`.
7. For each affected booking, `Handle Damage Service` publishes `payment.refund_required` when a cash refund is due.
8. For each affected booking, `Handle Damage Service` publishes `payment.adjustment_required` when an apology credit or discount is due.
9. For each affected booking, `Handle Damage Service` publishes `booking.disruption_notification` for the customer audience.
10. `Handle Damage Service` also publishes `booking.disruption_notification` for the ops audience with the opened maintenance ticket information.
11. On the synchronous pre-trip path, `Handle Damage Service` returns the recovery summary back to `Trip Experience Service`.
12. On the asynchronous incident path, `Handle Damage Service` finishes consumer processing after publishing the downstream events.

## Diagram Note

The repo uses one RabbitMQ broker / topic exchange. In this diagram it is shown as a single RabbitMQ box with:

- one inbound arrow into `Handle Damage Service` for consumed incident events
- one outbound arrow from `Handle Damage Service` for published downstream events
- one maintenance wrapper box plus one OutSystems backend box because the wrapper and backend are separate components in the codebase / deployment model


