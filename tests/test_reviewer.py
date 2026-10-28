import json
import re

from chickadee import reviewer
from chickadee.extractor import PageContent
from chickadee.reviewer import (
    Topic,
    build_system_prompt,
    format_page_for_review,
    make_custom_id,
    parse_custom_id,
    parse_review_text,
    review_schema,
    review_version,
    truncate_words,
)

SCHEMA = {"properties": {"topics": {"items": {"enum": ["Fish", "Policy"]}}}}
VALID = {
    "content_summary": "A summary.",
    "key_point": "The main finding.",
    "key_point_up_front": True,
    "topics": ["Fish"],
    "score": 7,
    "summary": "Solid basics.",
    "suggested_title": "Title",
    "suggested_description": "Description",
    "issues": ["One issue"],
}


# Reading Claude's answers


def test_valid_review_parses():
    review = parse_review_text(json.dumps(VALID))

    assert review is not None
    assert review.score == 7


def test_out_of_range_score_is_rejected():
    assert parse_review_text(json.dumps(VALID | {"score": 11})) is None


# Custom IDs


def test_custom_id_round_trips():
    custom_id = make_custom_id("recABC123", "0123456789abcdef", "abcdef012345")

    assert parse_custom_id(custom_id) == (
        "recABC123",
        "0123456789abcdef",
        "abcdef012345",
    )


def test_custom_ids_from_before_versions_still_parse():
    assert parse_custom_id("recABC123-0123456789abcdef") == (
        "recABC123",
        "0123456789abcdef",
        None,
    )


def test_custom_ids_from_before_hashing_still_parse():
    assert parse_custom_id("recABC123") == ("recABC123", None, None)


def test_custom_id_fits_the_batch_api_rules():
    custom_id = make_custom_id("rec" + "x" * 14, "f" * 16, "e" * 12)

    assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", custom_id)


# Review version


def test_review_version_is_stable():
    assert review_version("Prompt", SCHEMA) == review_version("Prompt", SCHEMA)
    assert re.fullmatch(r"[0-9a-f]{12}", review_version("Prompt", SCHEMA))


def test_review_version_changes_with_the_setup(monkeypatch):
    before = review_version("Prompt", SCHEMA)
    renamed = {"properties": {"topics": {"items": {"enum": ["Fish", "Law"]}}}}

    assert review_version("Prompt, edited", SCHEMA) != before
    assert review_version("Prompt", renamed) != before

    monkeypatch.setattr(reviewer, "MODEL", "claude-haiku-5-5")
    assert review_version("Prompt", SCHEMA) != before
    monkeypatch.undo()

    monkeypatch.setattr(reviewer, "REVIEW_REVISION", 2)
    assert review_version("Prompt", SCHEMA) != before


# Preparing pages for review


def test_truncation_happens_at_word_boundaries():
    assert truncate_words("one two three", 5) == ("one two three", False)
    assert truncate_words("one two three four", 2) == ("one two", True)


def test_review_tells_claude_when_text_was_cut_off():
    content = PageContent(None, None, (), (), 4, "one two three four", modified_at=None)

    cut = format_page_for_review("https://example.org/", content, max_words=2)
    whole = format_page_for_review("https://example.org/", content)

    assert "one two\n</page_text>" in cut
    assert "cut off after 2 words" in cut
    assert "cut off" not in whole


def test_schema_limits_topics_to_the_list():
    schema = review_schema(["Fish", "Farmed animals"])

    assert schema["properties"]["topics"]["items"]["enum"] == ["Fish", "Farmed animals"]


def test_prompt_lists_topics_with_descriptions():
    prompt = build_system_prompt(
        [Topic("Fish", "Research on fish welfare"), Topic("Diet")]
    )

    assert "- Fish: Research on fish welfare" in prompt
    assert "- Diet" in prompt
