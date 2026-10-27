import argparse
import sys
from datetime import UTC, datetime
from typing import Any

from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from chickadee.alerts import build_alert, send_alerts, should_alert, status_of
from chickadee.checker import check_url, make_client
from chickadee.config import load_alert_webhook, load_options, load_settings
from chickadee.store import should_log, to_check_fields, to_status_fields

HELP = "Check that every active page is up, and send alerts for changes."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    options = load_options()

    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    checks = api.table(settings.airtable_base_id, "Checks")

    records = pages.all(
        formula="{Active}", fields=["URL", "Name", "Status", "Status since"]
    )
    checked_at = datetime.now(UTC)
    new_checks = []
    page_updates: list[UpdateRecordDict] = []
    alerts: list[dict[str, Any]] = []

    with make_client() as client:
        for record in records:
            url = record["fields"]["URL"]
            previous_status = record["fields"].get("Status")
            result = check_url(client, url)

            status_label = "OK  " if result.ok else "FAIL"
            print(
                f"{status_label} {url} -> {result.status_code} "
                f"({result.response_time_ms} ms) {result.error or ''}"
            )

            page_updates.append(
                {
                    "id": record["id"],
                    "fields": to_status_fields(result, checked_at, previous_status),
                }
            )

            status = status_of(result)
            if should_alert(previous_status, status):
                since = record["fields"].get("Status since")
                alerts.append(
                    build_alert(
                        name=record["fields"].get("Name") or url,
                        url=url,
                        result=result,
                        previous_since=datetime.fromisoformat(since) if since else None,
                        checked_at=checked_at,
                    )
                )

            if should_log(previous_status, result, options.check_log):
                new_checks.append(to_check_fields(record["id"], result, checked_at))
    if new_checks:
        checks.batch_create(new_checks)
    pages.batch_update(page_updates)
    print(
        f"Updated {len(page_updates)} page(s); logged {len(new_checks)} check(s) "
        f"in '{options.check_log}' mode."
    )

    webhook_url = load_alert_webhook()
    if alerts and webhook_url:
        with make_client() as client:
            failures = send_alerts(client, webhook_url, alerts)

        print(f"Sent {len(alerts) - failures} of {len(alerts)} alert(s).")

        if failures:
            sys.exit(1)
    elif alerts:
        print(f"{len(alerts)} status change(s), but ALERT_WEBHOOK_URL isn't set.")
