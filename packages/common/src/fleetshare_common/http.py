from __future__ import annotations

from typing import Any

import httpx


def get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
    response = httpx.get(url, params=params, timeout=20.0)
    response.raise_for_status()
    return response.json()


def post_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = httpx.post(url, json=payload or {}, timeout=30.0)
    response.raise_for_status()
    return response.json()


def patch_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = httpx.patch(url, json=payload or {}, timeout=30.0)
    response.raise_for_status()
    return response.json()


def put_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = httpx.put(url, json=payload or {}, timeout=30.0)
    response.raise_for_status()
    return response.json()

