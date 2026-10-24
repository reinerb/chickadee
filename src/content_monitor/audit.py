import time
from datetime import UTC, datetime

import httpx
from anthropic import Anthropic
from anthropic.types.messages.batch_create_params import Request
from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from content_monitor.checker import make_client
from content_monitor.config import load_anthropic_key, load_settings
from content_monitor.extractor import extract_content
from content_monitor.reviewer import build_review_request
from content_monitor.store import to_content_fields


def main() -> None:
    settings = load_settings()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    batches = api.table(settings.airtable_base_id, "Audit batches")
    claude = Anthropic(api_key=load_anthropic_key())

    updates: list[UpdateRecordDict] = []
    requests: list[Request] = []

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
            updates.append({"id": record["id"], "fields": to_content_fields(content)})
            requests.append(build_review_request(record["id"], url, content))
            print("queued  {url}")

    if not requests:
        print("No pages to review.")
        return

    pages.batch_update(updates)
    batch = claude.messages.batches.create(requests=requests)
    batches.create(
        {
            "Batch ID": batch.id,
            "Submitted at": datetime.now(UTC).isoformat(),
            "Pages": len(requests),
        }
    )
    print(f"Submitted batch {batch.id} with {len(requests)} page(s).")
