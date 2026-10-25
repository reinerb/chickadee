import argparse
import time
from collections import Counter
from datetime import UTC, datetime

import httpx
from anthropic import Anthropic
from anthropic.types.messages.batch_create_params import Request
from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from content_monitor.checker import make_client
from content_monitor.config import load_anthropic_key, load_settings
from content_monitor.extractor import content_hash, extract_content
from content_monitor.reviewer import (
    Topic,
    build_review_request,
    build_system_prompt,
    review_schema,
)
from content_monitor.store import classify_change, needs_review, to_content_fields


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit page content and send new or changed pages for review."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="review every page, even ones that haven't changed",
    )
    args = parser.parse_args()

    settings = load_settings()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    batches = api.table(settings.airtable_base_id, "Audit batches")

    topics = [
        Topic(
            name=record["fields"]["Name"],
            description=record["fields"].get("Description"),
        )
        for record in api.table(settings.airtable_base_id, "Topics").all(
            fields=["Name", "Description"]
        )
        if record["fields"].get("Name")
    ]
    if not topics:
        raise SystemExit("Add at least one topic to the Topics table before auditing.")

    system = build_system_prompt(topics)
    schema = review_schema([topic.name for topic in topics])

    audited_at = datetime.now(UTC)
    updates: list[UpdateRecordDict] = []
    requests: list[Request] = []
    counts: Counter[str] = Counter()

    records = pages.all(
        formula="{Active}", fields=["URL", "Content hash", "Reviewed hash"]
    )

    with make_client() as client:
        for record in records:
            fields = record["fields"]
            url = fields["URL"]
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
            current = content_hash(content)
            change = classify_change(fields.get("Content hash"), current)
            counts[change] += 1

            updates.append(
                {
                    "id": record["id"],
                    "fields": to_content_fields(content, current, change, audited_at),
                }
            )

            if args.all or needs_review(fields.get("Reviewed hash"), current):
                requests.append(
                    build_review_request(
                        record["id"],
                        current,
                        url,
                        content,
                        system=system,
                        schema=schema,
                    )
                )
                action = "review"
            else:
                action = "skip"
            print(f"{change:<9} {action:<6} {url}")

    if updates:
        pages.batch_update(updates)
    print(
        f"{counts['new']} new, {counts['changed']} changed, {counts['unchanged']} unchanged."
    )

    if not requests:
        print("No pages need review.")
        return

    claude = Anthropic(api_key=load_anthropic_key())
    batch = claude.messages.batches.create(requests=requests)
    batches.create(
        {
            "Batch ID": batch.id,
            "Submitted at": audited_at.isoformat(),
            "Pages": len(requests),
        }
    )
    print(f"Submitted batch {batch.id} with {len(requests)} page(s).")
    print("Run `uv run content-collect` later to save the reviews.")
