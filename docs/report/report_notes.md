# FleetShare Report Notes

## Business Scenario

FleetShare addresses three car-sharing pain points in Singapore:

- subscription-boundary billing complexity
- disputes over pre-existing vehicle damage
- reactive maintenance that disrupts customer trips

## User Scenario 1

- Customer searches and reserves a vehicle close to a subscription-cycle boundary.
- Pricing computes provisional charges for post-midnight usage.
- Booking is confirmed after simulated payment.
- Trip completion publishes `trip.ended`.
- Renewal reconciliation consumes `subscription.renewed`, re-rates the post-midnight portion, and publishes refund adjustments.

## User Scenario 2

- Customer performs a pre-trip inspection and uploads evidence.
- Record Service stores the case and the damage assessment flow classifies severity.
- For pre-trip severe damage, `Rental Execution Service` calls `Handle Damage Service` synchronously.
- After a cleared inspection, the customer starts the trip through `Rental Execution Service` and `Start Trip Service`.
- Severe post-trip damage uses the asynchronous incident path rather than the synchronous pre-trip resolution path.

## User Scenario 3

- During an active trip, telemetry alerts or manual fault reports are processed by `Internal Damage Service`.
- Severe internal faults publish `incident.internal_fault_detected` and `booking.disruption_notification`.
- The downstream recovery flow opens maintenance work, cancels affected future bookings, and triggers compensation and notification events.
- The trip is then completed through the end-trip flow, which locks the vehicle, finalizes pricing, and publishes any required refund or adjustment events.

## Beyond The Labs

- Kong API Gateway for unified public routing.
- gRPC for latency-sensitive `Vehicle Service` commands.
- External AI-style damage assessment adapter.

## Appendix Material To Include

- Technical overview / SOA diagram
- microservice interaction diagrams for all 3 scenarios
- service API docs
- team contribution table

