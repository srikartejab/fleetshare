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
- Record Service stores the case.
- The AI adapter classifies damage severity and confidence.
- For pre-trip severe damage, `Trip Experience Service` resolves the incident synchronously by calling `Handle Damage Service`.
- `Handle Damage Service` opens maintenance tickets, cancels affected bookings, and triggers refund/notification events.
- `incident.external_damage_detected` is published for severe post-trip damage, not for the pre-trip inspection path.

## User Scenario 3

- Telemetry or manual pickup faults are validated before trip activation.
- Critical faults publish `incident.internal_fault_detected`.
- The same downstream recovery pipeline cancels bookings, stores tickets, issues compensation, and notifies stakeholders.

## Beyond The Labs

- Kong API Gateway for unified public routing.
- gRPC for latency-sensitive `Vehicle Service` commands.
- External AI-style damage assessment adapter.

## Appendix Material To Include

- Technical overview / SOA diagram
- microservice interaction diagrams for all 3 scenarios
- service API docs
- team contribution table

