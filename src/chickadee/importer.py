from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class ImportPlan:
    to_add: tuple[str, ...]
    no_longer_listed: tuple[str, ...]


def url_key(url: str) -> str:
    parts = urlsplit(url.strip())

    return urlunsplit(
        ("", parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


def new_page_fields(url: str, lastmod: datetime | None) -> dict[str, Any]:
    fields: dict[str, Any] = {"URL": url, "Active": True}
    if lastmod is not None:
        fields["Sitemap lastmod"] = lastmod.isoformat()
    return fields


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
