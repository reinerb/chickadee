import time
import zlib
from dataclasses import dataclass

import httpx
from defusedxml.ElementTree import fromstring

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
MAX_SITEMAPS = 50
MAX_SITEMAP_BYTES = 50 * 1024 * 1024
GZIP_MAGIC = b"\x1f\x8b"


@dataclass(frozen=True)
class SitemapEntries:
    pages: tuple[str, ...]
    sitemaps: tuple[str, ...]


class SitemapError(Exception):
    pass


def decompress(data: bytes, limit: int = MAX_SITEMAP_BYTES) -> bytes:
    if not data.startswith(GZIP_MAGIC):
        return data

    decompressor = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)
    try:
        xml = decompressor.decompress(data, limit + 1)
    except zlib.error as exc:
        raise SitemapError(f"couldn't decompress: {exc}") from None

    if len(xml) > limit:
        raise SitemapError(f"larger than {limit:,} bytes once decompressed")

    return xml


def fetch_sitemap(
    client: httpx.Client, url: str, limit: int = MAX_SITEMAP_BYTES
) -> bytes:
    chunks: list[bytes] = []
    size = 0

    with client.stream("GET", url) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            size += len(chunk)

            if size > limit:
                raise SitemapError(f"{url} is larger than {limit:,} bytes")

            chunks.append(chunk)

    try:
        return decompress(b"".join(chunks), limit)
    except SitemapError as exc:
        raise SitemapError(f"{url}: {exc}") from None


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

        entries = parse_sitemap(fetch_sitemap(client, url))
        pages.extend(entries.pages)
        to_visit.extend(entries.sitemaps)
        time.sleep(1)

    if to_visit:
        print(f"Stopped after {MAX_SITEMAPS} sitemaps. Some were not read.")

    return list(dict.fromkeys(pages))
