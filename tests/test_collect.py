from collections.abc import Sequence
from datetime import UTC, datetime

from chickadee.collect import (
    BatchOutcome,
    PendingBatch,
    ReviewResult,
    SavedReview,
    run_collect,
)
from chickadee.reviewer import PageReview, make_custom_id

NOW = datetime(2026, 11, 10, tzinfo=UTC)
TOPIC_IDS = {"Fish": "recFish", "Policy": "recPolicy"}


def review(*topics: str) -> PageReview:
    return PageReview(
        content_summary="A summary.",
        key_point="The main finding.",
        key_point_up_front=True,
        topics=list(topics),
        score=7,
        summary="Solid basics.",
        suggested_title="Title",
        suggested_description="Description",
        issues=[],
    )


class FakeBatches:
    def __init__(self, *pending: PendingBatch) -> None:
        self.waiting = list(pending)
        self.collected: list[str] = []

    def pending(self) -> list[PendingBatch]:
        return self.waiting

    def mark_collected(self, record_id: str) -> None:
        self.collected.append(record_id)


class FakeClaude:
    def __init__(
        self, statuses: dict[str, str], results: dict[str, list[ReviewResult]]
    ) -> None:
        self.statuses = statuses
        self.batch_results = results

    def status(self, batch_id: str) -> str:
        return self.statuses[batch_id]

    def results(self, batch_id: str) -> list[ReviewResult]:
        return self.batch_results[batch_id]


class FakePages:
    def __init__(self, *ids: str) -> None:
        self.existing = set(ids)
        self.saved: list[SavedReview] = []

    def ids(self) -> set[str]:
        return self.existing

    def save_reviews(
        self, reviews: Sequence[SavedReview], reviewed_at: datetime
    ) -> None:
        self.saved.extend(reviews)


def collect(batches: FakeBatches, claude: FakeClaude, pages: FakePages):
    return run_collect(batches, claude, pages, topic_ids=TOPIC_IDS, reviewed_at=NOW)


def test_finished_batches_are_saved_and_marked_collected():
    batches = FakeBatches(
        PendingBatch("recBatch1", "msgbatch_done"),
        PendingBatch("recBatch2", "msgbatch_running"),
    )
    claude = FakeClaude(
        {"msgbatch_done": "ended", "msgbatch_running": "in_progress"},
        {
            "msgbatch_done": [
                ReviewResult(make_custom_id("recA", "hashA", "v1"), review(" fish ")),
                ReviewResult(make_custom_id("recGone", "hashG", "v1"), review()),
                ReviewResult(make_custom_id("recB", "hashB", "v1"), None, "errored"),
                ReviewResult(make_custom_id("recC", "hashC", "v1"), review("Whales")),
            ]
        },
    )
    pages = FakePages("recA", "recB", "recC")

    outcomes = collect(batches, claude, pages)

    assert outcomes == [
        BatchOutcome("msgbatch_done", "ended", saved=2, missing=1),
        BatchOutcome("msgbatch_running", "in_progress"),
    ]
    assert batches.collected == ["recBatch1"]

    first, second = pages.saved
    assert (first.page_id, first.reviewed_hash, first.version) == (
        "recA",
        "hashA",
        "v1",
    )
    assert first.topic_ids == ("recFish",)
    # An unknown topic is reported and left off, but the review is still saved.
    assert (second.page_id, second.topic_ids) == ("recC", ())


def test_nothing_waiting_needs_no_page_lookups():
    class NoPages(FakePages):
        def ids(self) -> set[str]:
            raise AssertionError("pages were read with nothing to collect")

    outcomes = collect(FakeBatches(), FakeClaude({}, {}), NoPages())

    assert outcomes == []
