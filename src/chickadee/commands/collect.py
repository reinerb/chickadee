import argparse
from datetime import UTC, datetime

from chickadee.app import App
from chickadee.collect import run_collect

HELP = "Save finished reviews from Claude."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace, app: App) -> None:
    outcomes = run_collect(
        app.audit_batches,
        app.claude_batches,
        app.pages,
        topic_ids=app.topics.ids(),
        reviewed_at=datetime.now(UTC),
    )

    if not outcomes:
        print("No batches waiting to be collected.")
        return

    for outcome in outcomes:
        if outcome.status != "ended":
            print(f"{outcome.batch_id} still {outcome.status}")
            continue
        if outcome.missing:
            print(
                f"  skipped {outcome.missing} review(s) for pages no longer in Airtable"
            )
        print(f"{outcome.batch_id}: saved {outcome.saved} review(s)")
