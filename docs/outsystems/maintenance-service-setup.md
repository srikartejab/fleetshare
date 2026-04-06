# OutSystems Setup For `maintenance_service.py`

You cannot reliably hand-build a valid OutSystems `.oml` file outside Service Studio. The practical handoff artifact is the API contract plus a Service Studio build map.

For this service, use [maintenance-service-swagger-2.json](/c:/Users/srika/Documents/esd/fleetshare/docs/outsystems/maintenance-service-swagger-2.json) as the contract file and implement the module below in OutSystems.

## 1. Pick the migration style

Use one of these two approaches:

1. Native OutSystems replacement.
   Build the entity and exposed REST API directly in OutSystems. This is the simplest option if you are replacing the Python service.
2. External database compatibility.
   Use an external database integration only if you must keep using the existing `maintenance_tickets` table outside OutSystems. Otherwise let OutSystems own the table.

## 2. Create the module

In Service Studio:

1. Create a new Service module or a Core-style backend module that will own data and server actions.
2. Name it something like `MaintenanceService`.
3. Expose REST from this same module.

## 3. Create the data model

Create entity `MaintenanceTicket` with these attributes:

| Attribute | Type | Required | Default | Notes |
|---|---|---|---|---|
| `Id` | Identifier | Yes | Auto | OutSystems built-in primary key |
| `VehicleId` | Integer | Yes |  | Add index |
| `DamageSeverity` | Text | Yes |  | Length 32 |
| `DamageType` | Text | Yes |  | Length 128 |
| `RecommendedAction` | Text | Yes |  | Length 255 |
| `EstimatedDurationHours` | Integer | Yes | `24` |  |
| `RecordId` | Integer | No | Null |  |
| `BookingId` | Integer | No | Null |  |
| `TripId` | Integer | No | Null |  |
| `OpenedByEventType` | Text | No | Null | Length 128 |
| `Status` | Text | Yes | `OPEN` | Length 64 |
| `CreatedAt` | Date Time | Yes | `CurrDateTime()` | Use create-time assignment |

Notes:

- The Python version uses SQLAlchemy table name `maintenance_tickets`.
- A native OutSystems entity will not keep that exact physical table name.
- If exact database-table compatibility matters, use external database integration instead of a native entity.

## 4. Create request and response structures

Create these structures so the REST contract stays close to the FastAPI version.

### `TicketPayload`

| Field | Type | Required |
|---|---|---|
| `vehicleId` | Integer | Yes |
| `damageSeverity` | Text | Yes |
| `damageType` | Text | Yes |
| `recommendedAction` | Text | Yes |
| `estimatedDurationHours` | Integer | No |
| `recordId` | Integer | No |
| `bookingId` | Integer | No |
| `tripId` | Integer | No |
| `openedByEventType` | Text | No |

### `MaintenanceTicketResponse`

| Field | Type | Notes |
|---|---|---|
| `ticketId` | Integer | Map from entity `Id` |
| `vehicleId` | Integer |  |
| `damageSeverity` | Text |  |
| `damageType` | Text |  |
| `recommendedAction` | Text |  |
| `estimatedDurationHours` | Integer |  |
| `recordId` | Integer | Nullable |
| `bookingId` | Integer | Nullable |
| `tripId` | Integer | Nullable |
| `openedByEventType` | Text | Nullable |
| `status` | Text |  |
| `createdAt` | Date Time | See DateTime note below |

### `ErrorResponse`

| Field | Type |
|---|---|
| `detail` | Text |

Important:

- Keep the JSON names aligned with the current API contract: `vehicleId`, `damageSeverity`, `createdAt`, and so on.
- If your OutSystems serialization does not emit `createdAt` the way your consumers expect, change `createdAt` in the response structure to `Text` and format it explicitly.

## 5. Create the server actions

Create these server actions:

1. `TicketToResponse`
   Input: `Ticket : MaintenanceTicket Record`
   Output: `Response : MaintenanceTicketResponse`
2. `ListTickets`
   Output: `Result : List of MaintenanceTicketResponse`
3. `CreateTicket`
   Input: `Payload : TicketPayload`
   Output: `Result : MaintenanceTicketResponse`
4. `GetTicket`
   Input: `TicketId : Integer`
   Output: `Result : MaintenanceTicketResponse`

### `TicketToResponse`

Map fields exactly like the Python `ticket_to_dict()` function:

- `ticketId = Ticket.Id`
- `vehicleId = Ticket.VehicleId`
- `damageSeverity = Ticket.DamageSeverity`
- `damageType = Ticket.DamageType`
- `recommendedAction = Ticket.RecommendedAction`
- `estimatedDurationHours = Ticket.EstimatedDurationHours`
- `recordId = Ticket.RecordId`
- `bookingId = Ticket.BookingId`
- `tripId = Ticket.TripId`
- `openedByEventType = Ticket.OpenedByEventType`
- `status = Ticket.Status`
- `createdAt = Ticket.CreatedAt`

### `ListTickets`

Implementation:

1. Create an Aggregate on `MaintenanceTicket`.
2. Sort by `MaintenanceTicket.Id` descending.
3. Loop through the records.
4. For each record, call `TicketToResponse`.
5. Append to the output list.

### `CreateTicket`

Implementation:

1. Validate required fields if you do not trust the caller.
2. Call `CreateMaintenanceTicket`.
3. Assign:
   `VehicleId = Payload.vehicleId`
   `DamageSeverity = Payload.damageSeverity`
   `DamageType = Payload.damageType`
   `RecommendedAction = Payload.recommendedAction`
   `EstimatedDurationHours = Payload.estimatedDurationHours`
   `RecordId = Payload.recordId`
   `BookingId = Payload.bookingId`
   `TripId = Payload.tripId`
   `OpenedByEventType = Payload.openedByEventType`
   `Status = "OPEN"`
   `CreatedAt = CurrDateTime()`
4. Read back the created record if needed.
5. Return `TicketToResponse`.

Practical note:

- If the incoming request can omit `estimatedDurationHours`, normalize it to `24` before create. The exact expression depends on how your Service Studio version deserializes missing numeric fields.
- If `0` is a valid business value, do not treat `0` as "missing".

### `GetTicket`

Implementation:

1. Use `GetMaintenanceTicketById(TicketId)` or an Aggregate filtered by `Id`.
2. If not found, return HTTP 404 with body:

```json
{
  "detail": "Ticket not found"
}
```

3. If found, return `TicketToResponse`.

## 6. Expose the REST API

Create one exposed REST API, for example `MaintenanceApi`, with these methods:

| Method | URL | Logic |
|---|---|---|
| `GET` | `/maintenance/tickets` | `ListTickets` |
| `POST` | `/maintenance/tickets` | `CreateTicket` |
| `GET` | `/maintenance/tickets/{ticket_id}` | `GetTicket` |

REST details:

- Add path input `ticket_id` as Integer.
- Use `TicketPayload` as the POST request body.
- Use `MaintenanceTicketResponse` or list of it for responses.
- Configure the not-found path to return `404`.

## 7. Match the current Python behavior

The FastAPI service currently does only three things:

1. Lists tickets ordered by newest first.
2. Creates a ticket with status `OPEN`.
3. Fetches one ticket and returns `404` when it does not exist.

Keep the OutSystems version equally small first. Do not add update/delete actions unless you need them.

## 8. Test with sample payloads

### Create ticket request

```json
{
  "vehicleId": 101,
  "damageSeverity": "HIGH",
  "damageType": "Front bumper crack",
  "recommendedAction": "Replace bumper assembly",
  "estimatedDurationHours": 24,
  "recordId": 8801,
  "bookingId": 4402,
  "tripId": 9910,
  "openedByEventType": "END_TRIP_DAMAGE"
}
```

### Example response

```json
{
  "ticketId": 1,
  "vehicleId": 101,
  "damageSeverity": "HIGH",
  "damageType": "Front bumper crack",
  "recommendedAction": "Replace bumper assembly",
  "estimatedDurationHours": 24,
  "recordId": 8801,
  "bookingId": 4402,
  "tripId": 9910,
  "openedByEventType": "END_TRIP_DAMAGE",
  "status": "OPEN",
  "createdAt": "2026-04-06T10:00:00Z"
}
```

## 9. Recommended import path

If your goal is speed:

1. Start by building the data model and exposed REST manually in Service Studio.
2. Use [maintenance-service-swagger-2.json](/c:/Users/srika/Documents/esd/fleetshare/docs/outsystems/maintenance-service-swagger-2.json) as the contract reference.
3. Only use external database integration if you must preserve the existing database table outside OutSystems.

If you want, the next useful artifact is not an `.oml`. It is either:

1. An OutSystems field-by-field mapping sheet for Service Studio.
2. A fuller OpenAPI 3.0 file.
3. A complete screen flow for CRUD and test UI.
