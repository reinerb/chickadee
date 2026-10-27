import pytest

from chickadee.config import parse_options


def test_defaults_when_unset():
    options = parse_options({})

    assert options.check_log == "changes"
    assert options.retention_days == 90


def test_empty_values_count_as_unset():
    options = parse_options({"CHECK_LOG": "", "RETENTION_DAYS": ""})

    assert options.check_log == "changes"
    assert options.retention_days == 90


def test_unknown_mode_is_rejected():
    with pytest.raises(RuntimeError):
        parse_options({"CHECK_LOG": "everything"})


def test_zero_retention_is_rejected():
    with pytest.raises(RuntimeError):
        parse_options({"RETENTION_DAYS": "0"})


def test_stale_setting_defaults_to_a_year():
    assert parse_options({}).stale_after_days == 365
    assert parse_options({"STALE_AFTER_DAYS": "730"}).stale_after_days == 730


@pytest.mark.parametrize("value", [None, "", "   "])
def test_ignore_selectors_unset(value):
    env = {} if value is None else {"IGNORE_SELECTORS": value}
    assert parse_options(env).ignore_selectors is None


def test_ignore_selectors_are_trimmed():
    env = {"IGNORE_SELECTORS": " .related-posts, time "}
    assert parse_options(env).ignore_selectors == ".related-posts, time"


def test_invalid_selector_stops_at_startup():
    with pytest.raises(SystemExit, match="IGNORE_SELECTORS"):
        parse_options({"IGNORE_SELECTORS": ".related-posts,"})
