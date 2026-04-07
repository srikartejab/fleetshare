from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from fleetshare_common import timeutils
from fleetshare_common.timeutils import as_utc_naive, iso


def test_iso_serializes_naive_utc_as_z():
    assert iso(datetime(2026, 3, 18, 15, 40)) == "2026-03-18T15:40:00Z"


def test_iso_normalizes_aware_datetimes_to_utc():
    singapore_time = datetime(2026, 3, 18, 23, 40, tzinfo=timezone(timedelta(hours=8)))
    assert iso(singapore_time) == "2026-03-18T15:40:00Z"
    assert as_utc_naive(singapore_time) == datetime(2026, 3, 18, 15, 40)


def test_billing_today_uses_configured_timezone(monkeypatch):
    timeutils.billing_timezone.cache_clear()
    monkeypatch.setattr(timeutils, "get_settings", lambda: SimpleNamespace(billing_timezone="Asia/Singapore"))
    monkeypatch.setattr(timeutils, "utcnow", lambda: datetime(2026, 3, 31, 16, 30, tzinfo=timezone.utc))

    assert timeutils.billing_today() == date(2026, 4, 1)

    timeutils.billing_timezone.cache_clear()


def test_as_billing_time_uses_configured_timezone(monkeypatch):
    timeutils.billing_timezone.cache_clear()
    monkeypatch.setattr(timeutils, "get_settings", lambda: SimpleNamespace(billing_timezone="Asia/Singapore"))

    local_time = timeutils.as_billing_time(datetime(2026, 3, 31, 16, 30, tzinfo=timezone.utc))

    assert local_time.date() == date(2026, 4, 1)
    assert local_time.hour == 0
    assert local_time.minute == 30

    timeutils.billing_timezone.cache_clear()


def test_utcnow_naive_drops_timezone_after_normalizing_to_utc(monkeypatch):
    monkeypatch.setattr(timeutils, "utcnow", lambda: datetime(2026, 4, 7, 10, 45, tzinfo=timezone.utc))

    assert timeutils.utcnow_naive() == datetime(2026, 4, 7, 10, 45)
