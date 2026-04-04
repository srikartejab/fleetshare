from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException


def get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
    response = httpx.get(url, params=params, timeout=20.0)
    _raise_for_status(response)
    return response.json()


def post_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = httpx.post(url, json=payload or {}, timeout=30.0)
    _raise_for_status(response)
    return response.json()


def patch_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = httpx.patch(url, json=payload or {}, timeout=30.0)
    _raise_for_status(response)
    return response.json()


def put_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = httpx.put(url, json=payload or {}, timeout=30.0)
    _raise_for_status(response)
    return response.json()


def _raise_for_status(response: httpx.Response):
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
