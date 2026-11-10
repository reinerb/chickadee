import argparse
from datetime import UTC, datetime, timedelta

from chickadee.app import App
from chickadee.flags import ALL_FLAGS, run_flags

HELP = "Flag pages that need attention."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace, app: App) -> None:
    report = run_flags(
        app.pages,
        now=datetime.now(UTC),
        stale_after=timedelta(days=app.settings.stale_after_days),
    )

    print(f"Updated flags on {report.updated} pages.")
    for flag in ALL_FLAGS:
        print(f"  {report.counts[flag]:>4}  {flag}")
