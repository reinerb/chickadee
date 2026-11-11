import logging
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import httpx
from anthropic.types.messages.batch_create_params import Request

from chickadee.checker import fetch_html
from chickadee.errors import ConfigError
from chickadee.extractor import (
    ContentChange,
    PageContent,
    classify_change,
    content_hash,
    extract_content,
)
from chickadee.models import Page
from chickadee.reviewer import (
    ReviewState,
    Topic,
    build_review_request,
    build_system_prompt,
    review_schema,
    review_state,
    review_version,
)

log = logging.getLogger(__name__)

NEEDS_REVIEW = ("new", "changed", "setup")
SAVE_EVERY = 25


@dataclass(frozen=True)
class ReviewSetup:
    system: str
    schema: dict[str, Any]
    version: str


def review_setup(topics: Sequence[Topic], context: str | None) -> ReviewSetup:
    if not topics:
        raise ConfigError("Add at least one topic to the Topics table before auditing.")

    ordered = sorted(topics, key=lambda topic: topic.name.casefold())
    system = build_system_prompt(ordered, context=context)
    schema = review_schema([topic.name for topic in ordered])
    return ReviewSetup(system, schema, review_version(system, schema))


@dataclass(frozen=True)
class ContentUpdate:
    page_id: str
    content: PageContent
    content_hash: str
    change: ContentChange
    # Set for pages reviewed before review versions were tracked.
    review_version: str | None = None


class AuditPages(Protocol):
    """What run_audit needs from wherever pages are kept."""

    def active(self) -> Iterable[Page]: ...

    def save_content(
        self, updates: Sequence[ContentUpdate], audited_at: datetime
    ) -> None: ...


@dataclass(frozen=True)
class AuditReport:
    changes: Counter[ContentChange]
    states: Counter[ReviewState]
    requests: tuple[Request, ...]


def run_audit(
    pages: AuditPages,
    client: httpx.Client,
    setup: ReviewSetup,
    *,
    ignore: str | None,
    review_all: bool,
    audited_at: datetime,
    save_every: int = SAVE_EVERY,
    sleep: Callable[[float], None] = time.sleep,
) -> AuditReport:
    updates: list[ContentUpdate] = []
    requests: list[Request] = []
    changes: Counter[ContentChange] = Counter()
    states: Counter[ReviewState] = Counter()

    for page in pages.active():
        sleep(1)
        response = fetch_html(client, page.url)
        if response is None:
            continue

        content = extract_content(response.text, ignore=ignore)
        current = content_hash(content)
        change = classify_change(page.content_hash, current)
        state = review_state(
            page.reviewed_hash, current, page.review_version, setup.version
        )
        changes[change] += 1
        states[state] += 1

        updates.append(
            ContentUpdate(
                page.id,
                content,
                current,
                change,
                review_version=setup.version if state == "baseline" else None,
            )
        )

        review = review_all or state in NEEDS_REVIEW
        if review:
            requests.append(
                build_review_request(
                    page.id,
                    current,
                    page.url,
                    content,
                    system=setup.system,
                    schema=setup.schema,
                    version=setup.version,
                )
            )
        log.info(
            "%-9s %-6s %-8s %s", change, "review" if review else "skip", state, page.url
        )

        if len(updates) >= save_every:
            pages.save_content(updates, audited_at)
            updates = []

    if updates:
        pages.save_content(updates, audited_at)
    return AuditReport(changes, states, tuple(requests))


class ReviewSubmitter(Protocol):
    def submit(self, requests: Sequence[Request]) -> str: ...


class BatchLog(Protocol):
    def record(self, batch_id: str, submitted_at: datetime, pages: int) -> None: ...


def submit_reviews(
    claude: ReviewSubmitter,
    batches: BatchLog,
    requests: Sequence[Request],
    submitted_at: datetime,
) -> str:
    """Send the reviews to Claude, and note the batch so collect can find it."""
    batch_id = claude.submit(requests)
    batches.record(batch_id, submitted_at, len(requests))
    return batch_id
