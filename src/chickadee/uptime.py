import argparse
import sys
from datetime import UTC, datetime

from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from chickadee.alerts import (
    PendingAlert,
    build_alert,
    decide_alert,
    deliver_alerts,
    down_since,
    status_of,
)
from chickadee.checker import check_pages, make_client
from chickadee.config import load_alert_webhook, load_options, load_settings
from chickadee.store import should_log, to_check_fields, to_status_fields

HELP = "Check that every active page is up, and send alerts for changes."

FIELDS = ["URL", "Name", "Status", "Status since", "Alerted status"]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    options = load_options()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    checks = api.table(settings.airtable_base_id, "Checks")

    records = pages.all(formula="{Active}", fields=FIELDS)
    checked_at = datetime.now(UTC)

    with make_client() as client:
        results = check_pages(client, {r["id"]: r["fields"]["URL"] for r in records})

    new_checks = []
    page_updates: list[UpdateRecordDict] = []
    pending: list[PendingAlert] = []

    for record in records:
        fields = record["fields"]
        url = fields["URL"]
        result = results[record["id"]]
        previous_status = fields.get("Status")
        status = status_of(result)

        label = "OK  " if result.ok else "FAIL"
        print(
            f"{label} {url} -> {result.status_code} "
            f"({result.response_time_ms} ms) {result.error or ''}"
        )

        update = to_status_fields(result, checked_at, previous_status)
        action = decide_alert(fields.get("Alerted status"), status)
        if action == "record":
            update["Alerted status"] = status
        elif action == "send":
            since = fields.get("Status since")
            payload = build_alert(
                name=fields.get("Name") or url,
                url=url,
                result=result,
                down_since=down_since(
                    previous_status,
                    datetime.fromisoformat(since) if since else None,
                    result.ok,
                    checked_at,
                ),
                checked_at=checked_at,
            )
            pending.append(PendingAlert(record["id"], status, payload))
        page_updates.append({"id": record["id"], "fields": update})

        if should_log(previous_status, result, options.check_log):
            new_checks.append(to_check_fields(record["id"], result, checked_at))

    if new_checks:
        checks.batch_create(new_checks)
    if page_updates:
        pages.batch_update(page_updates)
    print(
        f"Updated {len(page_updates)} page(s); logged {len(new_checks)} check(s) "
        f"in '{options.check_log}' mode."
    )

    if not pending:
        return
    webhook_url = load_alert_webhook()
    if not webhook_url:
        print(f"{len(pending)} alert(s) due, but ALERT_WEBHOOK_URL isn't set.")
        return

    with make_client() as client:
        delivered = deliver_alerts(client, webhook_url, pending)
    if delivered:
        pages.batch_update(
            [
                {"id": alert.record_id, "fields": {"Alerted status": alert.status}}
                for alert in delivered
            ]
        )
    print(f"Sent {len(delivered)} of {len(pending)} alert(s).")
    if len(delivered) < len(pending):
        sys.exit(1)
