from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pyairtable import Table
from pyairtable.api.types import RecordDict, UpdateRecordDict

from chickadee.audit import ContentUpdate
from chickadee.checker import CheckResult, status_of
from chickadee.collect import PendingBatch, SavedReview
from chickadee.extractor import ContentChange, PageContent
from chickadee.models import Check, Flag, LinkResult, Page, Status
from chickadee.reviewer import PageReview, Topic
from chickadee.site_context import parse_site_context
from chickadee.uptime import StatusUpdate

# Page attribute -> Pages column. To read a new column, add a field
# to models.Page and a line here.
PAGE_COLUMNS = {
    "url": "URL",
    "name": "Name",
    "active": "Active",
    "sitemap_lastmod": "Sitemap lastmod",
    "status": "Status",
    "status_since": "Status since",
    "last_checked": "Last checked",
    "last_status_code": "Last status code",
    "last_response_time_ms": "Last response time (ms)",
    "alerted_status": "Alerted status",
    "current_title": "Current title",
    "current_description": "Current description",
    "word_count": "Word count",
    "page_modified_at": "Page modified at",
    "content_hash": "Content hash",
    "content_changed_at": "Content changed at",
    "content_summary": "Content summary",
    "key_point": "Key point",
    "key_point_up_front": "Key point up front",
    "topic_ids": "Topics",
    "seo_score": "SEO score",
    "seo_summary": "SEO summary",
    "suggested_title": "Suggested title",
    "suggested_description": "Suggested description",
    "seo_issues": "SEO issues",
    "last_audited": "Last audited",
    "reviewed_hash": "Reviewed hash",
    "review_version": "Review version",
    "broken_links": "Broken links",
    "unverified_links": "Unverified links",
    "broken_link_count": "Broken link count",
    "links_checked_at": "Links checked at",
    "attention": "Attention",
    "attention_count": "Attention count",
}
CHECK_COLUMNS = ["Page", "Checked at", "Ok", "Status code", "Error"]


def page_from_record(record: RecordDict) -> Page:
    fields = record["fields"]
    return Page.model_validate(
        {
            "id": record["id"],
            "created_at": record["createdTime"],
            **{
                attr: fields[column]
                for attr, column in PAGE_COLUMNS.items()
                if column in fields
            },
        }
    )


def check_from_record(record: RecordDict) -> Check | None:
    """A logged check, or None if the row is missing its page or time."""
    fields = record["fields"]
    linked: list[str] = fields.get("Page") or []
    checked_at = fields.get("Checked at")
    if not linked or not checked_at:
        return None
    return Check(
        page_id=linked[0],
        checked_at=datetime.fromisoformat(checked_at),
        ok=bool(fields.get("Ok")),
        status_code=fields.get("Status code"),
        error=fields.get("Error"),
    )


class AirtablePages:
    """The Pages table, spoken to in Chickadee's own types."""

    def __init__(self, table: Table) -> None:
        self._table = table

    def all(self) -> list[Page]:
        """Every page, including inactive ones."""
        return [page_from_record(record) for record in self._table.all()]

    def active(self) -> list[Page]:
        records = self._table.all(formula="{Active}")
        return [page_from_record(record) for record in records]

    def save_links(
        self, results: Mapping[str, Sequence[LinkResult]], checked_at: datetime
    ) -> None:
        updates: list[UpdateRecordDict] = [
            {"id": page_id, "fields": to_link_fields(found, checked_at)}
            for page_id, found in results.items()
        ]
        if updates:
            self._table.batch_update(updates)

    def save_flags(self, flags: Mapping[str, Sequence[Flag]]) -> None:
        updates: list[UpdateRecordDict] = [
            {"id": page_id, "fields": to_flag_fields(page_flags)}
            for page_id, page_flags in flags.items()
        ]
        if updates:
            self._table.batch_update(updates)

    def save_statuses(
        self, updates: Sequence[StatusUpdate], checked_at: datetime
    ) -> None:
        records: list[UpdateRecordDict] = [
            {
                "id": update.page_id,
                "fields": to_status_fields(
                    update.result,
                    checked_at,
                    update.previous_status,
                    alerted_status=update.alerted_status,
                ),
            }
            for update in updates
        ]
        if records:
            self._table.batch_update(records)

    def ids(self) -> set[str]:
        """Every page's record ID, including inactive pages."""
        return {record["id"] for record in self._table.all(fields=["URL"])}

    def save_content(
        self, updates: Sequence[ContentUpdate], audited_at: datetime
    ) -> None:
        records: list[UpdateRecordDict] = [
            {
                "id": update.page_id,
                "fields": to_content_fields(
                    update.content,
                    update.content_hash,
                    update.change,
                    audited_at,
                    review_version=update.review_version,
                ),
            }
            for update in updates
        ]
        if records:
            self._table.batch_update(records)

    def save_reviews(
        self, reviews: Sequence[SavedReview], reviewed_at: datetime
    ) -> None:
        records: list[UpdateRecordDict] = [
            {
                "id": review.page_id,
                "fields": to_review_fields(
                    review.review,
                    reviewed_at,
                    review.reviewed_hash,
                    review.version,
                    review.topic_ids,
                ),
            }
            for review in reviews
        ]
        if records:
            self._table.batch_update(records)

    def tracked_urls(self) -> set[str]:
        """Every page's URL, including inactive pages."""
        return {
            url
            for record in self._table.all(fields=["URL"])
            if (url := record["fields"].get("URL"))
        }

    def add(self, pages: Mapping[str, datetime | None]) -> None:
        if pages:
            self._table.batch_create(
                [to_new_page_fields(url, lastmod) for url, lastmod in pages.items()]
            )

    def save_alerted(self, statuses: Mapping[str, Status]) -> None:
        updates: list[UpdateRecordDict] = [
            {"id": page_id, "fields": {"Alerted status": status}}
            for page_id, status in statuses.items()
        ]
        if updates:
            self._table.batch_update(updates)


class AirtableChecks:
    """The Checks table: the uptime log."""

    def __init__(self, table: Table) -> None:
        self._table = table

    def record(self, results: Mapping[str, CheckResult], checked_at: datetime) -> None:
        rows = [
            to_check_fields(page_id, result, checked_at)
            for page_id, result in results.items()
        ]
        if rows:
            self._table.batch_create(rows)

    def since(self, start: datetime) -> list[Check]:
        records = self._table.all(formula=checked_after(start), fields=CHECK_COLUMNS)
        return [check for record in records if (check := check_from_record(record))]

    def newest_before(self, cutoff: datetime) -> Iterator[Check]:
        """Checks before `cutoff`, newest first, fetched a page at a time."""
        for records in self._table.iterate(
            formula=checked_before(cutoff), sort=["-Checked at"], fields=CHECK_COLUMNS
        ):
            for record in records:
                if (check := check_from_record(record)) is not None:
                    yield check

    def ids_before(self, cutoff: datetime) -> list[str]:
        records = self._table.all(formula=checked_before(cutoff), fields=["Checked at"])
        return [record["id"] for record in records]

    def delete(self, ids: Sequence[str]) -> None:
        if ids:
            self._table.batch_delete(ids)


class AirtableTopics:
    """The Topics table, which you manage."""

    def __init__(self, table: Table) -> None:
        self._table = table

    def all(self) -> list[Topic]:
        return [
            Topic(name=name, description=record["fields"].get("Description"))
            for record in self._table.all(fields=["Name", "Description"])
            if (name := record["fields"].get("Name"))
        ]

    def ids(self) -> dict[str, str]:
        """Each topic's record ID, by name."""
        return {
            name: record["id"]
            for record in self._table.all(fields=["Name"])
            if (name := record["fields"].get("Name"))
        }


class AirtableSite:
    """The Site table, which holds the site context."""

    def __init__(self, table: Table) -> None:
        self._table = table

    def context(self) -> str | None:
        records = self._table.all(fields=["Context"])
        return parse_site_context(
            [record["fields"].get("Context") for record in records]
        )


class AirtableBatches:
    """The Audit batches table: review batches waiting to be collected."""

    def __init__(self, table: Table) -> None:
        self._table = table

    def record(self, batch_id: str, submitted_at: datetime, pages: int) -> None:
        self._table.create(
            {
                "Batch ID": batch_id,
                "Submitted at": submitted_at.isoformat(),
                "Pages": pages,
            }
        )

    def pending(self) -> list[PendingBatch]:
        return [
            PendingBatch(record_id=record["id"], batch_id=record["fields"]["Batch ID"])
            for record in self._table.all(formula="NOT({Collected})")
        ]

    def mark_collected(self, record_id: str) -> None:
        self._table.update(record_id, {"Collected": True})


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def checked_before(cutoff: datetime) -> str:
    return f"IS_BEFORE({{Checked at}}, DATETIME_PARSE('{_stamp(cutoff)}'))"


def checked_after(cutoff: datetime) -> str:
    return f"IS_AFTER({{Checked at}}, DATETIME_PARSE('{_stamp(cutoff)}'))"


def to_check_fields(
    page_id: str, result: CheckResult, checked_at: datetime
) -> dict[str, Any]:
    fields = {
        "Page": [page_id],
        "Checked at": checked_at.isoformat(),
        "Status code": result.status_code,
        "Response time (ms)": result.response_time_ms,
        "Ok": result.ok,
        "Error": result.error,
    }

    # drop any None values
    return {name: value for name, value in fields.items() if value is not None}


def to_content_fields(
    content: PageContent,
    current_hash: str,
    change: ContentChange,
    audited_at: datetime,
    *,
    review_version: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "Current title": content.title,
        "Current description": content.meta_description,
        "Word count": content.word_count,
        "Content hash": current_hash,
        "Page modified at": content.modified_at.isoformat()
        if content.modified_at is not None
        else None,
    }

    if change == "changed":
        fields["Content changed at"] = audited_at.isoformat()
    if review_version is not None:
        fields["Review version"] = review_version

    return fields


def to_review_fields(
    review: PageReview,
    reviewed_at: datetime,
    reviewed_hash: str | None,
    version: str | None,
    topic_ids: Sequence[str],
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "Content summary": review.content_summary,
        "Key point": review.key_point,
        "Key point up front": "Yes" if review.key_point_up_front else "No",
        "Topics": list(topic_ids),
        "SEO score": review.score,
        "SEO summary": review.summary,
        "Suggested title": review.suggested_title,
        "Suggested description": review.suggested_description,
        "SEO issues": "\n".join(f"- {issue}" for issue in review.issues),
        "Last audited": reviewed_at.isoformat(),
    }

    if reviewed_hash is not None:
        fields["Reviewed hash"] = reviewed_hash
    if version is not None:
        fields["Review version"] = version

    return fields


def to_status_fields(
    result: CheckResult,
    checked_at: datetime,
    previous_status: str | None,
    *,
    alerted_status: Status | None = None,
) -> dict[str, Any]:
    status = status_of(result)
    fields: dict[str, Any] = {
        "Status": status,
        "Last status code": result.status_code,
        "Last response time (ms)": result.response_time_ms,
        "Last checked": checked_at.isoformat(),
    }

    if status != previous_status:
        fields["Status since"] = checked_at.isoformat()
    if alerted_status is not None:
        fields["Alerted status"] = alerted_status

    return fields


def to_link_fields(
    results: Sequence[LinkResult], checked_at: datetime
) -> dict[str, Any]:
    broken = [r for r in results if r.status == "broken"]
    unverified = [r for r in results if r.status == "unverified"]
    return {
        "Broken links": "\n".join(f"{r.url} ({r.detail})" for r in broken) or None,
        "Unverified links": "\n".join(f"{r.url} ({r.detail})" for r in unverified)
        or None,
        "Broken link count": len(broken),
        "Links checked at": checked_at.isoformat(),
    }


def to_flag_fields(flags: Sequence[Flag]) -> dict[str, Any]:
    return {"Attention": list(flags), "Attention count": len(flags)}


def to_new_page_fields(url: str, lastmod: datetime | None) -> dict[str, Any]:
    fields: dict[str, Any] = {"URL": url, "Active": True}
    if lastmod is not None:
        fields["Sitemap lastmod"] = lastmod.isoformat()
    return fields
