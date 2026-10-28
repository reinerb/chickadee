from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from chickadee.checker import CheckResult
from chickadee.config import CheckLog
from chickadee.extractor import PageContent
from chickadee.results import LinkResult
from chickadee.reviewer import PageReview

ContentChange = Literal["new", "changed", "unchanged"]
ReviewState = Literal["new", "changed", "setup", "baseline", "current"]


def classify_change(previous_hash: str | None, current_hash: str) -> ContentChange:
    if previous_hash is None:
        return "new"

    return "unchanged" if previous_hash == current_hash else "changed"


def needs_review(
    reviewed_hash: str | None,
    content_hash: str,
    reviewed_version: str | None,
    version: str,
) -> ReviewState:
    if reviewed_hash is None:
        return "new"
    if reviewed_hash != content_hash:
        return "changed"
    if reviewed_version is None:
        return "baseline"
    if reviewed_version != version:
        return "setup"
    return "current"


def match_topics(
    names: Sequence[str], topic_ids: Mapping[str, str]
) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    unknown: list[str] = []

    for name in names:
        record_id = topic_ids.get(name.strip().casefold())

        if record_id is None:
            unknown.append(name)
        elif record_id not in matched:
            matched.append(record_id)

    return matched, unknown


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


def status_of(result: CheckResult) -> str:
    return "Up" if result.ok else "Down"


def should_log(
    previous_status: str | None, result: CheckResult, check_log: CheckLog
) -> bool:
    if check_log == "all":
        return True

    return previous_status != status_of(result)


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
