import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    airtable_token: str
    airtable_base_id: str


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
