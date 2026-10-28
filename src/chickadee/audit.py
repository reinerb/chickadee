import argparse
import time
from collections import Counter
from datetime import UTC, datetime

import httpx
from anthropic import Anthropic
from anthropic.types.messages.batch_create_params import Request
from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from chickadee.checker import make_client
from chickadee.config import load_anthropic_key, load_options, load_settings
from chickadee.extractor import content_hash, extract_content
from chickadee.reviewer import (
    Topic,
    build_review_request,
    build_system_prompt,
    review_schema,
    review_version,
)
from chickadee.store import classify_change, review_state, to_content_fields

HELP = "Read each page, record changes, and send new or changed pages for review."

NEEDS_REVIEW = ("new", "changed", "setup")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--all",
        action="store_true",
        help="review every page, even ones that haven't changed",
    )


def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    options = load_options()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    batches = api.table(settings.airtable_base_id, "Audit batches")

    topics = sorted(
        (
            Topic(
                name=record["fields"]["Name"],
                description=record["fields"].get("Description"),
            )
            for record in api.table(settings.airtable_base_id, "Topics").all(
                fields=["Name", "Description"]
            )
            if record["fields"].get("Name")
        ),
        key=lambda topic: topic.name.casefold(),
    )
    if not topics:
        raise SystemExit("Add at least one topic to the Topics table before auditing.")

    system = build_system_prompt(topics)
    schema = review_schema([topic.name for topic in topics])
    version = review_version(system, schema)
    print(f"Review version {version}")

    audited_at = datetime.now(UTC)
    updates: list[UpdateRecordDict] = []
    requests: list[Request] = []
    counts: Counter[str] = Counter()
    states: Counter[str] = Counter()

    records = pages.all(
        formula="{Active}",
        fields=["URL", "Content hash", "Reviewed hash", "Review version"],
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

            content = extract_content(response.text, ignore=options.ignore_selectors)
            current = content_hash(content)
            change = classify_change(fields.get("Content hash"), current)
            counts[change] += 1

            state = review_state(
                fields.get("Reviewed hash"),
                current,
                fields.get("Review version"),
                version,
            )
            states[state] += 1

            page_fields = to_content_fields(content, current, change, audited_at)
            if state == "baseline":
                page_fields["Review version"] = version
            updates.append({"id": record["id"], "fields": page_fields})

            if args.all or state in NEEDS_REVIEW:
                requests.append(
                    build_review_request(
                        record["id"],
                        current,
                        url,
                        content,
                        system=system,
                        schema=schema,
                        version=version,
                    )
                )
                action = "review"
            else:
                action = "skip"
            print(f"{change:<9} {action:<6} {state:<8} {url}")

    if updates:
        pages.batch_update(updates)
    print(
        f"{counts['new']} new, {counts['changed']} changed, "
        f"{counts['unchanged']} unchanged."
    )
    if states["baseline"]:
        print(
            f"Recorded the review version for {states['baseline']} page(s) "
            "reviewed before versions were tracked."
        )
    if states["setup"]:
        print(
            f"{states['setup']} page(s) will be reviewed again "
            "because the review setup changed."
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
    print("Run `uv run chickadee collect` later to save the reviews.")
