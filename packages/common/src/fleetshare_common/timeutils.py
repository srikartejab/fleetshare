from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from fleetshare_common.settings import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@lru_cache
def billing_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().billing_timezone)


def billing_now() -> datetime:
    return utcnow().astimezone(billing_timezone())


def billing_today() -> date:
    return billing_now().date()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def as_utc_naive(value: datetime) -> datetime:
    return as_utc(value).replace(tzinfo=None)


def utcnow_naive() -> datetime:
    return utcnow().replace(tzinfo=None)


def as_billing_time(value: datetime) -> datetime:
    return as_utc(value).astimezone(billing_timezone())


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat().replace("+00:00", "Z")
