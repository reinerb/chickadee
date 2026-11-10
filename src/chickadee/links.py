import logging
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urlparse

import httpx

from chickadee.extractor import extract_links
from chickadee.models import LinkResult, LinkStatus, Page

log = logging.getLogger(__name__)

BROKEN_CODES = {404, 410}
MAX_LINKS_PER_PAGE = 100
PER_HOST_INTERVAL = 1.0


@dataclass(frozen=True)
class LinksReport:
    pages: int
    links: int
    broken: int


class LinkPages(Protocol):
    """What run_links needs from wherever pages are kept."""

    def active(self) -> Iterable[Page]: ...

    def save_links(
        self, results: Mapping[str, Sequence[LinkResult]], checked_at: datetime
    ) -> None: ...


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

    return LinkResult(url, status, str(code))


def wait_needed(last_request: float | None, now: float, interval: float) -> float:
    if last_request is None:
        return 0.0

    return max(0.0, interval - (now - last_request))


def links_on_page(
    client: httpx.Client, url: str, *, ignore: str | None
) -> list[str] | None:
    """The links in a page's main content, or None if it can't be read."""
    try:
        response = client.get(url)
    except httpx.RequestError as exc:
        log.warning("SKIP %s: %s", url, type(exc).__name__)
        return None

    if not response.is_success or "text/html" not in response.headers.get(
        "content-type", ""
    ):
        log.warning("SKIP %s: status %s", url, response.status_code)
        return None

    links = extract_links(response.text, str(response.url), ignore=ignore)
    return links[:MAX_LINKS_PER_PAGE]


def check_links(
    client: httpx.Client,
    links: Iterable[str],
    *,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> dict[str, LinkResult]:
    """Check each link, pausing between requests to the same site."""
    results: dict[str, LinkResult] = {}
    last_request: dict[str, float] = {}

    for link in links:
        host = urlparse(link).netloc
        sleep(wait_needed(last_request.get(host), monotonic(), PER_HOST_INTERVAL))

        result = check_link(client, link)
        last_request[host] = monotonic()
        results[link] = result

        if result.status != "ok":
            log.info("  %-10s %-16s %s", result.status, result.detail, link)

    return results


def run_links(
    pages: LinkPages,
    client: httpx.Client,
    *,
    ignore: str | None,
    checked_at: datetime,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> LinksReport:
    found: dict[str, list[str]] = {}
    for page in pages.active():
        sleep(1)
        links = links_on_page(client, page.url, ignore=ignore)
        if links is not None:
            found[page.id] = links

    unique = list(dict.fromkeys(link for links in found.values() for link in links))
    log.info("Checking %d unique link(s) on %d pages", len(unique), len(found))
    results = check_links(client, unique, sleep=sleep, monotonic=monotonic)

    pages.save_links(
        {
            page_id: [results[link] for link in links]
            for page_id, links in found.items()
        },
        checked_at,
    )

    broken = sum(1 for result in results.values() if result.status == "broken")
    return LinksReport(pages=len(found), links=len(unique), broken=broken)
