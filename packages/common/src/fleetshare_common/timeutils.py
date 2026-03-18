from __future__ import annotations

from datetime import datetime


def utcnow() -> datetime:
    return datetime.utcnow()


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()

