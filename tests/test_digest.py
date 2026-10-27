from datetime import UTC, datetime, timedelta
from typing import Any

from pyairtable.api.types import RecordDict

from chickadee.digest import (
    changed_pages,
    claude_input,
    needs_attention,
    new_pages,
    page_item,
    render_digest,
    uptime_lines,
)
from chickadee.history import Event

NOW = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
SINCE = NOW - timedelta(days=7)
LONG_AGO = "2026-01-01T00:00:00.000Z"


def record(
    fields: dict[str, Any], created: str = LONG_AGO, record_id: str = "recA"
) -> RecordDict:
    return {
        "id": record_id,
        "createdTime": created,
        "fields": {"URL": "https://example.org/a/"} | fields,
    }


def test_new_and_changed_pages_dont_overlap():
    added = record(
        {"Name": "Added", "Content changed at": "2026-10-25T00:00:00.000Z"},
        created="2026-10-22T00:00:00.000Z",
    )
    edited = record(
        {"Name": "Edited", "Content changed at": "2026-10-24T00:00:00.000Z"}
    )
    quiet = record({"Name": "Quiet", "Content changed at": "2026-09-01T00:00:00.000Z"})

    assert [item.name for item in new_pages([added, edited, quiet], SINCE)] == ["Added"]
    assert [item.name for item in changed_pages([added, edited, quiet], SINCE)] == [
        "Edited"
    ]


def test_summary_is_shown_only_for_the_reviewed_version():
    current = record(
        {"Content hash": "abc", "Reviewed hash": "abc", "Content summary": "S"}
    )
    pending = record(
        {"Content hash": "new", "Reviewed hash": "abc", "Content summary": "S"}
    )

    assert page_item(current).summary == "S"
    assert page_item(pending).summary is None


def test_attention_is_sorted_and_flags_are_normalized():
    one_flag = record({"Name": "b", "Attention": ["Stale"]}, record_id="r1")
    two_flags = record(
        {"Name": "a", "Attention": ["Stale", "Down", "Bogus"]}, record_id="r2"
    )
    clean = record({"Name": "c"}, record_id="r3")

    flagged, counts = needs_attention([one_flag, two_flags, clean])

    assert [(item.name, item.flags) for item in flagged] == [
        ("a", ("Down", "Stale")),
        ("b", ("Stale",)),
    ]
    assert counts["Stale"] == 2


def test_digest_shows_empty_sections_and_limits_long_lists():
    flagged = [
        page_item(record({"Name": f"P{n}", "Attention": ["Stale"]})) for n in range(3)
    ]

    digest = render_digest(
        since=SINCE,
        until=NOW,
        overview="A quiet week.",
        new=[],
        changed=[],
        flagged=flagged,
        flag_counts={"Stale": 3},
        down=[],
        events=[],
        limit=2,
    )

    assert digest.startswith(
        "# Content digest: Oct 20 to Oct 27, 2026\n\nA quiet week."
    )
    assert "None this week." in digest
    assert "...and 1 more in the Needs attention view" in digest
    assert "Every page is up." in digest


def test_uptime_lines_use_calculated_durations():
    down = record(
        {
            "Name": "Library",
            "Status": "Down",
            "Status since": "2026-10-27T07:45:00.000Z",
            "Last status code": 503,
        }
    )
    events = [
        Event(
            "recA",
            datetime(2026, 10, 22, 14, 17, tzinfo=UTC),
            "Down",
            None,
            "ConnectTimeout",
        )
    ]

    now_down, happened = uptime_lines([down], events, {"recA": "Library"}, NOW)

    assert now_down == ["Library: down for 2h 15m (503)"]
    assert happened == ["Oct 22, 14:17 UTC: Library went down (ConnectTimeout)"]


def test_empty_sections_are_marked_for_claude():
    assert claude_input([], [], [], [], []).count("(none)") == 5
