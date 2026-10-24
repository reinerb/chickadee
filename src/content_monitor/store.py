from datetime import datetime
from typing import Any

from content_monitor.checker import CheckResult
from content_monitor.extractor import PageContent
from content_monitor.reviewer import SeoReview


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


def to_content_fields(content: PageContent) -> dict[str, Any]:
    return {
        "Current title": content.title,
        "Current description": content.meta_description,
        "Word count": content.word_count,
    }


def to_review_fields(review: SeoReview, audited_at: datetime) -> dict[str, Any]:
    return {
        "SEO score": review.score,
        "SEO summary": review.summary,
        "Suggested title": review.suggested_title,
        "Suggested description": review.suggested_description,
        "SEO issues": "\n".join(f"- {issue}" for issue in review.issues),
        "Last audited": audited_at.isoformat(),
    }


def to_audit_fields(
    content: PageContent, review: SeoReview | None, audited_at: datetime
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
