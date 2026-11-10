import pytest

from chickadee.config import parse_settings, required
from chickadee.errors import ConfigError


def test_defaults_when_unset():
    settings = parse_settings({})

    assert settings.check_log == "changes"
    assert settings.retention_days == 90


def test_empty_values_count_as_unset():
    settings = parse_settings({"CHECK_LOG": "", "RETENTION_DAYS": ""})

    assert settings.check_log == "changes"
    assert settings.retention_days == 90


def test_unknown_mode_is_rejected():
    with pytest.raises(ConfigError):
        parse_settings({"CHECK_LOG": "everything"})


def test_zero_retention_is_rejected():
    with pytest.raises(ConfigError):
        parse_settings({"RETENTION_DAYS": "0"})


def test_stale_setting_defaults_to_a_year():
    assert parse_settings({}).stale_after_days == 365
    assert parse_settings({"STALE_AFTER_DAYS": "730"}).stale_after_days == 730


@pytest.mark.parametrize("value", [None, "", "   "])
def test_ignore_selectors_unset(value):
    env = {} if value is None else {"IGNORE_SELECTORS": value}
    assert parse_settings(env).ignore_selectors is None


def test_ignore_selectors_are_trimmed():
    env = {"IGNORE_SELECTORS": " .related-posts, time "}
    assert parse_settings(env).ignore_selectors == ".related-posts, time"


def test_invalid_selector_stops_at_startup():
    with pytest.raises(ConfigError, match="IGNORE_SELECTORS"):
        parse_settings({"IGNORE_SELECTORS": ".related-posts,"})


def test_nothing_is_required_until_a_command_needs_it():
    settings = parse_settings({})

    assert settings.airtable_token is None
    assert settings.alert_webhook_url is None


def test_a_missing_value_names_itself():
    with pytest.raises(ConfigError, match="Missing AIRTABLE_TOKEN"):
        required(parse_settings({}).airtable_token, "AIRTABLE_TOKEN")

    assert required("pat123", "AIRTABLE_TOKEN") == "pat123"


@pytest.mark.parametrize("base_id", ["tblABC", "appXYZ/tblABC"])
def test_a_base_id_that_isnt_one_is_rejected(base_id: str):
    with pytest.raises(ConfigError, match="AIRTABLE_BASE_ID looks wrong"):
        parse_settings({"AIRTABLE_BASE_ID": base_id})


def test_secrets_never_appear_in_the_repr():
    settings = parse_settings(
        {
            "AIRTABLE_TOKEN": "pat-secret",
            "ANTHROPIC_API_KEY": "sk-ant-secret",
            "ALERT_WEBHOOK_URL": "https://hook.example.org/secret",
            "AIRTABLE_BASE_ID": "appXYZ",
        }
    )

    assert "secret" not in repr(settings)
    assert "appXYZ" in repr(settings)
