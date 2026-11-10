import argparse
from datetime import UTC, datetime

from chickadee.app import App
from chickadee.links import run_links

HELP = "Check the links in each page's main content."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace, app: App) -> None:
    report = run_links(
        app.pages,
        app.http,
        ignore=app.options.ignore_selectors,
        checked_at=datetime.now(UTC),
    )
    print(f"Done: {report.broken} broken link(s) out of {report.links} checked.")
