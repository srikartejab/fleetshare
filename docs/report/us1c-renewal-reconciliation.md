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

1. In the demo flow, `POST /ops-console/renewal/simulate` forwards to `POST /renewal-reconciliation/simulate`, which publishes a `subscription.renewed` event with a concrete `newBillingCycleId`.

2. Renewal Reconciliation Service consumes the `subscription.renewed` event from RabbitMQ.

3. It calls Pricing Service at `POST /pricing/customers/{userId}/renewal` to apply or confirm the renewed billing cycle and obtain the active `billingCycleId`.

4. Using that active billing cycle, it calls Booking Service at `GET /bookings/reconciliation-pending?userId=...&billingCycleId=...` to retrieve bookings still pending renewal reconciliation.

5. For each pending candidate, it calls Trip Service at `GET /trips/{tripId}` and continues only if the trip is already `ENDED` and has `endedAt`.

6. It then calls Pricing Service at `POST /pricing/re-rate-renewed-booking` with the booking, trip, user, active billing cycle, and `actualPostMidnightHours` to calculate the revised final price, refund amount, and restored included hours.

7. If `refundAmount > 0`, Renewal Reconciliation Service publishes `payment.refund_required` to RabbitMQ and updates the booking reconciliation state to `REFUND_PENDING` while keeping `refundPendingOnRenewal=true`.

8. Payment Service consumes `payment.refund_required`, persists the refund payment record, and then publishes `payment.refund_completed`.

9. Renewal Reconciliation Service consumes `payment.refund_completed`, clears `refundPendingOnRenewal`, marks both booking and pricing reconciliation as `COMPLETED`, and sets the booking status to `RECONCILED`.

10. If the re-rating produced a refund or restored included hours, Renewal Reconciliation Service publishes `billing.refund_adjustment_completed`; Notification Service consumes it and stores the in-app notification, which the customer sees later through the normal wallet/account flow.

