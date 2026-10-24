from datetime import UTC, datetime

from content_monitor.checker import CheckResult
from content_monitor.store import to_check_fields

CHECKED_AT = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def test_successful_check_includes_all_fields():
    result = CheckResult(
        url="https://example.com",
        ok=True,
        status_code=200,
        response_time_ms=123,
        error=None,
    )

    fields = to_check_fields("recABC123", result, CHECKED_AT)

    assert fields == {
        "Page": ["recABC123"],
        "Checked at": "2026-10-24T12:00:00+00:00",
        "Status code": 200,
        "Response time (ms)": 123,
        "Ok": True,
    }


def test_connection_failure_omits_missing_values():
    result = CheckResult(
        url="https://nope.invalid",
        ok=False,
        status_code=None,
        response_time_ms=None,
        error="ConnectError: name resolution failed",
    )

    fields = to_check_fields("recABC123", result, CHECKED_AT)

    assert "Status code" not in fields
    assert "Response time (ms)" not in fields
    assert fields["Ok"] is False
    assert fields["Error"] == "ConnectError: name resolution failed"
