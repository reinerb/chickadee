import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from chickadee.reviewer import PageReview, match_topics, parse_custom_id

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewResult:
    """One page's result from a finished batch."""

    custom_id: str
    review: PageReview | None
    problem: str | None = None  # why there's no review


@dataclass(frozen=True)
class PendingBatch:
    record_id: str
    batch_id: str


@dataclass(frozen=True)
class SavedReview:
    page_id: str
    review: PageReview
    reviewed_hash: str | None
    version: str | None
    topic_ids: tuple[str, ...]


class ReviewBatches(Protocol):
    """Claude's side: how a batch is doing, and what came back."""

    def status(self, batch_id: str) -> str: ...

    def results(self, batch_id: str) -> Iterable[ReviewResult]: ...


class CollectBatches(Protocol):
    """Our side: the batches waiting to be collected."""

    def pending(self) -> list[PendingBatch]: ...

    def mark_collected(self, record_id: str) -> None: ...


class CollectPages(Protocol):
    def ids(self) -> set[str]: ...

    def save_reviews(
        self, reviews: Sequence[SavedReview], reviewed_at: datetime
    ) -> None: ...


@dataclass(frozen=True)
class BatchOutcome:
    batch_id: str
    status: str
    saved: int = 0
    missing: int = 0  # reviews for pages deleted since the batch was sent


def saved_reviews(
    results: Iterable[ReviewResult], topic_ids: Mapping[str, str]
) -> list[SavedReview]:
    """Turn a batch's results into reviews to save, reporting any problems."""
    lookup = {name.strip().casefold(): topic_id for name, topic_id in topic_ids.items()}
    reviews: list[SavedReview] = []

    for result in results:
        if result.review is None:
            log.warning("  %s: %s", result.custom_id, result.problem)
            continue

        matched, unknown = match_topics(result.review.topics, lookup)
        if unknown:
            log.warning(
                "  %s: unknown topic(s): %s", result.custom_id, ", ".join(unknown)
            )

        page_id, reviewed_hash, version = parse_custom_id(result.custom_id)
        reviews.append(
            SavedReview(page_id, result.review, reviewed_hash, version, tuple(matched))
        )

    return reviews


def run_collect(
    batches: CollectBatches,
    claude: ReviewBatches,
    pages: CollectPages,
    *,
    topic_ids: Mapping[str, str],
    reviewed_at: datetime,
) -> list[BatchOutcome]:
    pending = batches.pending()
    if not pending:
        return []

    existing = pages.ids()
    outcomes: list[BatchOutcome] = []

    for batch in pending:
        status = claude.status(batch.batch_id)
        if status != "ended":
            outcomes.append(BatchOutcome(batch.batch_id, status))
            continue

        reviews = saved_reviews(claude.results(batch.batch_id), topic_ids)
        kept = [review for review in reviews if review.page_id in existing]
        pages.save_reviews(kept, reviewed_at)
        batches.mark_collected(batch.record_id)

        outcomes.append(
            BatchOutcome(
                batch.batch_id,
                status,
                saved=len(kept),
                missing=len(reviews) - len(kept),
            )
        )

    return outcomes
