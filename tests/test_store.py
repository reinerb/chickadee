from datetime import UTC, datetime

from content_monitor.checker import CheckResult
from content_monitor.extractor import PageContent
from content_monitor.reviewer import SeoReview
from content_monitor.store import to_check_fields, to_content_fields, to_review_fields

CHECKED_AT = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
CONTENT = PageContent(
    title=None,
    meta_description="A description.",
    h1s=("Heading",),
    h2s=(),
    word_count=250,
)


def test_successful_check_includes_all_fields():
    result = CheckResult(
        url="https://example.com",
        ok=True,
        status_code=200,
        response_time_ms=123,
        error=None,
    )

    fields = to_check_fields("recABC123", result, CHECKED_AT)

    assert fields == {
        "Page": ["recABC123"],
        "Checked at": "2026-10-24T12:00:00+00:00",
        "Status code": 200,
        "Response time (ms)": 123,
        "Ok": True,
    }


def test_connection_failure_omits_missing_values():
    result = CheckResult(
        url="https://nope.invalid",
        ok=False,
        status_code=None,
        response_time_ms=None,
        error="ConnectError: name resolution failed",
    )

    fields = to_check_fields("recABC123", result, CHECKED_AT)

    assert "Status code" not in fields
    assert "Response time (ms)" not in fields
    assert fields["Ok"] is False
    assert fields["Error"] == "ConnectError: name resolution failed"


def test_missing_title_is_sent_as_none_to_clear_old_value():
    fields = to_content_fields(CONTENT)

    assert "Current title" in fields
    assert fields["Current title"] is None


def test_review_fields_include_score_and_bulleted_issues():
    review = SeoReview(
        score=6,
        summary="Decent.",
        suggested_title="Title",
        suggested_description="Description",
        issues=["First problem", "Second problem"],
    )

    fields = to_review_fields(review, CHECKED_AT)

    assert fields["SEO score"] == 6
    assert fields["SEO issues"] == "- First problem\n- Second problem"
