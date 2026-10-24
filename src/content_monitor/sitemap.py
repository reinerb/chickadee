import time
from dataclasses import dataclass

import httpx
from defusedxml.ElementTree import fromstring

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
MAX_SITEMAPS = 50


@dataclass(frozen=True)
class SitemapEntries:
    pages: tuple[str, ...]
    sitemaps: tuple[str, ...]


def parse_sitemap(xml: bytes | str) -> SitemapEntries:
    root = fromstring(xml)
    pages = tuple(
        loc.text.strip() for loc in root.findall("sm:url/sm:loc", NS) if loc.text
    )
    sitemaps = tuple(
        loc.text.strip() for loc in root.findall("sm:sitemap/sm:loc", NS) if loc.text
    )
    return SitemapEntries(pages, sitemaps)


def collect_page_urls(client: httpx.Client, sitemap_url: str) -> list[str]:
    to_visit = [sitemap_url]
    visited: set[str] = set()
    pages: list[str] = []

    while to_visit and len(visited) < MAX_SITEMAPS:
        url = to_visit.pop()
        if url in visited:
            continue
        visited.add(url)

        response = client.get(url)
        response.raise_for_status()
        entries = parse_sitemap(response.content)
        pages.extend(entries.pages)
        to_visit.extend(entries.sitemaps)
        time.sleep(1)

    if to_visit:
        print(f"Stopped after {MAX_SITEMAPS} sitemaps. Some were not read.")

    return list(dict.fromkeys(pages))
