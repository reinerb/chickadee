from datetime import UTC, datetime
from typing import Any

from pyairtable.api.types import RecordDict

from chickadee.history import describe_duration, find_events, latest_status


def make_check(page_id: str, at: str, ok: bool) -> RecordDict:
    fields: dict[str, Any] = {
        "Page": [page_id],
        "Checked at": at,
        "Status code": 200 if ok else 503,
    }
    if ok:
        fields["Ok"] = True
    return {"id": f"rec-{page_id}-{at}", "createdTime": at, "fields": fields}


def test_changes_log_reports_outage_and_recovery():
    checks = [
        make_check("recA", "2026-10-20T10:00:00.000Z", ok=True),
        make_check("recA", "2026-10-21T10:00:00.000Z", ok=False),
        make_check("recA", "2026-10-21T14:00:00.000Z", ok=True),
    ]

    assert [event.status for event in find_events(checks)] == ["Down", "Up"]


def test_repeated_checks_collapse_into_single_events():
    checks = [
        make_check("recA", f"2026-10-20T{hour:02d}:00:00.000Z", ok=ok)
        for hour, ok in enumerate([True, False, False, True, True])
    ]

    assert [event.status for event in find_events(checks)] == ["Down", "Up"]


def test_pages_are_tracked_separately():
    checks = [
        make_check("recA", "2026-10-20T10:00:00.000Z", ok=False),
        make_check("recB", "2026-10-20T11:00:00.000Z", ok=True),
    ]

    events = find_events(checks)

    assert [(event.page_id, event.status) for event in events] == [("recA", "Down")]


def test_input_order_does_not_matter():
    checks = [
        make_check("recA", "2026-10-21T14:00:00.000Z", ok=True),
        make_check("recA", "2026-10-21T10:00:00.000Z", ok=False),
    ]

    assert [event.status for event in find_events(checks)] == ["Down", "Up"]


def test_recovery_from_an_outage_before_the_week_is_an_event():
    week = [make_check("recA", "2026-10-22T10:00:00.000Z", ok=True)]

    assert find_events(week) == []
    events = find_events(week, {"recA": "Down"})
    assert [(event.page_id, event.status) for event in events] == [("recA", "Up")]


def test_page_already_down_doesnt_go_down_again():
    week = [make_check("recA", "2026-10-22T10:00:00.000Z", ok=False)]

    assert find_events(week, {"recA": "Down"}) == []


def test_latest_status_stops_once_every_page_is_found():
    checks = [
        make_check("recA", "2026-10-19T00:00:00.000Z", ok=False),
        make_check("recA", "2026-10-10T00:00:00.000Z", ok=True),
        make_check("recB", "2026-10-05T00:00:00.000Z", ok=True),
        make_check("recC", "2026-10-01T00:00:00.000Z", ok=False),
    ]
    remaining = iter(checks)

    assert latest_status(remaining, {"recA", "recB"}) == {"recA": "Down", "recB": "Up"}
    assert next(remaining) is checks[3]


def test_durations_are_formatted_by_size():
    start = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)

    assert (
        describe_duration(start, datetime(2026, 10, 22, 13, 0, tzinfo=UTC)) == "2d 3h"
    )
    assert (
        describe_duration(start, datetime(2026, 10, 20, 12, 15, tzinfo=UTC)) == "2h 15m"
    )
    assert describe_duration(start, datetime(2026, 10, 20, 10, 45, tzinfo=UTC)) == "45m"
