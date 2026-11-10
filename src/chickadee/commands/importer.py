import argparse

from chickadee.app import App
from chickadee.commands._args import positive_int
from chickadee.importer import run_import

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


def run(args: argparse.Namespace, app: App) -> None:
    report = run_import(
        app.pages,
        app.http,
        args.sitemap_url,
        contains=args.contains,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    plan = report.plan

    print(f"Found {report.found} URL(s) in the sitemap.")
    for url in plan.to_add:
        print(f"  + {url}")
    for url in plan.no_longer_listed:
        print(f"  ? {url} (tracked, but no longer in sitemap)")

    if args.dry_run:
        print(f"Dry run: would add {len(plan.to_add)} page(s). Nothing was changed.")
        return

    print(f"Added {len(plan.to_add)} page(s).")
