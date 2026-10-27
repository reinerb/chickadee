from pyairtable.api.types import UpdateRecordDict

from chickadee.collect import drop_missing


def test_reviews_for_deleted_pages_are_set_aside():
    updates: list[UpdateRecordDict] = [
        {"id": "rec1", "fields": {"SEO score": 7}},
        {"id": "rec2", "fields": {"SEO score": 5}},
        {"id": "rec3", "fields": {"SEO score": 9}},
    ]

    kept, missing = drop_missing(updates, {"rec1", "rec3", "rec4"})

    assert [update["id"] for update in kept] == ["rec1", "rec3"]
    assert missing == ["rec2"]
