import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

CheckLog = Literal["all", "changes"]


@dataclass(frozen=True)
class Settings:
    airtable_token: str
    airtable_base_id: str


@dataclass(frozen=True)
class Options:
    check_log: CheckLog
    retention_days: int
    stale_after_days: int


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    text = env.get(name) or str(default)
    try:
        value = int(text)
    except ValueError:
        raise RuntimeError(f"{name} must be a whole number, not {text!r}.") from None
    if value < 1:
        raise RuntimeError(f"{name} must be at least 1.")
    return value


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("AIRTABLE_TOKEN")
    base_id = os.getenv("AIRTABLE_BASE_ID")

    if not token:
        raise RuntimeError(
            "Missing AIRTABLE_TOKEN environment variable. Check your .env file."
        )

    if not base_id:
        raise RuntimeError(
            "Missing AIRTABLE_BASE_ID environment variable. Check your .env file."
        )

    if not base_id.startswith("app") or "/" in base_id:
        raise RuntimeError(
            f"AIRTABLE_BASE_ID looks wrong: {base_id!r}. It should be just the 'app...' part."
        )

    return Settings(
        airtable_token=token,
        airtable_base_id=base_id,
    )


def load_anthropic_key() -> str:
    load_dotenv()
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing ANTHROPIC_API_KEY. Check your .env file or CI secrets."
        )
    return key


def parse_options(env: Mapping[str, str]) -> Options:
    check_log = env.get("CHECK_LOG") or "changes"
    if check_log not in ("all", "changes"):
        raise RuntimeError(f"CHECK_LOG must be 'all' or 'changes', not {check_log!r}.")

    return Options(
        check_log=check_log,
        retention_days=_positive_int(env, "RETENTION_DAYS", 90),
        stale_after_days=_positive_int(env, "STALE_AFTER_DAYS", 365),
    )


def load_options() -> Options:
    load_dotenv()
    return parse_options(os.environ)


def load_alert_webhook() -> str | None:
    load_dotenv()
    return os.getenv("ALERT_WEBHOOK_URL") or None


def load_digest_webhook() -> str | None:
    load_dotenv()
    return os.getenv("DIGEST_WEBHOOK_URL") or None
