from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from chickadee.digest import (
    build_digest,
    changed_pages,
    claude_input,
    needs_attention,
    new_pages,
    page_item,
    render_digest,
    uptime_lines,
)
from chickadee.history import Event
from chickadee.models import Check, Page

NOW = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
SINCE = NOW - timedelta(days=7)
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


def page(
    *, created: datetime = LONG_AGO, record_id: str = "recA", **fields: Any
) -> Page:
    return Page(
        id=record_id, created_at=created, url="https://example.org/a/", **fields
    )


def test_new_and_changed_pages_dont_overlap():
    added = page(
        name="Added",
        content_changed_at=datetime(2026, 10, 25, tzinfo=UTC),
        created=datetime(2026, 10, 22, tzinfo=UTC),
    )
    edited = page(name="Edited", content_changed_at=datetime(2026, 10, 24, tzinfo=UTC))
    quiet = page(name="Quiet", content_changed_at=datetime(2026, 9, 1, tzinfo=UTC))

    assert [item.name for item in new_pages([added, edited, quiet], SINCE)] == ["Added"]
    assert [item.name for item in changed_pages([added, edited, quiet], SINCE)] == [
        "Edited"
    ]


def test_summary_is_shown_only_for_the_reviewed_version():
    current = page(content_hash="abc", reviewed_hash="abc", content_summary="S")
    pending = page(content_hash="new", reviewed_hash="abc", content_summary="S")

    assert page_item(current).summary == "S"
    assert page_item(pending).summary is None


def test_attention_is_sorted_and_flags_are_normalized():
    one_flag = page(name="b", attention=["Stale"], record_id="r1")
    two_flags = page(name="a", attention=["Stale", "Down", "Bogus"], record_id="r2")
    clean = page(name="c", record_id="r3")

    flagged, counts = needs_attention([one_flag, two_flags, clean])

    assert [(item.name, item.flags) for item in flagged] == [
        ("a", ("Down", "Stale")),
        ("b", ("Stale",)),
    ]
    assert counts["Stale"] == 2


def test_digest_shows_empty_sections_and_limits_long_lists():
    flagged = [page_item(page(name=f"P{n}", attention=["Stale"])) for n in range(3)]

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
    down = page(
        name="Library",
        status="Down",
        status_since=datetime(2026, 10, 27, 7, 45, tzinfo=UTC),
        last_status_code=503,
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


class FakePages:
    def __init__(self, *pages: Page) -> None:
        self.pages = list(pages)

    def all(self) -> list[Page]:
        return self.pages


class FakeChecks:
    def __init__(self, week: list[Check], earlier: list[Check]) -> None:
        self.week = week
        self.earlier = earlier

    def since(self, start: datetime) -> list[Check]:
        return self.week

    def newest_before(self, cutoff: datetime) -> Iterator[Check]:
        return iter(self.earlier)


def test_build_digest_puts_the_week_together():
    library = page(
        name="Library",
        active=True,
        created=datetime(2026, 10, 22, tzinfo=UTC),
        record_id="recLib",
    )
    retired = page(name="Old page", active=False, record_id="recOld")
    checks = FakeChecks(
        week=[
            Check("recOld", datetime(2026, 10, 23, 9, 0, tzinfo=UTC), ok=False),
            Check("recLib", datetime(2026, 10, 24, 9, 0, tzinfo=UTC), ok=False),
        ],
        earlier=[Check("recLib", datetime(2026, 10, 19, tzinfo=UTC), ok=True)],
    )
    seen: list[str] = []

    def overview(content: str) -> str:
        seen.append(content)
        return "A busy week."

    digest = build_digest(
        FakePages(library, retired),
        checks,
        since=SINCE,
        until=NOW,
        overview=overview,
    )

    assert "A busy week." in digest.markdown
    assert "Library went down" in digest.markdown
    # A page switched off since its outage is still named, not "(unknown page)".
    assert "Old page went down" in digest.markdown
    assert "Library" in seen[0]
    assert (digest.new, digest.changed, digest.down) == (1, 0, 0)
    assert digest.payload(test=True)["subject"].startswith("[TEST] ")
