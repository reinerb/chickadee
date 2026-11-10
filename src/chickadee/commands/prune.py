import argparse
from datetime import UTC, datetime, timedelta

from chickadee.app import App
from chickadee.commands._args import positive_int

HELP = "Delete logged checks older than the retention period."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--days",
        type=positive_int,
        help="keep checks from the last N days (default: the RETENTION_DAYS setting, or 90)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="count old checks without deleting anything",
    )


def run(args: argparse.Namespace, app: App) -> None:
    days = args.days if args.days is not None else app.settings.retention_days
    cutoff = datetime.now(UTC) - timedelta(days=days)

    old = app.checks.ids_before(cutoff)
    print(f"Found {len(old)} check(s) older than {days} days")

    if args.dry_run:
        print("Dry run: nothing was deleted")
        return
    if not old:
        return

    app.checks.delete(old)
    print(f"Deleted {len(old)} check(s).")
