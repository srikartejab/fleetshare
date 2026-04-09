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


## Demo-triggered path

1. `POST /ops-console/renewal/simulate`
2. forwards to `POST /renewal-reconciliation/simulate`
3. publishes `subscription.renewed` with concrete `newBillingCycleId`

## Renewal reconciliation

4. Renewal Reconciliation Service consumes `subscription.renewed`
5. calls `POST /pricing/customers/{userId}/renewal`
6. Pricing Service returns active `billingCycleId`
7. calls `GET /bookings/reconciliation-pending?userId=...&billingCycleId=...`
8. Booking Service returns candidates where:
   - `refundPendingOnRenewal = true`
   - `pricingSnapshot.nextBillingCycleId == billingCycleId`
9. for each candidate, call `GET /trips/{tripId}`
10. continue only if:
    - trip `status == ENDED`
    - `endedAt` exists

## Re-rating

11. call `POST /pricing/re-rate-renewed-booking` with:
    - `bookingId`
    - `tripId`
    - `userId`
    - `newBillingCycleId`
    - `actualPostMidnightHours`
12. Pricing Service computes:
    - revised `finalPrice`
    - `refundAmount`
    - `eligibleIncludedHours`
13. Pricing Service internally sets reconciliation ledger to:
    - `REFUND_PENDING` if `refundAmount > 0`
    - `COMPLETED` otherwise

## Refund-required branch

14. if `refundAmount > 0`, publish `payment.refund_required`
15. patch Booking Service `/booking/{bookingId}/reconciliation-state` to:
    - `finalPrice = rerated final price`
    - `refundPendingOnRenewal = true`
    - `reconciliationStatus = REFUND_PENDING`

## Payment completion

16. Payment Service consumes `payment.refund_required`
17. stores refund payment record with status `REFUNDED`
18. publishes `payment.refund_completed`

## Final completion

19. Renewal Reconciliation Service consumes `payment.refund_completed`
20. patch Booking Service to:
    - `finalPrice = finalPrice from completion payload`
    - `refundPendingOnRenewal = false`
    - `reconciliationStatus = COMPLETED`
    - booking `status = RECONCILED`
21. patch Pricing Service `/pricing/bookings/{bookingId}/reconciliation-state` to `COMPLETED`

## Notification

22. if `refundAmount > 0` or `eligibleIncludedHours > 0`, publish `billing.refund_adjustment_completed`
23. Notification Service consumes it and stores in-app notification
24. customer later sees refund/payment + notification via wallet/account flow

## Additional actual-code trigger

- Renewal Reconciliation Service also consumes `trip.ended`
- this acts as a catch-up trigger for bookings still pending renewal reconciliation after the billing cycle becomes active