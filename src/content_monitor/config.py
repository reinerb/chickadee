import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    airtable_token: str
    airtable_base_id: str
    anthropic_api_key: str


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("AIRTABLE_TOKEN")
    base_id = os.getenv("AIRTABLE_BASE_ID")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

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

    if not anthropic_key:
        raise RuntimeError(
            "Missing ANTHROPIC_API_KEY environment variable. Check your .env file."
        )

    return Settings(
        airtable_token=token, airtable_base_id=base_id, anthropic_api_key=anthropic_key
    )
