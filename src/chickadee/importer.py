import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

from chickadee.sitemap import collect_page_urls


@dataclass(frozen=True)
class ImportPlan:
    to_add: tuple[str, ...]
    no_longer_listed: tuple[str, ...]


@dataclass(frozen=True)
class ImportReport:
    found: int
    plan: ImportPlan


class ImportPages(Protocol):
    """What run_import needs from wherever pages are kept."""

    def tracked_urls(self) -> set[str]: ...

    def add(self, pages: Mapping[str, datetime | None]) -> None: ...


def url_key(url: str) -> str:
    parts = urlsplit(url.strip())

    return urlunsplit(
        ("", parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


def plan_import(
    sitemap_urls: Sequence[str],
    tracked: set[str],
    *,
    contains: str | None = None,
    limit: int | None = None,
) -> ImportPlan:
    listed = {url_key(url) for url in sitemap_urls}
    hosts = {urlsplit(url).hostname for url in sitemap_urls}

    no_longer_listed = tuple(
        sorted(
            url
            for url in tracked
            if urlsplit(url).hostname in hosts and url_key(url) not in listed
        )
    )

    seen = {url_key(url) for url in tracked}
    to_add: list[str] = []

    for url in sitemap_urls:
        if contains is not None and contains not in url:
            continue

        key = url_key(url)
        if key not in seen:
            seen.add(key)
            to_add.append(url)

    if limit is not None:
        to_add = to_add[:limit]

    return ImportPlan(to_add=tuple(to_add), no_longer_listed=no_longer_listed)


def run_import(
    pages: ImportPages,
    client: httpx.Client,
    sitemap_url: str,
    *,
    contains: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> ImportReport:
    """Plan an import from the sitemap, and carry it out unless it's a dry run."""
    listed = collect_page_urls(client, sitemap_url, sleep=sleep)
    plan = plan_import(
        list(listed), pages.tracked_urls(), contains=contains, limit=limit
    )

    if not dry_run:
        pages.add({url: listed[url] for url in plan.to_add})

    return ImportReport(found=len(listed), plan=plan)
