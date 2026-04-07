# US3B Notification Dispatch

## Scope / Boundary

This diagram stops at notification creation and persistence.

It includes:

- notification event publication to RabbitMQ
- event consumption by `Notification Service`
- per-user notification persistence in the `notifications` table
- generic downstream consumers that later read notifications through service APIs

It does not include:

- the detailed customer or ops read paths
- Kong routing details
- browser-side merging logic

## Textual Flow

1. Backend workflow services publish notification-related events such as `booking.disruption_notification` or `billing.refund_adjustment_completed` to RabbitMQ.
2. `Notification Service` consumes those events from the shared RabbitMQ exchange.
3. `Notification Service` checks whether the incoming `event_id` was already recorded to avoid duplicate notification creation.
4. The service resolves target users from `userIds` or the fallback `userId` in the event payload.
5. For each target user, `Notification Service` derives the `CUSTOMER` or `OPS` audience and inserts one in-app notification row into the `notifications` table.
6. The first inserted row stores the source `event_id` for idempotency tracking.
7. Customer-facing and ops-facing consumers later retrieve those persisted notifications through `Notification Service` APIs .

