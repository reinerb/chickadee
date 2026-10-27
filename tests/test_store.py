from datetime import UTC, datetime
from typing import Any

from chickadee.checker import CheckResult
from chickadee.extractor import PageContent, content_hash
from chickadee.results import LinkResult
from chickadee.reviewer import PageReview
from chickadee.store import (
    classify_change,
    match_topics,
    needs_review,
    should_log,
    to_check_fields,
    to_content_fields,
    to_link_fields,
    to_review_fields,
    to_status_fields,
)

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
    fields = to_content_fields(CONTENT, content_hash(CONTENT), "new", datetime.now())

    assert "Current title" in fields
    assert fields["Current title"] is None


def test_review_fields_include_score_and_bulleted_issues():
    review = make_review()

    fields = to_review_fields(
        review, CHECKED_AT, content_hash(CONTENT), ["Has problems"]
    )

    assert fields["SEO score"] == 6
    assert fields["SEO issues"] == "- First problem\n- Second problem"


def test_changes_mode_logs_only_when_status_changes():
    assert should_log("Up", make_result(ok=False), "changes")
    assert not should_log("Up", make_result(ok=True), "changes")


def test_first_check_is_always_logged():
    assert should_log(None, make_result(ok=True), "changes")


def test_all_mode_logs_every_check():
    assert should_log("Up", make_result(ok=True), "all")


def test_status_since_only_moves_when_status_changes():
    unchanged = to_status_fields(make_result(ok=True), CHECKED_AT, "Up")
    changed = to_status_fields(make_result(ok=False), CHECKED_AT, "Up")

    assert "Status since" not in unchanged
    assert changed["Status since"] == CHECKED_AT.isoformat()


def test_change_classification():
    assert classify_change(None, "abc") == "new"
    assert classify_change("abc", "abc") == "unchanged"
    assert classify_change("abc", "xyz") == "changed"


def test_review_needed_until_the_current_version_is_reviewed():
    assert needs_review(None, "abc")
    assert needs_review("old", "abc")
    assert not needs_review("abc", "abc")


def test_changed_at_is_only_set_for_real_changes():
    new = to_content_fields(CONTENT, "abc", "new", CHECKED_AT)
    changed = to_content_fields(CONTENT, "abc", "changed", CHECKED_AT)

    assert "Content changed at" not in new
    assert changed["Content changed at"] == CHECKED_AT.isoformat()
    assert changed["Content hash"] == "abc"


def test_topics_match_case_insensitively_and_report_unknowns():
    ids = {"fish": "recFish", "farmed animals": "recFarm"}

    matched, unknown = match_topics(["Fish", "farmed Animals", "fish", "Cats"], ids)

    assert matched == ["recFish", "recFarm"]
    assert unknown == ["Cats"]


def test_key_point_is_saved_as_yes_or_no():
    up_front = to_review_fields(make_review(), CHECKED_AT, "abc", ["recFish"])
    buried = to_review_fields(
        make_review(key_point_up_front=False), CHECKED_AT, "abc", []
    )

    assert up_front["Key point up front"] == "Yes"
    assert buried["Key point up front"] == "No"
    assert up_front["Topics"] == ["recFish"]
    assert buried["Topics"] == []


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
