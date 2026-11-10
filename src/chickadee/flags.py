from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pyairtable.api.types import RecordDict

from chickadee.models import Flag

LOW_SCORE = 4

DOWN: Flag = "Down"
BROKEN_LINKS: Flag = "Has broken links"
STALE: Flag = "Stale"
LOW_SCORE_FLAG: Flag = "Low SEO score"
MISSING_METADATA: Flag = "Missing metadata"
KEY_POINT_BURIED: Flag = "Key point buried"

ALL_FLAGS: tuple[Flag, ...] = (
    DOWN,
    BROKEN_LINKS,
    STALE,
    LOW_SCORE_FLAG,
    MISSING_METADATA,
    KEY_POINT_BURIED,
)


@dataclass(frozen=True)
class PageFacts:
    audited: bool
    down: bool
    broken_links: int
    seo_score: int | None
    has_title: bool
    has_description: bool
    key_point_buried: bool
    last_updated: datetime


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)

    return None


def last_updated(record: RecordDict) -> datetime:
    fields = record["fields"]
    observed = [
        moment
        for moment in (
            _parse_time(fields.get("Page modified at")),
            _parse_time(fields.get("Content changed at")),
        )
        if moment is not None
    ]
    if observed:
        return max(observed)
    return _parse_time(fields.get("Sitemap lastmod")) or datetime.fromisoformat(
        record["createdTime"]
    )


def facts_from_record(record: RecordDict) -> PageFacts:
    fields = record["fields"]
    return PageFacts(
        audited=bool(fields.get("Content hash")),
        down=fields.get("Status") == "Down",
        broken_links=fields.get("Broken link count") or 0,
        seo_score=fields.get("SEO score"),
        has_title=bool(fields.get("Current title")),
        has_description=bool(fields.get("Current description")),
        key_point_buried=fields.get("Key point up front") == "No",
        last_updated=last_updated(record),
    )


def find_flags(facts: PageFacts, now: datetime, stale_after: timedelta) -> list[str]:
    flags: list[str] = []
    if facts.down:
        flags.append(DOWN)
    if facts.broken_links > 0:
        flags.append(BROKEN_LINKS)
    if now - facts.last_updated > stale_after:
        flags.append(STALE)
    if facts.seo_score is not None and facts.seo_score <= LOW_SCORE:
        flags.append(LOW_SCORE_FLAG)
    if facts.audited and not (facts.has_title and facts.has_description):
        flags.append(MISSING_METADATA)
    if facts.key_point_buried:
        flags.append(KEY_POINT_BURIED)
    return flags


def flag_update(
    fields: Mapping[str, Any], flags: Sequence[str]
) -> dict[str, Any] | None:
    unchanged = set(fields.get("Attention") or []) == set(flags) and fields.get(
        "Attention count"
    ) == len(flags)
    if unchanged:
        return None
    return {"Attention": list(flags), "Attention count": len(flags)}
