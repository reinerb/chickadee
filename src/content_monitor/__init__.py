import httpx
from pyairtable import Api

from content_monitor.checker import check_url
from content_monitor.config import load_settings


def main() -> None:
    settings = load_settings()

    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")

    records = pages.all(formula="{Active}")

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
