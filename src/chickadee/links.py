import logging
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urlparse

import httpx

from chickadee.checker import fetch_html
from chickadee.extractor import extract_links
from chickadee.models import LinkResult, LinkStatus, Page

log = logging.getLogger(__name__)

BROKEN_CODES = {404, 410}
MAX_LINKS_PER_PAGE = 100
PER_HOST_INTERVAL = 1.0
SAVE_EVERY = 25


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
    response = fetch_html(client, url)
    if response is None:
        return None

    links = extract_links(response.text, str(response.url), ignore=ignore)
    return links[:MAX_LINKS_PER_PAGE]


def check_links(
    client: httpx.Client,
    links: Iterable[str],
    *,
    last_request: dict[str, float],
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> dict[str, LinkResult]:
    """Check each link, pausing between requests to the same site.

    `last_request` holds when each site was last asked, and is updated, so
    the pacing carries over from one call to the next.
    """
    results: dict[str, LinkResult] = {}

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
    save_every: int = SAVE_EVERY,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> LinksReport:
    # Each link is checked once per run, however many pages it's on.
    results: dict[str, LinkResult] = {}
    last_request: dict[str, float] = {}
    unsaved: dict[str, list[LinkResult]] = {}
    pages_read = 0

    for page in pages.active():
        sleep(1)
        links = links_on_page(client, page.url, ignore=ignore)
        if links is None:
            continue
        pages_read += 1

        new = [link for link in dict.fromkeys(links) if link not in results]
        results |= check_links(
            client, new, last_request=last_request, sleep=sleep, monotonic=monotonic
        )
        unsaved[page.id] = [results[link] for link in links]

        if len(unsaved) >= save_every:
            pages.save_links(unsaved, checked_at)
            unsaved = {}

    if unsaved:
        pages.save_links(unsaved, checked_at)

    broken = sum(1 for result in results.values() if result.status == "broken")
    return LinksReport(pages=pages_read, links=len(results), broken=broken)
