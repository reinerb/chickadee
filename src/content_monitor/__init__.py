from datetime import UTC, datetime

from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from content_monitor.checker import check_url, make_client
from content_monitor.config import load_options, load_settings
from content_monitor.store import should_log, to_check_fields, to_status_fields


def main() -> None:
    settings = load_settings()
    options = load_options()

    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    checks = api.table(settings.airtable_base_id, "Checks")

    records = pages.all(formula="{Active}")
    checked_at = datetime.now(UTC)
    new_checks = []
    page_updates: list[UpdateRecordDict] = []

    with make_client() as client:
        for record in records:
            url = record["fields"]["URL"]
            previous_status = record["fields"].get("Status")
            result = check_url(client, url)

            status = "OK  " if result.ok else "FAIL"
            print(
                f"{status} {url} -> {result.status_code} "
                f"({result.response_time_ms} ms) {result.error or ''}"
            )

            page_updates.append(
                {
                    "id": record["id"],
                    "fields": to_status_fields(result, checked_at, previous_status),
                }
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
