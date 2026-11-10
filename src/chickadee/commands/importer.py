import argparse

from pyairtable import Api

from chickadee.checker import make_client
from chickadee.commands._args import positive_int
from chickadee.config import load_settings
from chickadee.importer import new_page_fields, plan_import
from chickadee.sitemap import collect_page_urls

HELP = "Add pages from a sitemap to the Pages table."


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
        sitemap_pages = collect_page_urls(client, args.sitemap_url)

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
        pages.batch_create(
            new_page_fields(url, sitemap_pages[url]) for url in plan.to_add
        )

    print(f"Added {len(plan.to_add)} page(s).")
