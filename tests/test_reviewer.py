import json
import re

from chickadee.extractor import PageContent
from chickadee.reviewer import (
    Topic,
    build_system_prompt,
    format_page_for_review,
    make_custom_id,
    parse_custom_id,
    parse_review_text,
    review_schema,
    truncate_words,
)

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


def test_valid_review_parses():
    review = parse_review_text(json.dumps(VALID))

    assert review is not None
    assert review.score == 7


def test_out_of_range_score_is_rejected():
    assert parse_review_text(json.dumps(VALID | {"score": 11})) is None


def test_custom_id_round_trips():
    custom_id = make_custom_id("recABC123", "0123456789abcdef")

    assert parse_custom_id(custom_id) == ("recABC123", "0123456789abcdef")


def test_custom_ids_from_before_hashing_still_parse():
    assert parse_custom_id("recABC123") == ("recABC123", None)


def test_custom_id_fits_the_batch_api_rules():
    custom_id = make_custom_id("rec" + "x" * 14, "f" * 16)

    assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", custom_id)


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
