from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pyairtable.api.types import RecordDict

from chickadee.airtable import (
    PAGE_COLUMNS,
    checked_after,
    checked_before,
    page_from_record,
    to_check_fields,
    to_content_fields,
    to_flag_fields,
    to_link_fields,
    to_new_page_fields,
    to_review_fields,
    to_status_fields,
)
from chickadee.checker import CheckResult
from chickadee.extractor import PageContent, content_hash
from chickadee.models import LinkResult, Page
from chickadee.reviewer import PageReview

CHECKED_AT = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
CONTENT = PageContent(
    title=None,
    meta_description="A description.",
    h1s=("Heading",),
    h2s=(),
    word_count=250,
    text="Lorem ipsum, dolor sit amet consectetur adipisicing elit. Modi qui temporibus saepe eaque earum, molestiae autem in iure magnam asperiores distinctio explicabo. Beatae, ducimus fuga eaque quas repudiandae unde alias in numquam, enim sunt, laborum provident id placeat? Qui culpa adipisci consequuntur voluptas aliquid laudantium itaque dicta. Nesciunt soluta tempora esse amet, repudiandae a hic porro ex mollitia eaque voluptatem, nulla error reprehenderit non blanditiis totam. Nostrum sed quisquam ipsum hic laboriosam placeat necessitatibus neque? Sapiente omnis illum iure, aliquid adipisci quae nostrum quidem ipsam, libero velit neque vitae necessitatibus? Possimus eaque omnis sit mollitia beatae provident ad velit laboriosam obcaecati in quaerat, rerum eum ullam consequuntur molestiae ducimus nostrum assumenda accusantium voluptatem amet! Consequatur totam temporibus praesentium quasi maxime fuga quae officia neque perspiciatis, nemo possimus nostrum ratione nobis rem inventore? Placeat asperiores fugiat ipsam odio eius quod eligendi corporis, vero voluptatibus sapiente dolores soluta dolore laudantium quae. Repellat laboriosam corporis, omnis minus quis nulla excepturi veniam id ut, quod fugiat quasi expedita, beatae ex! Soluta minus ad labore vel asperiores quia, corporis officiis nobis, voluptas quo voluptatem accusamus dolore, totam animi repellat dolores enim earum saepe veritatis odio doloremque eos quas ullam impedit? Tempora, suscipit, explicabo quidem rerum molestiae quia inventore quasi eaque sit magni molestias enim a, voluptatum doloribus totam libero pariatur culpa ipsum ut reiciendis itaque minus sequi neque! Odit labore non temporibus ducimus atque dolorem ipsam soluta harum eum, repudiandae mollitia reiciendis fugiat saepe ut optio dolorum ex reprehenderit, voluptate iste error perferendis. Optio, tempore.",
    modified_at=None,
)


def make_review(**overrides: Any) -> PageReview:
    data = {
        "content_summary": "A summary.",
        "key_point": "The main finding.",
        "key_point_up_front": True,
        "topics": ["Fish"],
        "score": 6,
        "summary": "Decent.",
        "suggested_title": "Title",
        "suggested_description": "Description",
        "issues": ["First problem", "Second problem"],
    }
    return PageReview(**(data | overrides))


def make_result(ok: bool) -> CheckResult:
    return CheckResult(
        url="https://example.org",
        ok=ok,
        status_code=200 if ok else 503,
        response_time_ms=100,
        error=None,
    )


def test_formula_uses_utc_timestamp():
    cutoff = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    assert checked_before(cutoff) == (
        "IS_BEFORE({Checked at}, DATETIME_PARSE('2026-10-10T12:00:00Z'))"
    )


def test_formula_converts_other_timezones_to_utc():
    cutoff = datetime(2026, 10, 10, 8, 0, tzinfo=ZoneInfo("America/New_York"))

    assert "2026-10-10T12:00:00Z" in checked_before(cutoff)


def test_checked_after_uses_is_after():
    cutoff = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    assert checked_after(cutoff) == (
        "IS_AFTER({Checked at}, DATETIME_PARSE('2026-10-10T12:00:00Z'))"
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
    fields = to_content_fields(CONTENT, content_hash(CONTENT), "new", CHECKED_AT)

    assert "Current title" in fields
    assert fields["Current title"] is None


def test_review_version_is_recorded_only_when_given():
    plain = to_content_fields(CONTENT, content_hash(CONTENT), "unchanged", CHECKED_AT)
    baseline = to_content_fields(
        CONTENT, content_hash(CONTENT), "unchanged", CHECKED_AT, review_version="v2"
    )

    assert "Review version" not in plain
    assert baseline["Review version"] == "v2"


def test_review_fields_include_score_and_bulleted_issues():
    review = make_review()

    fields = to_review_fields(
        review, CHECKED_AT, content_hash(CONTENT), "v1", ["recFish"]
    )

    assert fields["SEO score"] == 6
    assert fields["SEO issues"] == "- First problem\n- Second problem"


def test_status_since_only_moves_when_status_changes():
    unchanged = to_status_fields(make_result(ok=True), CHECKED_AT, "Up")
    changed = to_status_fields(make_result(ok=False), CHECKED_AT, "Up")

    assert "Status since" not in unchanged
    assert changed["Status since"] == CHECKED_AT.isoformat()


def test_alerted_status_is_saved_only_when_given():
    plain = to_status_fields(make_result(ok=True), CHECKED_AT, None)
    recorded = to_status_fields(
        make_result(ok=True), CHECKED_AT, None, alerted_status="Up"
    )

    assert "Alerted status" not in plain
    assert recorded["Alerted status"] == "Up"


def test_changed_at_is_only_set_for_real_changes():
    new = to_content_fields(CONTENT, "abc", "new", CHECKED_AT)
    changed = to_content_fields(CONTENT, "abc", "changed", CHECKED_AT)

    assert "Content changed at" not in new
    assert changed["Content changed at"] == CHECKED_AT.isoformat()
    assert changed["Content hash"] == "abc"


def test_key_point_is_saved_as_yes_or_no():
    up_front = to_review_fields(make_review(), CHECKED_AT, "abc", "v1", ["recFish"])
    buried = to_review_fields(
        make_review(key_point_up_front=False), CHECKED_AT, "abc", "v1", []
    )

    assert up_front["Key point up front"] == "Yes"
    assert buried["Key point up front"] == "No"
    assert up_front["Topics"] == ["recFish"]
    assert buried["Topics"] == []


def test_review_version_is_saved_only_when_known():
    current = to_review_fields(make_review(), CHECKED_AT, "abc", "v1", ["recFish"])
    old_batch = to_review_fields(make_review(), CHECKED_AT, "abc", None, ["recFish"])

    assert current["Review version"] == "v1"
    assert "Review version" not in old_batch
    assert old_batch["Reviewed hash"] == "abc"


def test_link_fields_separate_broken_from_unverified():
    fields = to_link_fields(
        [
            LinkResult("https://a.example/", "broken", "404"),
            LinkResult("https://b.example/", "unverified", "403"),
            LinkResult("https://c.example/", "ok", "200"),
        ],
        CHECKED_AT,
    )

    assert fields["Broken links"] == "https://a.example/ (404)"
    assert fields["Unverified links"] == "https://b.example/ (403)"
    assert fields["Broken link count"] == 1


def test_fixed_links_are_cleared():
    fields = to_link_fields([LinkResult("https://a.example/", "ok", "200")], CHECKED_AT)

    assert "Broken links" in fields
    assert fields["Broken links"] is None
    assert fields["Broken link count"] == 0


def test_every_page_attribute_has_a_column():
    attributes = set(Page.model_fields) - {"id", "created_at"}
    assert attributes == set(PAGE_COLUMNS)


def test_page_from_a_full_record():
    record: RecordDict = {
        "id": "recAbc",
        "createdTime": "2026-01-05T09:00:00.000Z",
        "fields": {
            "URL": "https://example.org/post",
            "Active": True,
            "Status": "Up",
            "Status since": "2026-11-01T12:00:00.000Z",
            "Last response time (ms)": 182,
            "Key point up front": "No",
            "Topics": ["recT1", "recT2"],
            "Attention": ["Stale", "Key point buried"],
        },
    }

    page = page_from_record(record)

    assert page.label == "https://example.org/post"
    assert page.active is True
    assert page.status_since == datetime(2026, 11, 1, 12, tzinfo=UTC)
    assert page.key_point_up_front is False
    assert page.topic_ids == ("recT1", "recT2")
    assert page.attention == ("Stale", "Key point buried")
    assert page.seo_score is None  # empty fields are left out


def test_page_from_a_new_record():
    record: RecordDict = {
        "id": "recNew",
        "createdTime": "2026-11-09T15:00:00.000Z",
        "fields": {"URL": "https://example.org/new"},
    }

    page = page_from_record(record)

    assert page.active is False
    assert page.status is None
    assert page.attention == ()


def test_flag_fields_store_the_flags_and_their_count():
    assert to_flag_fields(["Stale", "Down"]) == {
        "Attention": ["Stale", "Down"],
        "Attention count": 2,
    }
    assert to_flag_fields([]) == {"Attention": [], "Attention count": 0}


def test_new_pages_keep_the_sitemap_lastmod():
    lastmod = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)

    assert to_new_page_fields("https://example.org/post", lastmod) == {
        "URL": "https://example.org/post",
        "Active": True,
        "Sitemap lastmod": "2026-03-01T09:30:00+00:00",
    }


def test_new_pages_without_a_lastmod_leave_it_empty():
    fields = to_new_page_fields("https://example.org/post", None)

    assert "Sitemap lastmod" not in fields
