import argparse
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from pyairtable import Api
from pyairtable.api.types import UpdateRecordDict

from chickadee.checker import make_client
from chickadee.config import load_settings
from chickadee.extractor import extract_links
from chickadee.results import LinkResult, LinkStatus
from chickadee.store import to_link_fields

HELP = "Check the links in each page's main content."

BROKEN_CODES = {404, 410}
MAX_LINKS_PER_PAGE = 100
PER_HOST_INTERVAL = 1.0


def classify(status_code: int) -> LinkStatus:
    if status_code < 400:
        return "ok"

    if status_code in BROKEN_CODES:
        return "broken"

    return "unverified"


def redirected_home(requested: httpx.URL, final: httpx.URL) -> bool:
    return requested.path not in ("", "/") and final.path in ("", "/")


def check_link(client: httpx.Client, url: str) -> LinkResult:
    try:
        with client.stream("GET", url) as response:
            code = response.status_code
            final = response.url
    except (httpx.ConnectError, httpx.InvalidURL, httpx.UnsupportedProtocol) as exc:
        return LinkResult(url, "broken", type(exc).__name__)
    except httpx.HTTPError as exc:
        return LinkResult(url, "unverified", type(exc).__name__)

    status = classify(code)
    if status == "ok" and redirected_home(httpx.URL(url), final):
        return LinkResult(url, "unverified", "redirects to homepage")

    return LinkResult(url, classify(code), str(code))


def wait_needed(last_request: float | None, now: float, interval: float) -> float:
    if last_request is None:
        return 0.0

    return max(0.0, interval - (now - last_request))


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    pages = Api(settings.airtable_token).table(settings.airtable_base_id, "Pages")
    records = pages.all(formula="{Active}", fields=["URL"])

    page_links: dict[str, list[str]] = {}
    results: dict[str, LinkResult] = {}
    last_request: dict[str, float] = {}

    with make_client() as client:
        for record in records:
            url = record["fields"]["URL"]
            time.sleep(1)

            try:
                response = client.get(url)
            except httpx.RequestError as exc:
                print(f"SKIP {url}: {type(exc).__name__}")
                continue

            if not response.is_success or "text/html" not in response.headers.get(
                "content-type", ""
            ):
                print(f"SKIP {url}: status {response.status_code}")

            links = extract_links(response.text, str(response.url))
            page_links[record["id"]] = links[:MAX_LINKS_PER_PAGE]

        unique = list(
            dict.fromkeys(link for links in page_links.values() for link in links)
        )
        print(f"Checking {len(unique)} unique link(s) on {len(page_links)} pages")

        for link in unique:
            host = urlparse(link).netloc
            time.sleep(
                wait_needed(last_request.get(host), time.monotonic(), PER_HOST_INTERVAL)
            )

            results[link] = check_link(client, link)
            last_request[host] = time.monotonic()

            if results[link].status != "ok":
                print(f"  {results[link].status:<10} {results[link].detail:<16} {link}")

    checked_at = datetime.now(UTC)
    updates: list[UpdateRecordDict] = [
        {
            "id": record_id,
            "fields": to_link_fields([results[link] for link in links], checked_at),
        }
        for record_id, links in page_links.items()
    ]

    if updates:
        pages.batch_update(updates)

    broken = sum(1 for result in results.values() if result.status == "broken")
    print(f"Done: {broken} broken link(s) out of {len(unique)} checked.")
