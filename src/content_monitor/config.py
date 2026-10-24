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

    return Settings(airtable_token=token, airtable_base_id=base_id)
