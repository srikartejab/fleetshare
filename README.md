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

If you are running Docker Desktop with very low resources, increase memory first. The full stack is not reliable at roughly `2 GB` total Docker memory; on this machine MySQL was being OOM-killed and the rest of the services then failed to resolve `mysql`.

3. Open:
   - UI via Kong: `http://localhost:8000`
   - Kong Admin API: `http://localhost:8001`
   - Kong Manager UI: `http://localhost:8002`
   - RabbitMQ UI: `http://localhost:15672`
   - MinIO console: `http://localhost:9001`
   - MySQL UI (Adminer): `http://localhost:8080`

Local default access:

- UI via Kong: no login
- Kong Admin API: no login
- Kong Manager UI: no login
- RabbitMQ UI: username `guest`, password `guest`
- RabbitMQ AMQP: `amqp://guest:guest@rabbitmq:5672/`
- MinIO console / S3: username `minioadmin`, password `minioadmin`
- Adminer: no separate app login
- MySQL through Adminer: system `MySQL`, server `mysql`, username `root`, password `fleetshare_root`
- MySQL through Adminer: database can be left blank to browse all schemas, or set to a schema like `pricing_db`

## Deployment Notes

- Billing boundaries use `BILLING_TIMEZONE`, which defaults to `Asia/Singapore`. This controls subscription end dates and post-midnight allowance logic even if the VM clock or container timezone differs.
- The frontend is built to call Kong at `http://localhost:8000` by default, and Kong is the intended public entrypoint for the UI and browser-facing APIs.
- Kong services and routes are bootstrapped from `infrastructure/kong/kong.yml`. Kong Manager is available for inspection and temporary edits, but rerunning the Kong bootstrap will reapply the repo-defined baseline.
- `APP_ENV` is informational only. The current runtime does not switch behavior based on `APP_ENV`.
- MinIO remains the supported evidence store for this release. `AZURE_STORAGE_CONNECTION_STRING` is not used by the current code path.
- `AZURE_VISION_MODE=azure` requires `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, and `AZURE_OPENAI_DEPLOYMENT`. If Azure AI is unavailable, the inspection flow will force manual review instead of silently using mock results.

## Demo Flow

- Search and reserve a vehicle in the Customer view.
- Open Kong Manager at `http://localhost:8002` if you want to inspect the configured services and routes.
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

## Tests

Run the Python test suite from the repo root:

```powershell
pytest -q
```

This runs the fast unit/integration-style tests locally.

To run the full end-to-end business scenario tests against Docker Compose:

```powershell
python scripts/run_scenario_tests.py
```

This will:

- bring the full FleetShare stack up with `docker compose`
- wait for Kong and the backend services to become ready
- run all 3 scenario tests with terminal log output for key checkpoints
- shut the stack down and remove volumes when finished

If you want to keep the stack running after the scenario tests:

```powershell
python scripts/run_scenario_tests.py --keep-up
```

## Important Notes

- `Vehicle Service` is implemented in Python first so the surrounding contracts stay stable; it is intentionally isolated so it can later be ported to OutSystems.
- Payment and notifications are simulated but persisted.
- Azure OpenAI powers the production inspection path; local development can stay on `AZURE_VISION_MODE=mock`.
