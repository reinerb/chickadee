import argparse
import sys
from datetime import UTC, datetime, timedelta
from itertools import chain

from pyairtable import Api

from chickadee.airtable import checked_after, checked_before
from chickadee.app import App
from chickadee.checker import make_client
from chickadee.config import load_digest_webhook, load_settings
from chickadee.digest import (
    build_digest_payload,
    changed_pages,
    claude_input,
    digest_system_prompt,
    needs_attention,
    new_pages,
    page_item,
    render_digest,
    uptime_lines,
    write_overview,
)
from chickadee.history import find_events, latest_status
from chickadee.site_context import load_site_context
from chickadee.webhooks import post_json

HELP = "Write the weekly digest and email it."
DIGEST_DAYS = 7

PAGE_FIELDS = [
    "Name",
    "URL",
    "Active",
    "Content hash",
    "Reviewed hash",
    "Content summary",
    "Content changed at",
    "Attention",
    "Status",
    "Status since",
    "Last status code",
]


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
    settings = load_settings()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    checks = api.table(settings.airtable_base_id, "Checks")

    now = datetime.now(UTC)
    since = now - timedelta(days=DIGEST_DAYS)

    all_pages = pages.all(fields=PAGE_FIELDS)
    active = [page for page in all_pages if page["fields"].get("Active")]
    names = {page["id"]: page_item(page).name for page in all_pages}
    recent_checks = checks.all(
        formula=checked_after(since),
        fields=["Page", "Checked at", "Ok", "Status code", "Error"],
    )
    earlier_checks = chain.from_iterable(
        checks.iterate(
            formula=checked_before(since),
            sort=["-Checked at"],
            fields=["Page", "Ok", "Checked at"],
        )
    )
    initial = latest_status(earlier_checks, {page["id"] for page in active})

    new = new_pages(active, since)
    changed = changed_pages(active, since)
    flagged, flag_counts = needs_attention(active)
    down, events = uptime_lines(active, find_events(recent_checks, initial), names, now)

    overview = None
    if not args.no_overview:
        context = load_site_context(api, settings.airtable_base_id)
        overview = write_overview(
            claude_input(new, changed, flagged, down, events),
            digest_system_prompt(context),
        )

    markdown_text = render_digest(
        since=since,
        until=now,
        overview=overview,
        new=new,
        changed=changed,
        flagged=flagged,
        flag_counts=flag_counts,
        down=down,
        events=events,
    )
    print(markdown_text)

    if args.no_send:
        return

    webhook_url = load_digest_webhook()
    if not webhook_url:
        print(
            "DIGEST_WEBHOOK_URL isn't set, so the digest wasn't emailed.",
            file=sys.stderr,
        )
        return

    payload = build_digest_payload(
        markdown_text=markdown_text,
        since=since,
        until=now,
        new=len(new),
        changed=len(changed),
        needs_attention=len(flagged),
        down=len(down),
        test=args.test,
    )

    with make_client() as client:
        error = post_json(client, webhook_url, payload)

    if error:
        print(f"Digest delivery failed: {error}", file=sys.stderr)
        sys.exit(1)

    print("Digest emailed.", file=sys.stderr)
