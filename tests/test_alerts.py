import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from chickadee.alerts import (
    PendingAlert,
    build_alert,
    build_test_alert,
    decide_alert,
    deliver_alerts,
    down_since,
)
from chickadee.checker import CheckResult

NOW = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
EARLIER = NOW - timedelta(hours=2, minutes=15)


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


# When to alert


@pytest.mark.parametrize(
    ("alerted", "status", "action"),
    [
        (None, "Up", "record"),
        (None, "Down", "send"),
        ("Up", "Up", "none"),
        ("Up", "Down", "send"),
        ("Down", "Down", "none"),
        ("Down", "Up", "send"),
    ],
)
def test_alerts_follow_what_was_last_announced(alerted, status, action):
    assert decide_alert(alerted, status) == action


def test_outage_start_is_known_only_when_it_can_be():
    # Still down, or recovering: the outage started when Status last changed.
    assert down_since("Down", EARLIER, False, NOW) == EARLIER
    assert down_since("Down", EARLIER, True, NOW) == EARLIER
    # Just went down: the outage starts now.
    assert down_since("Up", EARLIER, False, NOW) == NOW
    # A retried recovery: Status since is when it came back up, not when it went down.
    assert down_since("Up", EARLIER, True, NOW) is None


# What alerts say


def test_new_outage_reports_status_code_without_a_duration():
    alert = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=False, status_code=503),
        down_since=NOW,
        checked_at=NOW,
    )

    assert alert["event"] == "down"
    assert alert["duration"] is None
    assert alert["message"].startswith("Library is down (503).")


def test_down_alert_falls_back_to_error_when_no_response():
    alert = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=False, status_code=None, error="ConnectTimeout"),
        down_since=NOW,
        checked_at=NOW,
    )

    assert "(ConnectTimeout)" in alert["message"]


def test_retried_down_alert_says_how_long_the_page_has_been_down():
    alert = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=False, status_code=503),
        down_since=EARLIER,
        checked_at=NOW,
    )

    assert alert["duration"] == "2h 15m"
    assert "has been down for 2h 15m (503)" in alert["message"]


def test_recovery_alert_includes_downtime():
    alert = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=True),
        down_since=EARLIER,
        checked_at=NOW,
    )

    assert alert["event"] == "recovered"
    assert alert["duration"] == "2h 15m"
    assert "after 2h 15m down" in alert["message"]


def test_recovery_with_unknown_start_leaves_out_the_duration():
    alert = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=True),
        down_since=None,
        checked_at=NOW,
    )

    assert alert["duration"] is None
    assert alert["message"].startswith("Library is back up. ")


def test_every_alert_has_the_same_shape():
    down = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=False, status_code=None, error="ConnectTimeout"),
        down_since=NOW,
        checked_at=NOW,
    )
    recovered = build_alert(
        name="Library",
        url="https://example.org/",
        result=make_result(ok=True),
        down_since=EARLIER,
        checked_at=NOW,
    )

    assert down.keys() == recovered.keys()


def test_test_alerts_cover_both_events_with_the_same_shape():
    down = build_test_alert(recovered=False, now=NOW)
    recovered = build_test_alert(recovered=True, now=NOW)

    assert (down["event"], recovered["event"]) == ("down", "recovered")
    assert down["test"] and recovered["test"]
    assert down.keys() == recovered.keys()


# Delivering alerts


def test_only_delivered_alerts_are_reported_as_delivered():
    def handler(request: httpx.Request) -> httpx.Response:
        page = json.loads(request.content)["page"]
        return httpx.Response(500 if page == "Broken" else 200)

    pending = [
        PendingAlert("rec1", "Down", {"page": "Library"}),
        PendingAlert("rec2", "Down", {"page": "Broken"}),
        PendingAlert("rec3", "Up", {"page": "Blog"}),
    ]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        delivered = deliver_alerts(client, "https://hooks.example.org/x", pending)

    assert [alert.record_id for alert in delivered] == ["rec1", "rec3"]
