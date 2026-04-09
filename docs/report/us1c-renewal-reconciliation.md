# US1C Renewal Reconciliation

## Scope / Boundary

This diagram covers the event-driven reconciliation flow for cross-cycle bookings after a subscription renewal.

It includes:

- event-driven ingress into `Renewal Reconciliation Service`
- manual renewal simulation through the ops route
- pricing renewal application
- pending-booking lookup
- ended-trip validation
- booking re-rating after renewal
- refund event publication
- reconciliation completion update
- billing adjustment notification event publication

It does not include:

- the original booking creation flow
- notification consumer internals
- payment consumer internals

## Textual Flow

1. `Renewal Reconciliation Service` starts a RabbitMQ consumer for both `subscription.renewed` and `trip.ended`.
2. In demo and ops flows, `POST /ops-console/renewal/simulate` forwards to `POST /renewal-reconciliation/simulate`, which publishes `subscription.renewed` with a concrete `newBillingCycleId`.
3. On the renewal path, `Renewal Reconciliation Service` applies the new customer billing cycle through `Pricing Service` at `POST /pricing/customers/{userId}/renewal`.
4. After pricing confirms the active billing cycle, `Renewal Reconciliation Service` asks `Booking Service` for pending candidates through `GET /bookings/reconciliation-pending`.
5. On the `trip.ended` catch-up path, `Renewal Reconciliation Service` first loads the booking from `Booking Service`, fetches the customer's current summary from `Pricing Service`, and exits unless `refundPendingOnRenewal` is still true and the booking's stored `nextBillingCycleId` now matches the active billing cycle derived from that summary.
6. For each pending candidate that still requires reconciliation, `Renewal Reconciliation Service` loads the trip from `Trip Service` and continues only when the trip is already `ENDED`.
7. `Renewal Reconciliation Service` requests the final re-rating from `Pricing Service` at `POST /pricing/re-rate-renewed-booking`, using the actual post-midnight usage from the ended trip.
8. If the re-rating result includes a positive refund amount, `Renewal Reconciliation Service` publishes `payment.refund_required` to RabbitMQ and updates the booking to `reconciliationStatus=REFUND_PENDING` while keeping `refundPendingOnRenewal=true`.
9. `Payment Service` persists the refund row and then publishes `payment.refund_completed` with the original refund event id as `sourceEventId`.
10. `Renewal Reconciliation Service` consumes `payment.refund_completed`, marks booking and pricing reconciliation as `COMPLETED`, clears `refundPendingOnRenewal`, and only then sets the booking status to `RECONCILED`.
11. If the re-rating restored included hours or produced a refund, `Renewal Reconciliation Service` publishes `billing.refund_adjustment_completed` after the final completion step.
12. On zero-refund re-rates, `Renewal Reconciliation Service` may complete the booking immediately after the re-rate because no downstream cash refund persistence is required.
