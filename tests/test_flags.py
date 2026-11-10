from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, get_args

from chickadee.flags import (
    ALL_FLAGS,
    BROKEN_LINKS,
    DOWN,
    KEY_POINT_BURIED,
    LOW_SCORE_FLAG,
    MISSING_METADATA,
    STALE,
    find_flags,
    flags_changed,
    last_updated,
    run_flags,
)
from chickadee.models import Flag, Page

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
CREATED = datetime(2026, 10, 1, tzinfo=UTC)
YEAR = timedelta(days=365)

HEALTHY: dict[str, Any] = {
    "content_hash": "abc",
    "status": "Up",
    "broken_link_count": 0,
    "seo_score": 8,
    "current_title": "Title",
    "current_description": "Description",
    "key_point_up_front": True,
    "page_modified_at": datetime(2026, 9, 1, tzinfo=UTC),
}


def page(
    *, created: datetime = CREATED, record_id: str = "rec1", **fields: Any
) -> Page:
    return Page(id=record_id, created_at=created, url="https://example.org", **fields)


def flags_for(fields: dict[str, Any], created: datetime = CREATED) -> list[Flag]:
    return find_flags(page(created=created, **fields), NOW, YEAR)


def test_healthy_page_has_no_flags():
    assert flags_for(HEALTHY) == []


def test_each_rule_raises_its_own_flag():
    assert flags_for(HEALTHY | {"status": "Down"}) == [DOWN]
    assert flags_for(HEALTHY | {"broken_link_count": 2}) == [BROKEN_LINKS]
    assert flags_for(HEALTHY | {"key_point_up_front": False}) == [KEY_POINT_BURIED]
    assert flags_for(HEALTHY | {"current_description": None}) == [MISSING_METADATA]


def test_low_score_threshold():
    assert flags_for(HEALTHY | {"seo_score": 4}) == [LOW_SCORE_FLAG]
    assert flags_for(HEALTHY | {"seo_score": 5}) == []


def test_staleness_uses_the_most_recent_date():
    old = HEALTHY | {"page_modified_at": datetime(2024, 1, 1, tzinfo=UTC)}

    assert flags_for(old) == [STALE]
    assert (
        flags_for(old | {"content_changed_at": datetime(2026, 10, 1, tzinfo=UTC)}) == []
    )


def test_no_evidence_means_no_flags():
    assert flags_for({}) == []
    assert flags_for({}, created=datetime(2020, 1, 1, tzinfo=UTC)) == [STALE]


def test_only_real_changes_are_written():
    current = page(attention=(STALE, DOWN), attention_count=2)

    assert not flags_changed(current, [DOWN, STALE])
    assert flags_changed(current, [])
    assert flags_changed(page(), [])  # never flagged: count is still empty


def test_sitemap_date_stands_in_when_nothing_better_is_known():
    assert last_updated(page()) == CREATED
    assert last_updated(
        page(sitemap_lastmod=datetime(2024, 3, 1, tzinfo=UTC))
    ) == datetime(2024, 3, 1, tzinfo=UTC)


def test_page_date_beats_a_newer_sitemap_date():
    record = page(
        sitemap_lastmod=datetime(2026, 10, 20, tzinfo=UTC),
        page_modified_at=datetime(2023, 1, 1, tzinfo=UTC),
    )

    assert last_updated(record) == datetime(2023, 1, 1, tzinfo=UTC)


def test_all_flags_lists_every_flag_once():
    assert sorted(ALL_FLAGS) == sorted(get_args(Flag))


class FakePages:
    def __init__(self, *pages: Page) -> None:
        self.pages = pages
        self.saved: dict[str, Sequence[Flag]] = {}

    def active(self) -> tuple[Page, ...]:
        return self.pages

    def save_flags(self, flags: Mapping[str, Sequence[Flag]]) -> None:
        self.saved = dict(flags)


def test_run_flags_saves_only_pages_whose_flags_changed():
    already_flagged: dict[str, Any] = HEALTHY | {
        "status": "Down",
        "attention": (DOWN,),
        "attention_count": 1,
    }
    newly_broken: dict[str, Any] = HEALTHY | {"broken_link_count": 3}
    store = FakePages(
        page(record_id="recSame", **already_flagged),
        page(record_id="recNew", **newly_broken),
    )

    report = run_flags(store, now=NOW, stale_after=YEAR)

    assert store.saved == {"recNew": [BROKEN_LINKS]}
    assert report.updated == 1
    assert report.counts[DOWN] == 1
    assert report.counts[BROKEN_LINKS] == 1
