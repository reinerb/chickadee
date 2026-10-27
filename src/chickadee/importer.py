import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

from pyairtable import Api

from chickadee.checker import make_client
from chickadee.config import load_settings
from chickadee.prune import positive_int
from chickadee.sitemap import collect_page_urls

HELP = "Add pages from a sitemap to the Pages table."


@dataclass(frozen=True)
class ImportPlan:
    to_add: tuple[str, ...]
    no_longer_listed: tuple[str, ...]


def plan_import(
    sitemap_urls: Sequence[str],
    tracked: set[str],
    *,
    contains: str | None = None,
    limit: int | None = None,
) -> ImportPlan:
    listed = set(sitemap_urls)
    hosts = {urlparse(url).netloc for url in sitemap_urls}

    no_longer_listed = tuple(
        sorted(
            url
            for url in tracked
            if urlparse(url).netloc in hosts and url not in listed
        )
    )

    to_add = [
        url
        for url in sitemap_urls
        if url not in tracked and (contains is None or contains in url)
    ]

    if limit is not None:
        to_add = to_add[:limit]

    return ImportPlan(to_add=tuple(to_add), no_longer_listed=no_longer_listed)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("sitemap_url", help="URL of a sitemap or sitemap index")
    parser.add_argument("--contains", help="only add URLs containing this text")
    parser.add_argument(
        "--limit", type=positive_int, help="add at most this many new pages"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would change without touching Airtable",
    )


def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    pages = Api(settings.airtable_token).table(settings.airtable_base_id, "Pages")

    with make_client() as client:
        sitemap_urls = collect_page_urls(client, args.sitemap_url)

    print(f"Found {len(sitemap_urls)} URL(s) in the sitemap.")

    tracked = {
        url
        for record in pages.all(fields=["URL"])
        if (url := record["fields"].get("URL"))
    }

    plan = plan_import(sitemap_urls, tracked, contains=args.contains, limit=args.limit)

    for url in plan.to_add:
        print(f"  + {url}")
    for url in plan.no_longer_listed:
        print(f"  ? {url} (tracked, but no longer in sitemap)")

    if args.dry_run:
        print(f"Dry run: would add {len(plan.to_add)} page(s). Nothing was changed.")
        return

    if plan.to_add:
        pages.batch_create({"URL": url, "Active": True} for url in plan.to_add)

    print(f"Added {len(plan.to_add)} page(s).")
