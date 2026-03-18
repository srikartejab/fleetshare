from __future__ import annotations

import json
from pathlib import Path

import httpx


SERVICES = {
    "vehicle": "http://localhost:8000/vehicles/openapi.json",
    "booking": "http://localhost:8000/bookings/openapi.json",
    "trip": "http://localhost:8000/trips/openapi.json",
    "record": "http://localhost:8000/records/openapi.json",
    "maintenance": "http://localhost:8000/maintenance/openapi.json",
    "pricing": "http://localhost:8000/pricing/openapi.json",
    "payment": "http://localhost:8000/payments/openapi.json",
    "notification": "http://localhost:8000/notifications/openapi.json",
    "search": "http://localhost:8000/search-vehicles/openapi.json",
    "process-booking": "http://localhost:8000/process-booking/openapi.json",
    "external-damage": "http://localhost:8000/damage-assessment/openapi.json",
    "internal-damage": "http://localhost:8000/internal-damage/openapi.json",
    "end-trip": "http://localhost:8000/end-trip/openapi.json",
    "renewal-reconciliation": "http://localhost:8000/renewal-reconciliation/openapi.json",
}


def main():
    output_dir = Path("docs/generated/openapi")
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, url in SERVICES.items():
        response = httpx.get(url, timeout=20.0)
        response.raise_for_status()
        (output_dir / f"{name}.json").write_text(json.dumps(response.json(), indent=2), encoding="utf-8")
        print(f"exported {name}")


if __name__ == "__main__":
    main()

