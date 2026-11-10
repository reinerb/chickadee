import argparse
import sys
from datetime import UTC, datetime, timedelta

from chickadee.app import App
from chickadee.config import load_digest_webhook
from chickadee.digest import build_digest, digest_system_prompt, write_overview
from chickadee.errors import ChickadeeError
from chickadee.webhooks import post_json

HELP = "Write the weekly digest and email it."
DIGEST_DAYS = 7


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-overview",
        action="store_true",
        help="skip Claude's opening paragraph",
    )
    parser.add_argument("--test", action="store_true", help="mark the email as a test")
    parser.add_argument(
        "--no-send", action="store_true", help="print the digest without emailing it"
    )


def run(args: argparse.Namespace, app: App) -> None:
    until = datetime.now(UTC)
    since = until - timedelta(days=DIGEST_DAYS)

    def overview(content: str) -> str | None:
        system = digest_system_prompt(app.site.context())
        return write_overview(app.claude, content, system)

    digest = build_digest(
        app.pages,
        app.checks,
        since=since,
        until=until,
        overview=None if args.no_overview else overview,
    )
    # stdout is the digest itself: the workflow saves it as the job summary.
    print(digest.markdown)

    if args.no_send:
        return

    webhook_url = load_digest_webhook()
    if not webhook_url:
        print(
            "DIGEST_WEBHOOK_URL isn't set, so the digest wasn't emailed.",
            file=sys.stderr,
        )
        return

    error = post_json(app.http, webhook_url, digest.payload(test=args.test))
    if error:
        raise ChickadeeError(f"Digest delivery failed: {error}")

    print("Digest emailed.", file=sys.stderr)
