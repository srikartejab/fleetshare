from datetime import datetime, timedelta, timezone

from fleetshare_common.timeutils import as_utc_naive, iso


def test_iso_serializes_naive_utc_as_z():
    assert iso(datetime(2026, 3, 18, 15, 40)) == "2026-03-18T15:40:00Z"


def test_iso_normalizes_aware_datetimes_to_utc():
    singapore_time = datetime(2026, 3, 18, 23, 40, tzinfo=timezone(timedelta(hours=8)))
    assert iso(singapore_time) == "2026-03-18T15:40:00Z"
    assert as_utc_naive(singapore_time) == datetime(2026, 3, 18, 15, 40)
