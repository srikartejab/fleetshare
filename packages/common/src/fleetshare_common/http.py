from __future__ import annotations

import json
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


def post_form_json(
    url: str,
    data: dict[str, Any] | None = None,
    files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
) -> dict[str, Any]:
    filtered_data = {key: value for key, value in (data or {}).items() if value is not None}
    response = httpx.post(url, data=filtered_data, files=files or [], timeout=30.0)
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
        detail = _extract_error_detail(exc.response)
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc


def _extract_error_detail(response: httpx.Response) -> str:
    raw_text = response.text.strip()
    if not raw_text:
        return response.reason_phrase

    current: Any = raw_text
    for _ in range(4):
        if isinstance(current, str):
            try:
                current = json.loads(current)
            except json.JSONDecodeError:
                return current
        if isinstance(current, dict):
            detail = current.get("detail")
            if detail is None:
                return raw_text
            current = detail
            continue
        if isinstance(current, list):
            first = current[0] if current else None
            if isinstance(first, dict):
                msg = first.get("msg")
                if isinstance(msg, str) and msg.strip():
                    return msg
            return raw_text
        return str(current)

    return raw_text
