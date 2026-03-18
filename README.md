# FleetShare

FleetShare is a university microservices project for a smart car-sharing platform. The repo contains:

- a React + TypeScript dashboard in `apps/web`
- Python microservices and shared contracts in `packages/common/src/fleetshare_common`
- infrastructure config for Kong, MySQL, RabbitMQ, and MinIO in `infrastructure`
- Docker orchestration in `docker-compose.yml`

## Stack

- Frontend: React 19, TypeScript, Vite
- Backend services: FastAPI, SQLAlchemy, gRPC, RabbitMQ
- Data: MySQL with separate databases per service
- Storage: MinIO for inspection evidence
- Gateway: Kong

## Core Scenarios

1. Overnight booking across a subscription boundary with provisional charging and post-renewal refund reconciliation.
2. Pre-trip external damage inspection with AI-assisted severity assessment and manual-review fallback.
3. Telemetry-backed proactive maintenance that blocks unsafe trip start, cancels affected bookings, and triggers refunds.

## Run

1. Copy `.env.example` to `.env` if you need custom values.
2. Start the full system:

```powershell
docker compose up --build
```

3. Open:
   - UI: `http://localhost:4173`
   - Kong proxy: `http://localhost:8000`
   - Kong admin: `http://localhost:8001`
   - RabbitMQ UI: `http://localhost:15672`
   - MinIO console: `http://localhost:9001`

## Demo Flow

- Search and reserve a vehicle in the Customer view.
- Submit a pre-trip inspection with notes like `scratch` or `dent`.
- Start a trip. For Scenario 3, inject `CRITICAL` telemetry first and then retry trip start.
- End the trip manually or with `SEVERE_INTERNAL_FAULT`.
- Publish a renewal event from the Operations panel to trigger refund reconciliation.
- Verify tickets, payments, records, and notifications in the Operations and Technician panels.

## OpenAPI

Each FastAPI service exposes `/openapi.json` on its own container and through Kong where routed. Use:

```powershell
python scripts/export_openapi.py
```

to export selected OpenAPI specs into `docs/generated/openapi/` once the stack is running.

## Important Notes

- `Vehicle Service` is implemented in Python first so the surrounding contracts stay stable; it is intentionally isolated so it can later be ported to OutSystems.
- Payment and notifications are simulated but persisted.
- Azure Computer Vision is represented by a mockable adapter inside the external damage workflow.
