"""Data types shared across Chickadee.

No I/O, and no Airtable column names. airtable.py maps those.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Status = Literal["Up", "Down"]
LinkStatus = Literal["ok", "broken", "unverified"]
Flag = Literal[
    "Down",
    "Has broken links",
    "Stale",
    "Low SEO score",
    "Missing metadata",
    "Key point buried",
]


@dataclass(frozen=True)
class LinkResult:
    url: str
    status: LinkStatus
    detail: str


class Page(BaseModel):
    """A row of the Pages table, as the rest of Chickadee sees it.

    Airtable leaves empty fields out of its responses, so every column
    but URL is optional, and None means "not set yet".
    airtable.PAGE_COLUMNS maps each attribute to its column.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: datetime

    # You, or import
    url: str
    name: str | None = None
    active: bool = False  # unchecked boxes are left out
    sitemap_lastmod: datetime | None = None

    # uptime
    status: Status | None = None
    status_since: datetime | None = None
    last_checked: datetime | None = None
    last_status_code: int | None = None
    last_response_time_ms: int | None = None
    alerted_status: Status | None = None

    # audit
    current_title: str | None = None
    current_description: str | None = None
    word_count: int | None = None
    page_modified_at: datetime | None = None
    content_hash: str | None = None
    content_changed_at: datetime | None = None

    # collect
    content_summary: str | None = None
    key_point: str | None = None
    # Stored as "Yes" or "No"; Pydantic parses those to bool.
    key_point_up_front: bool | None = None
    topic_ids: tuple[str, ...] = ()  # linked Topics rows
    seo_score: int | None = None
    seo_summary: str | None = None
    suggested_title: str | None = None
    suggested_description: str | None = None
    seo_issues: str | None = None
    last_audited: datetime | None = None
    reviewed_hash: str | None = None
    review_version: str | None = None

    # links
    broken_links: str | None = None
    unverified_links: str | None = None
    broken_link_count: int | None = None
    links_checked_at: datetime | None = None

    # flags
    attention: tuple[Flag, ...] = ()
    attention_count: int | None = None

    @property
    def label(self) -> str:
        return self.name or self.url
