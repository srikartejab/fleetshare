from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

MANAGED_TAG = "fleetshare-managed"
CONFIG_PATH = Path(__file__).with_name("kong.yml")
ADMIN_URL = os.getenv("KONG_ADMIN_URL", "http://kong:8001").rstrip("/")
BOOTSTRAP_TIMEOUT_SECONDS = int(os.getenv("KONG_BOOTSTRAP_TIMEOUT_SECONDS", "90"))


def _admin_request(method: str, path: str, *, expected_statuses: set[int], json: dict[str, Any] | None = None) -> httpx.Response:
    response = httpx.request(method, f"{ADMIN_URL}{path}", json=json, timeout=10.0)
    if response.status_code not in expected_statuses:
        raise RuntimeError(f"{method} {path} failed with {response.status_code}: {response.text.strip()}")
    return response


def _wait_for_admin():
    deadline = time.time() + BOOTSTRAP_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            response = httpx.get(f"{ADMIN_URL}/", timeout=5.0)
            if response.is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError(f"Kong Admin API was not ready within {BOOTSTRAP_TIMEOUT_SECONDS} seconds.")


def _load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    services = raw.get("services")
    if not isinstance(services, list):
        raise RuntimeError(f"Invalid Kong config at {CONFIG_PATH}: expected 'services' list.")
    return raw


def _service_payload(service: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": service["name"],
        "tags": [MANAGED_TAG],
    }
    for field in ("url", "protocol", "host", "port", "path"):
        value = service.get(field)
        if value is not None:
            payload[field] = value
    return payload


def _route_payload(route: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": route["name"],
        "tags": [MANAGED_TAG],
    }
    for field in ("paths", "methods", "protocols", "hosts", "strip_path", "preserve_host"):
        value = route.get(field)
        if value is not None:
            payload[field] = value
    return payload


def _get_or_create_service(service: dict[str, Any]) -> dict[str, Any]:
    name = service["name"]
    payload = _service_payload(service)
    existing = _admin_request("GET", f"/services/{name}", expected_statuses={200, 404})
    if existing.status_code == 404:
        return _admin_request("POST", "/services", expected_statuses={201}, json=payload).json()
    return _admin_request("PATCH", f"/services/{name}", expected_statuses={200}, json=payload).json()


def _get_or_create_route(service_name: str, route: dict[str, Any]) -> dict[str, Any]:
    name = route["name"]
    payload = _route_payload(route)
    existing = _admin_request("GET", f"/routes/{name}", expected_statuses={200, 404})
    if existing.status_code == 404:
        return _admin_request("POST", f"/services/{service_name}/routes", expected_statuses={201}, json=payload).json()
    return _admin_request("PATCH", f"/routes/{name}", expected_statuses={200}, json=payload).json()


def _delete_stale_routes(desired_route_names: set[str]):
    routes = _admin_request("GET", "/routes", expected_statuses={200}).json().get("data", [])
    for route in routes:
        tags = set(route.get("tags") or [])
        if MANAGED_TAG not in tags:
            continue
        route_name = route.get("name")
        if route_name in desired_route_names:
            continue
        _admin_request("DELETE", f"/routes/{route['id']}", expected_statuses={204, 404})


def _delete_stale_services(desired_service_names: set[str]):
    services = _admin_request("GET", "/services", expected_statuses={200}).json().get("data", [])
    for service in services:
        tags = set(service.get("tags") or [])
        if MANAGED_TAG not in tags:
            continue
        service_name = service.get("name")
        if service_name in desired_service_names:
            continue
        _admin_request("DELETE", f"/services/{service['id']}", expected_statuses={204, 404})


def sync():
    _wait_for_admin()
    config = _load_config()
    desired_service_names: set[str] = set()
    desired_route_names: set[str] = set()

    for service in config["services"]:
        service_name = service["name"]
        desired_service_names.add(service_name)
        _get_or_create_service(service)
        for route in service.get("routes", []):
            desired_route_names.add(route["name"])
            _get_or_create_route(service_name, route)

    _delete_stale_routes(desired_route_names)
    _delete_stale_services(desired_service_names)


if __name__ == "__main__":
    try:
        sync()
    except Exception as exc:  # pragma: no cover - script entrypoint
        print(f"[kong-bootstrap] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
