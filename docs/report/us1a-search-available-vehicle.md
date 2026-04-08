# US1A Search Available Vehicle

## Scope / Boundary

This diagram covers the customer vehicle-search path before any booking is created.

It includes:

- UI entry through Kong
- `Search Available Vehicles Service` orchestration
- station catalog lookup
- vehicle candidate discovery
- operational availability check through vehicle gRPC
- booking-slot availability check
- per-vehicle pricing quote enrichment
- grouped search response back to the UI

It does not include:

- booking creation
- payment
- trip start

## Textual Flow

1. The customer submits the search request from the FleetShare UI to `GET /search-vehicles/search` through Kong.
2. Kong routes the request to `Search Available Vehicles Service`.
3. `Search Available Vehicles Service` validates that `endTime` is later than `startTime`.
4. `Search Available Vehicles Service` loads the station list from `Vehicle Service` at `GET /vehicles/stations` and the current vehicle candidates from `Vehicle Service` at `GET /vehicles/availability`.
5. `Search Available Vehicles Service` resolves the requested pickup location to the selected station and filters the candidate list by `vehicleType` when that filter is present.
6. For each remaining candidate vehicle, `Search Available Vehicles Service` checks operational readiness through the vehicle gRPC adapter. Vehicles that are not operationally available are removed from the result set.
7. `Search Available Vehicles Service` sends the surviving vehicle ids to `Booking Service` at `GET /bookings/availability` to remove vehicles that are already reserved for the requested time window.
8. For each vehicle that is still available, `Search Available Vehicles Service` requests a quote from `Pricing Service` at `GET /pricing/quote`.
9. `Search Available Vehicles Service` enriches each vehicle with pricing fields such as `estimatedPrice`, `crossCycleBooking`, allowance usage, and provisional post-midnight charging information.
10. `Search Available Vehicles Service` groups and sorts the vehicles into station buckets, prioritising the selected station and nearer results.
11. `Search Available Vehicles Service` returns the final search payload through Kong to the UI, including `vehicleList`, `estimatedPrice`, `availabilitySummary`, `selectedStationId`, `mapCenter`, and `stationList`.
