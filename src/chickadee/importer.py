import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pyairtable import Api

from chickadee.checker import make_client
from chickadee.config import load_settings
from chickadee.prune import positive_int
from chickadee.sitemap import SitemapError, collect_page_urls

HELP = "Add pages from a sitemap to the Pages table."


@dataclass(frozen=True)
class ImportPlan:
    to_add: tuple[str, ...]
    no_longer_listed: tuple[str, ...]


def url_key(url: str) -> str:
    parts = urlsplit(url.strip())

    return urlunsplit(
        ("", parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


def new_page_fields(url: str, lastmod: datetime | None) -> dict[str, Any]:
    fields: dict[str, Any] = {"URL": url, "Active": True}
    if lastmod is not None:
        fields["Sitemap lastmod"] = lastmod.isoformat()
    return fields


def plan_import(
    sitemap_urls: Sequence[str],
    tracked: set[str],
    *,
    contains: str | None = None,
    limit: int | None = None,
) -> ImportPlan:
    listed = {url_key(url) for url in sitemap_urls}
    hosts = {urlsplit(url).hostname for url in sitemap_urls}

    no_longer_listed = tuple(
        sorted(
            url
            for url in tracked
            if urlsplit(url).hostname in hosts and url_key(url) not in listed
        )
    )

    seen = {url_key(url) for url in tracked}
    to_add: list[str] = []

    for url in sitemap_urls:
        if contains is not None and contains not in url:
            continue

        key = url_key(url)
        if key not in seen:
            seen.add(key)
            to_add.append(url)

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
        try:
            sitemap_pages = collect_page_urls(client, args.sitemap_url)
        except SitemapError as exc:
            raise SystemExit(f"Couldn't read the sitemap: {exc}") from None

    print(f"Found {len(sitemap_pages)} URL(s) in the sitemap.")

    tracked = {
        url
        for record in pages.all(fields=["URL"])
        if (url := record["fields"].get("URL"))
    }

    plan = plan_import(
        list(sitemap_pages), tracked, contains=args.contains, limit=args.limit
    )

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
