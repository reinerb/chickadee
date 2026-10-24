from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ImportPlan:
    to_add: tuple[str, ...]
    no_longer_listed: tuple[str, ...]


def plan_import(
    sitemap_urls: Sequence[str],
    tracked: set[str],
    *,
    contains: str | None = None,
    limit: int | None = None,
) -> ImportPlan:
    listed = set(sitemap_urls)
    hosts = {urlparse(url).netloc for url in sitemap_urls}

    no_longer_listed = tuple(
        sorted(
            url
            for url in tracked
            if urlparse(url).netloc in hosts and url not in listed
        )
    )

    to_add = [
        url
        for url in sitemap_urls
        if url not in tracked and (contains is None or contains in url)
    ]

    if limit is not None:
        to_add = to_add[:limit]

    return ImportPlan(to_add=tuple(to_add), no_longer_listed=no_longer_listed)
