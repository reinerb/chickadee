import json
import re

from content_monitor.reviewer import make_custom_id, parse_custom_id, parse_review_text

VALID = {
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
