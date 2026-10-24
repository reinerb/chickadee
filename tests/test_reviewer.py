import json

from content_monitor.reviewer import parse_review_text

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
