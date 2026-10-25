import argparse
from datetime import UTC, datetime, timedelta

from pyairtable import Api

from content_monitor.config import load_options, load_settings


def older_than_formula(cutoff: datetime) -> str:
    stamp = cutoff.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"IS_BEFORE({{Checked at}}, DATETIME_PARSE('{stamp}'))"


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")

    return number


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete uptime checks older than a set number of days."
    )
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
    args = parser.parse_args()

    settings = load_settings()
    checks = Api(settings.airtable_token).table(settings.airtable_base_id, "Checks")
    days = args.days if args.days is not None else load_options().retention_days

    cutoff = datetime.now(UTC) - timedelta(days=days)
    old = checks.all(formula=older_than_formula(cutoff), fields=["Checked at"])
    print(f"Found {len(old)} check(s) older than {days} days")

    if args.dry_run:
        print("Dry run: nothing was deleted")
        return
    if not old:
        return

    checks.batch_delete(record["id"] for record in old)
    print(f"Deleted {len(old)} check(s).")
