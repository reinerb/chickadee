import argparse
from datetime import UTC, datetime

from chickadee.app import App
from chickadee.audit import review_setup, run_audit, submit_reviews

HELP = "Read each page, record changes, and send new or changed pages for review."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--all",
        action="store_true",
        help="review every page, even ones that haven't changed",
    )


def run(args: argparse.Namespace, app: App) -> None:
    topics = app.topics.all()
    context = app.site.context()
    setup = review_setup(topics, context)
    print(
        f"Review version {setup.version} "
        f"({'with' if context else 'without'} site context, {len(topics)} topic(s))"
    )

    audited_at = datetime.now(UTC)
    report = run_audit(
        app.pages,
        app.http,
        setup,
        ignore=app.settings.ignore_selectors,
        review_all=args.all,
        audited_at=audited_at,
    )

    changes, states = report.changes, report.states
    print(
        f"{changes['new']} new, {changes['changed']} changed, "
        f"{changes['unchanged']} unchanged."
    )
    if states["baseline"]:
        print(
            f"Recorded the review version for {states['baseline']} page(s) "
            "reviewed before versions were tracked."
        )
    if states["setup"]:
        print(
            f"{states['setup']} page(s) will be reviewed again "
            "because the review setup changed."
        )

    if not report.requests:
        print("No pages need review.")
        return

    batch_id = submit_reviews(
        app.claude_batches, app.audit_batches, report.requests, audited_at
    )
    print(f"Submitted batch {batch_id} with {len(report.requests)} page(s).")
    print("Run `uv run chickadee collect` later to save the reviews.")
