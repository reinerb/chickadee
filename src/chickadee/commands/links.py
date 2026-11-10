import argparse
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from chickadee.airtable import to_link_fields
from chickadee.checker import make_client
from chickadee.config import load_options, load_settings
from chickadee.links import (
    PER_HOST_INTERVAL,
    LinkResult,
    check_link,
    links_on_page,
    wait_needed,
)

HELP = "Check the links in each page's main content."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    options = load_options()
    pages = Api(settings.airtable_token).table(settings.airtable_base_id, "Pages")
    records = pages.all(formula="{Active}", fields=["URL"])

    page_links: dict[str, list[str]] = {}
    results: dict[str, LinkResult] = {}
    last_request: dict[str, float] = {}

    with make_client() as client:
        for record in records:
            time.sleep(1)
            links = links_on_page(
                client, record["fields"]["URL"], ignore=options.ignore_selectors
            )
            if links is not None:
                page_links[record["id"]] = links

        unique = list(
            dict.fromkeys(link for links in page_links.values() for link in links)
        )
        print(f"Checking {len(unique)} unique link(s) on {len(page_links)} pages")

        for link in unique:
            host = urlparse(link).netloc
            time.sleep(
                wait_needed(last_request.get(host), time.monotonic(), PER_HOST_INTERVAL)
            )

            results[link] = check_link(client, link)
            last_request[host] = time.monotonic()

            if results[link].status != "ok":
                print(f"  {results[link].status:<10} {results[link].detail:<16} {link}")

    checked_at = datetime.now(UTC)
    updates: list[UpdateRecordDict] = [
        {
            "id": record_id,
            "fields": to_link_fields([results[link] for link in links], checked_at),
        }
        for record_id, links in page_links.items()
    ]

    if updates:
        pages.batch_update(updates)

    broken = sum(1 for result in results.values() if result.status == "broken")
    print(f"Done: {broken} broken link(s) out of {len(unique)} checked.")
