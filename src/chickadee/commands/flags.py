import argparse
from collections import Counter
from datetime import UTC, datetime, timedelta

from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from chickadee.config import load_options, load_settings
from chickadee.flags import ALL_FLAGS, facts_from_record, find_flags, flag_update

HELP = "Flag pages that need attention."

FIELDS = [
    "Content hash",
    "Status",
    "Broken link count",
    "SEO score",
    "Current title",
    "Current description",
    "Key point up front",
    "Page modified at",
    "Content changed at",
    "Sitemap lastmod",
    "Attention",
    "Attention count",
]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    options = load_options()
    pages = Api(settings.airtable_token).table(settings.airtable_base_id, "Pages")

    now = datetime.now(UTC)
    stale_after = timedelta(options.stale_after_days)

    updates: list[UpdateRecordDict] = []
    counts: Counter[str] = Counter()

    for record in pages.all(formula="{Active}", fields=FIELDS):
        flags = find_flags(facts_from_record(record), now, stale_after)
        counts.update(flags)
        fields = flag_update(record["fields"], flags)

        if fields is not None:
            updates.append({"id": record["id"], "fields": fields})

    if updates:
        pages.batch_update(updates)

    print(f"Updated flags on {len(updates)} pages.")
    for flag in ALL_FLAGS:
        print(f"  {counts[flag]:>4}  {flag}")
