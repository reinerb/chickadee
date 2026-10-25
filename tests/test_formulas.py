from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from content_monitor.formulas import checked_after, checked_before


def test_formula_uses_utc_timestamp():
    cutoff = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    assert checked_before(cutoff) == (
        "IS_BEFORE({Checked at}, DATETIME_PARSE('2026-10-10T12:00:00Z'))"
    )


def test_formula_converts_other_timezones_to_utc():
    cutoff = datetime(2026, 10, 10, 8, 0, tzinfo=ZoneInfo("America/New_York"))

    assert "2026-10-10T12:00:00Z" in checked_before(cutoff)


def test_checked_after_uses_is_after():
    cutoff = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    assert checked_after(cutoff) == (
        "IS_AFTER({Checked at}, DATETIME_PARSE('2026-10-10T12:00:00Z'))"
    )
