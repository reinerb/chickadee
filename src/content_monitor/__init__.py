from datetime import UTC, datetime

import httpx
from pyairtable import Api

from content_monitor.checker import check_url
from content_monitor.config import load_settings
from content_monitor.store import to_check_fields


def main() -> None:
    settings = load_settings()

    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    checks = api.table(settings.airtable_base_id, "Checks")

    records = pages.all(formula="{Active}")
    checked_at = datetime.now(UTC)
    rows = []

    with httpx.Client(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": "content-monitor (learning project)"},
    ) as client:
        for record in records:
            url = record["fields"]["URL"]
            result = check_url(client, url)
            status = "OK  " if result.ok else "FAIL"
            print(
                f"{status} {url} -> {result.status_code} "
                f"({result.response_time_ms} ms) {result.error or ''}"
            )
            rows.append(to_check_fields(record["id"], result, checked_at))

    checks.batch_create(rows)
    print(f"Saved {len(rows)} check(s) to Airtable")
