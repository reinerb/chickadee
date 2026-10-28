from datetime import UTC, datetime, timedelta
from typing import Any

from pyairtable.api.types import RecordDict

from chickadee.flags import (
    BROKEN_LINKS,
    DOWN,
    KEY_POINT_BURIED,
    LOW_SCORE_FLAG,
    MISSING_METADATA,
    STALE,
    facts_from_record,
    find_flags,
    flag_update,
    last_updated,
)

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
YEAR = timedelta(days=365)

HEALTHY: dict[str, Any] = {
    "Content hash": "abc",
    "Status": "Up",
    "Broken link count": 0,
    "SEO score": 8,
    "Current title": "Title",
    "Current description": "Description",
    "Key point up front": "Yes",
    "Page modified at": "2026-09-01T00:00:00.000Z",
}


def page(**fields: Any) -> RecordDict:
    return {"id": "rec1", "createdTime": "2026-10-01T00:00:00.000Z", "fields": fields}


def flags_for(
    fields: dict[str, Any], created: str = "2026-10-01T00:00:00.000Z"
) -> list[str]:
    record: RecordDict = {"id": "recA", "createdTime": created, "fields": fields}
    return find_flags(facts_from_record(record), NOW, YEAR)


def test_healthy_page_has_no_flags():
    assert flags_for(HEALTHY) == []


def test_each_rule_raises_its_own_flag():
    assert flags_for(HEALTHY | {"Status": "Down"}) == [DOWN]
    assert flags_for(HEALTHY | {"Broken link count": 2}) == [BROKEN_LINKS]
    assert flags_for(HEALTHY | {"Key point up front": "No"}) == [KEY_POINT_BURIED]

    no_description = {k: v for k, v in HEALTHY.items() if k != "Current description"}
    assert flags_for(no_description) == [MISSING_METADATA]


def test_low_score_threshold():
    assert flags_for(HEALTHY | {"SEO score": 4}) == [LOW_SCORE_FLAG]
    assert flags_for(HEALTHY | {"SEO score": 5}) == []


def test_staleness_uses_the_most_recent_date():
    old = HEALTHY | {"Page modified at": "2024-01-01T00:00:00.000Z"}

    assert flags_for(old) == [STALE]
    assert flags_for(old | {"Content changed at": "2026-10-01T00:00:00.000Z"}) == []


def test_no_evidence_means_no_flags():
    assert flags_for({}) == []
    assert flags_for({}, created="2020-01-01T00:00:00.000Z") == [STALE]


def test_only_real_changes_are_written():
    current = {"Attention": [STALE, DOWN], "Attention count": 2}

    assert flag_update(current, [DOWN, STALE]) is None
    assert flag_update(current, []) == {"Attention": [], "Attention count": 0}
    assert flag_update({}, []) == {"Attention": [], "Attention count": 0}


def test_sitemap_date_stands_in_when_nothing_better_is_known():
    assert last_updated(page()) == datetime(2026, 10, 1, tzinfo=UTC)
    assert last_updated(
        page(**{"Sitemap lastmod": "2024-03-01T00:00:00+00:00"})
    ) == datetime(2024, 3, 1, tzinfo=UTC)


def test_page_date_beats_a_newer_sitemap_date():
    record = page(
        **{
            "Sitemap lastmod": "2026-10-20T00:00:00+00:00",
            "Page modified at": "2023-01-01T00:00:00+00:00",
        }
    )

    assert last_updated(record) == datetime(2023, 1, 1, tzinfo=UTC)
