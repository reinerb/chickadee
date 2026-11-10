from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from anthropic.types.messages.batch_create_params import Request

from chickadee.audit import (
    ContentUpdate,
    review_setup,
    run_audit,
    submit_reviews,
)
from chickadee.errors import ConfigError
from chickadee.extractor import content_hash, extract_content
from chickadee.models import Page
from chickadee.reviewer import Topic

NOW = datetime(2026, 11, 10, tzinfo=UTC)
TOPICS = [Topic("Policy"), Topic("Fish", "Anything about fish.")]
SETUP = review_setup(TOPICS, context=None)

NEW_HTML = (
    "<html><head><title>New</title></head><body><main>New page.</main></body></html>"
)
SAME_HTML = (
    "<html><head><title>Same</title></head><body><main>Unchanged.</main></body></html>"
)
SAME_HASH = content_hash(extract_content(SAME_HTML, ignore=None))


class FakePages:
    def __init__(self, *pages: Page) -> None:
        self.pages = pages
        self.saved: list[ContentUpdate] = []

    def active(self) -> tuple[Page, ...]:
        return self.pages

    def save_content(
        self, updates: Sequence[ContentUpdate], audited_at: datetime
    ) -> None:
        self.saved = list(updates)


class FakeClaude:
    def __init__(self) -> None:
        self.submitted: list[Request] = []

    def submit(self, requests: Sequence[Request]) -> str:
        self.submitted = list(requests)
        return "msgbatch_123"


class FakeBatchLog:
    def __init__(self) -> None:
        self.recorded: list[tuple[str, datetime, int]] = []

    def record(self, batch_id: str, submitted_at: datetime, pages: int) -> None:
        self.recorded.append((batch_id, submitted_at, pages))


def site(request: httpx.Request) -> httpx.Response:
    pages = {"/new": NEW_HTML, "/same": SAME_HTML}
    if request.url.path not in pages:
        return httpx.Response(404)
    return httpx.Response(200, html=pages[request.url.path])


def audit(pages: FakePages, *, review_all: bool = False):
    client = httpx.Client(transport=httpx.MockTransport(site))
    return run_audit(
        pages,
        client,
        SETUP,
        ignore=None,
        review_all=review_all,
        audited_at=NOW,
        sleep=lambda seconds: None,
    )


def page(record_id: str, path: str, **fields: Any) -> Page:
    return Page(
        id=record_id, created_at=NOW, url=f"https://example.org{path}", **fields
    )


UNCHANGED = page(
    "recSame",
    "/same",
    content_hash=SAME_HASH,
    reviewed_hash=SAME_HASH,
    review_version=SETUP.version,
)


def test_only_new_or_changed_pages_are_sent_for_review():
    pages = FakePages(page("recNew", "/new"), UNCHANGED, page("recGone", "/gone"))

    report = audit(pages)

    assert [request["custom_id"].split("-")[0] for request in report.requests] == [
        "recNew"
    ]
    assert report.changes == {"new": 1, "unchanged": 1}
    # The page that couldn't be read is skipped, not saved.
    assert [update.page_id for update in pages.saved] == ["recNew", "recSame"]


def test_all_sends_every_readable_page():
    report = audit(FakePages(page("recNew", "/new"), UNCHANGED), review_all=True)

    assert len(report.requests) == 2


def test_pages_reviewed_before_versions_get_one_recorded():
    pages = FakePages(
        page("recOld", "/same", content_hash=SAME_HASH, reviewed_hash=SAME_HASH)
    )

    report = audit(pages)

    assert report.requests == ()
    [update] = pages.saved
    assert update.review_version == SETUP.version


def test_auditing_needs_at_least_one_topic():
    with pytest.raises(ConfigError, match="at least one topic"):
        review_setup([], context=None)


def test_topic_order_does_not_change_the_review_version():
    assert review_setup(list(reversed(TOPICS)), None).version == SETUP.version


def test_submitted_batches_are_recorded_for_collect():
    requests = audit(FakePages(page("recNew", "/new"))).requests
    claude, log = FakeClaude(), FakeBatchLog()

    batch_id = submit_reviews(claude, log, requests, NOW)

    assert batch_id == "msgbatch_123"
    assert claude.submitted == list(requests)
    assert log.recorded == [("msgbatch_123", NOW, 1)]
