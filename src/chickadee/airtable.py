from collections.abc import Container, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pyairtable import Table
from pyairtable.api.types import RecordDict, UpdateRecordDict

from chickadee.checker import CheckResult, status_of
from chickadee.extractor import ContentChange, PageContent
from chickadee.models import Flag, LinkResult, Page
from chickadee.reviewer import PageReview

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


class AirtablePages:
    """The Pages table, spoken to in Chickadee's own types."""

    def __init__(self, table: Table) -> None:
        self._table = table

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


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def checked_before(cutoff: datetime) -> str:
    return f"IS_BEFORE({{Checked at}}, DATETIME_PARSE('{_stamp(cutoff)}'))"


def checked_after(cutoff: datetime) -> str:
    return f"IS_AFTER({{Checked at}}, DATETIME_PARSE('{_stamp(cutoff)}'))"


def drop_missing(
    updates: Sequence[UpdateRecordDict], existing: Container[str]
) -> tuple[list[UpdateRecordDict], list[str]]:
    kept = [update for update in updates if update["id"] in existing]
    missing = [update["id"] for update in updates if update["id"] not in existing]

    return kept, missing


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
    content: PageContent, current_hash: str, change: ContentChange, audited_at: datetime
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


def to_audit_fields(
    content: PageContent, review: PageReview | None, audited_at: datetime
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "Current title": content.title,
        "Current description": content.meta_description,
        "Word count": content.word_count,
        "Last audited": audited_at.isoformat(),
    }

    if review is not None:
        fields |= {
            "SEO score": review.score,
            "SEO summary": review.summary,
            "Suggested title": review.suggested_title,
            "Suggested description": review.suggested_description,
            "SEO issues": "\n".join(f"- {issue}" for issue in review.issues),
        }

    return fields


def to_status_fields(
    result: CheckResult, checked_at: datetime, previous_status: str | None
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
