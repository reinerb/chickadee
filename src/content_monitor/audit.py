import time
from datetime import UTC, datetime

import httpx
from anthropic import Anthropic
from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from content_monitor.checker import make_client
from content_monitor.config import load_settings
from content_monitor.extractor import extract_content
from content_monitor.reviewer import review_page
from content_monitor.store import to_audit_fields


def main() -> None:
    settings = load_settings()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    claude = Anthropic(api_key=settings.anthropic_api_key)

    audited_at = datetime.now(UTC)
    updates: list[UpdateRecordDict] = []

    with make_client() as client:
        for record in pages.all(formula="{Active}"):
            url = record["fields"]["URL"]
            time.sleep(1)

            try:
                response = client.get(url)
            except httpx.RequestError as exc:
                print(f"SKIP {url}: {exc}")
                continue

            content_type = response.headers.get("content-type", "")
            if not response.is_success or "text/html" not in content_type:
                print(f"SKIP {url}: status {response.status_code}, {content_type}")
                continue

            content = extract_content(response.text)
            review = review_page(claude, url, content)
            score = review.score if review else "?"
            print(f"{score:>2}/10  {url}")

            updates.append(
                {
                    "id": record["id"],
                    "fields": to_audit_fields(content, review, audited_at),
                }
            )

    pages.batch_update(updates)
    print(f"Updated {len(updates)} page(s) in Airtable.")
