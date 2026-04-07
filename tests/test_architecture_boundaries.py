from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_kong_exposes_only_browser_facing_composite_routes():
    kong_config = yaml.safe_load((ROOT / "infrastructure" / "kong" / "kong.yml").read_text())
    public_paths = {
        path
        for service in kong_config["services"]
        for route in service.get("routes", [])
        for path in route.get("paths", [])
    }

    assert public_paths == {"/", "/search-vehicles", "/process-booking", "/rental-execution", "/ops-console"}


def test_only_owner_services_have_database_urls_in_compose():
    compose_config = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose_config["services"]
    database_services = {
        service_name
        for service_name, service in services.items()
        if "DATABASE_URL" in (service.get("environment") or {})
    }

    assert database_services == {
        "vehicle-service",
        "booking-service",
        "trip-service",
        "record-service",
        "maintenance-service",
        "pricing-service",
        "payment-service",
        "notification-service",
    }


def test_db_less_composites_do_not_import_shared_database_layer():
    db_less_services = [
        "search_available_vehicles_service.py",
        "process_booking_service.py",
        "rental_execution_service.py",
        "external_damage_service.py",
        "start_trip_service.py",
        "internal_damage_service.py",
        "end_trip_service.py",
        "handle_damage_service.py",
        "renewal_reconciliation_service.py",
        "ops_console_service.py",
    ]

    apps_dir = ROOT / "packages" / "common" / "src" / "fleetshare_common" / "apps"
    for service_filename in db_less_services:
        source = (apps_dir / service_filename).read_text()
        assert "fleetshare_common.database" not in source, service_filename
