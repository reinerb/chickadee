import argparse
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from content_monitor.prune import older_than_formula, positive_int


def test_formula_uses_utc_timestamp():
    cutoff = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    assert older_than_formula(cutoff) == (
        "IS_BEFORE({Checked at}, DATETIME_PARSE('2026-10-10T12:00:00Z'))"
    )


def test_formula_converts_other_timezones_to_utc():
    cutoff = datetime(2026, 10, 10, 8, 0, tzinfo=ZoneInfo("America/New_York"))

    assert "2026-10-10T12:00:00Z" in older_than_formula(cutoff)


def test_zero_days_is_rejected():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("0")
