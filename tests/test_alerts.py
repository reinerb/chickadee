from datetime import UTC, datetime

from content_monitor.alerts import build_alert, should_alert
from content_monitor.checker import CheckResult

NOW = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)


def make_result(
    ok: bool, status_code: int | None = 200, error: str | None = None
) -> CheckResult:
    return CheckResult(
        url="https://example.org/",
        ok=ok,
        status_code=status_code,
        response_time_ms=100,
        error=error,
    )


def test_alert_rules():
    assert should_alert(None, "Down")
    assert not should_alert(None, "Up")
    assert should_alert("Up", "Down")
    assert should_alert("Down", "Up")
    assert not should_alert("Up", "Up")


def test_down_alert_reports_status_code():
    alert = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=False, status_code=503),
        previous_since=None,
        checked_at=NOW,
    )

    assert alert["event"] == "down"
    assert "(503)" in alert["message"]


def test_down_alert_falls_back_to_error_when_no_response():
    alert = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=False, status_code=None, error="ConnectTimeout"),
        previous_since=None,
        checked_at=NOW,
    )

    assert "(ConnectTimeout)" in alert["message"]


def test_recovery_alert_includes_downtime():
    alert = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=True),
        previous_since=datetime(2026, 10, 24, 12, 45, tzinfo=UTC),
        checked_at=NOW,
    )

    assert alert["event"] == "recovered"
    assert alert["duration"] == "2h 15m"
    assert "after 2h 15m down" in alert["message"]
