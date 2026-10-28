import pytest
from pyairtable.api.types import RecordDict

from chickadee import digest, reviewer
from chickadee.digest import digest_system_prompt
from chickadee.reviewer import Topic, build_system_prompt, review_version
from chickadee.site_context import MAX_CONTEXT_CHARS, parse_site_context

TOPICS = [Topic("Fish", "Research on fish welfare")]
CONTEXT = "A research nonprofit. Readers are advocates and journalists."


def site(*contexts: str | None) -> list[RecordDict]:
    records: list[RecordDict] = []
    for number, context in enumerate(contexts):
        fields = {"Name": "Site"}
        if context is not None:
            fields["Context"] = context
        records.append({"id": f"rec{number}", "createdTime": "", "fields": fields})
    return records


@pytest.mark.parametrize("records", [site(), site(None), site("   \n ")])
def test_no_context(records):
    assert parse_site_context(records) is None


def test_context_is_trimmed():
    assert parse_site_context(site(f"  {CONTEXT}\n")) == CONTEXT


def test_one_filled_row_among_empty_ones_is_fine():
    assert parse_site_context(site(None, CONTEXT, "")) == CONTEXT


def test_two_contexts_stop_the_run():
    with pytest.raises(SystemExit, match="2 rows"):
        parse_site_context(site(CONTEXT, "Another site."))


def test_context_has_a_length_limit():
    assert parse_site_context(site("x" * MAX_CONTEXT_CHARS)) is not None
    with pytest.raises(SystemExit, match="2,001 characters"):
        parse_site_context(site("x" * (MAX_CONTEXT_CHARS + 1)))


@pytest.mark.parametrize(
    ("prompt", "role", "rules"),
    [
        (build_system_prompt(TOPICS, context=CONTEXT), reviewer.ROLE, reviewer.RULES),
        (digest_system_prompt(CONTEXT), digest.ROLE, digest.RULES),
    ],
)
def test_context_sits_between_the_role_and_the_rules(prompt, role, rules):
    assert prompt.index(role) < prompt.index(CONTEXT) < prompt.index(rules)


def test_without_context_there_is_no_context_section():
    assert "<site_context>" not in build_system_prompt(TOPICS, context=None)
    assert "<site_context>" not in digest_system_prompt(None)


def test_changing_the_context_changes_the_review_version():
    schema: dict = {}
    plain = review_version(build_system_prompt(TOPICS, context=None), schema)
    with_context = review_version(build_system_prompt(TOPICS, context=CONTEXT), schema)

    assert plain != with_context
