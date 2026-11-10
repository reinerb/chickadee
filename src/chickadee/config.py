import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

import soupsieve
from dotenv import load_dotenv

from chickadee.errors import ConfigError

CheckLog = Literal["all", "changes"]


@dataclass(frozen=True)
class Settings:
    """Everything Chickadee reads from the environment or a .env file.

    Values are checked when they're read, but none is required until a
    command uses it (see `required`), so `test-alert` works without any
    Airtable credentials. Secrets are left out of the repr, so printing
    or logging the settings can't reveal them.
    """

    airtable_token: str | None = field(default=None, repr=False)
    airtable_base_id: str | None = None
    anthropic_api_key: str | None = field(default=None, repr=False)
    alert_webhook_url: str | None = field(default=None, repr=False)
    digest_webhook_url: str | None = field(default=None, repr=False)
    check_log: CheckLog = "changes"
    retention_days: int = 90
    stale_after_days: int = 365
    ignore_selectors: str | None = None


def required(value: str | None, name: str) -> str:
    """The value a command needs, or a clear error saying which one is missing."""
    if not value:
        raise ConfigError(
            f"Missing {name} environment variable. Check your .env file or CI secrets."
        )
    return value


def _text(env: Mapping[str, str], name: str) -> str | None:
    return env.get(name, "").strip() or None


def _base_id(env: Mapping[str, str]) -> str | None:
    base_id = _text(env, "AIRTABLE_BASE_ID")
    if base_id is not None and (not base_id.startswith("app") or "/" in base_id):
        raise ConfigError(
            f"AIRTABLE_BASE_ID looks wrong: {base_id!r}. It should be just the 'app...' part."
        )
    return base_id


def _check_log(env: Mapping[str, str]) -> CheckLog:
    check_log = _text(env, "CHECK_LOG") or "changes"
    if check_log not in ("all", "changes"):
        raise ConfigError(f"CHECK_LOG must be 'all' or 'changes', not {check_log!r}.")
    return check_log


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    text = _text(env, name) or str(default)
    try:
        value = int(text)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, not {text!r}.") from None
    if value < 1:
        raise ConfigError(f"{name} must be at least 1.")
    return value


def _selectors(env: Mapping[str, str], name: str) -> str | None:
    value = _text(env, name)
    if value is None:
        return None

    try:
        soupsieve.compile(value)
    except soupsieve.SelectorSyntaxError as exc:
        raise ConfigError(f"{name} isn't a valid CSS selector: {exc}") from None

    return value


def parse_settings(env: Mapping[str, str]) -> Settings:
    return Settings(
        airtable_token=_text(env, "AIRTABLE_TOKEN"),
        airtable_base_id=_base_id(env),
        anthropic_api_key=_text(env, "ANTHROPIC_API_KEY"),
        alert_webhook_url=_text(env, "ALERT_WEBHOOK_URL"),
        digest_webhook_url=_text(env, "DIGEST_WEBHOOK_URL"),
        check_log=_check_log(env),
        retention_days=_positive_int(env, "RETENTION_DAYS", 90),
        stale_after_days=_positive_int(env, "STALE_AFTER_DAYS", 365),
        ignore_selectors=_selectors(env, "IGNORE_SELECTORS"),
    )


def load_settings() -> Settings:
    """Read the settings once: values already in the environment win over .env."""
    load_dotenv()
    return parse_settings(os.environ)
