from datetime import UTC, datetime

from anthropic import Anthropic
from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from content_monitor.config import load_settings
from content_monitor.reviewer import parse_review
from content_monitor.store import to_review_fields


def main() -> None:
    settings = load_settings()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    batches = api.table(settings.airtable_base_id, "Audit batches")
    claude = Anthropic(api_key=settings.anthropic_api_key)

    pending = batches.all(formula="NOT({Collected})")
    if not pending:
        print("No batches waiting to be collected.")
        return

    for batch_record in pending:
        batch_id = batch_record["fields"]["Batch ID"]
        batch = claude.messages.batches.retrieve(batch_id)

        if batch.processing_status != "ended":
            print(f"{batch_id} still {batch.processing_status}")
            continue

        reviewed_at = datetime.now(UTC)
        updates: list[UpdateRecordDict] = []

        for result in claude.messages.batches.results(batch_id):
            outcome = result.result
            if outcome.type != "succeeded":
                print(f"  {result.custom_id}: {outcome.type}")
                continue

            review = parse_review(outcome.message)
            if review is None:
                print(f"  {result.custom_id}: no usable review")
                continue

            updates.append(
                {
                    "id": result.custom_id,
                    "fields": to_review_fields(review, reviewed_at),
                }
            )

        pages.batch_update(updates)
        batches.update(batch_record["id"], {"Collected": True})
        print(f"{batch_id}: saved {len(updates)} review(s)")
