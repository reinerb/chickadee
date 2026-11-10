from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from chickadee.models import Flag, Page

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
class FlagsReport:
    updated: int
    counts: Counter[Flag]


class FlagPages(Protocol):
    """What run_flags needs from wherever pages are kept."""

    def active(self) -> Iterable[Page]: ...

    def save_flags(self, flags: Mapping[str, Sequence[Flag]]) -> None: ...


def last_updated(page: Page) -> datetime:
    observed = [
        moment
        for moment in (page.page_modified_at, page.content_changed_at)
        if moment is not None
    ]
    if observed:
        return max(observed)
    return page.sitemap_lastmod or page.created_at


def find_flags(page: Page, now: datetime, stale_after: timedelta) -> list[Flag]:
    flags: list[Flag] = []
    if page.status == "Down":
        flags.append(DOWN)
    if (page.broken_link_count or 0) > 0:
        flags.append(BROKEN_LINKS)
    if now - last_updated(page) > stale_after:
        flags.append(STALE)
    if page.seo_score is not None and page.seo_score <= LOW_SCORE:
        flags.append(LOW_SCORE_FLAG)
    if page.content_hash and not (page.current_title and page.current_description):
        flags.append(MISSING_METADATA)
    if page.key_point_up_front is False:
        flags.append(KEY_POINT_BURIED)
    return flags


def flags_changed(page: Page, flags: Sequence[Flag]) -> bool:
    return set(page.attention) != set(flags) or page.attention_count != len(flags)


def run_flags(
    pages: FlagPages, *, now: datetime, stale_after: timedelta
) -> FlagsReport:
    changes: dict[str, list[Flag]] = {}
    counts: Counter[Flag] = Counter()

    for page in pages.active():
        flags = find_flags(page, now, stale_after)
        counts.update(flags)
        if flags_changed(page, flags):
            changes[page.id] = flags

    pages.save_flags(changes)
    return FlagsReport(updated=len(changes), counts=counts)
