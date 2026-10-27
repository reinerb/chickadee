import gzip

import httpx
import pytest

from chickadee.sitemap import SitemapError, decompress, fetch_sitemap, parse_sitemap

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.org/one/</loc></url>
  <url><loc>https://example.org/two/</loc></url>
</urlset>"""

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.org/post-sitemap.xml</loc></sitemap>
</sitemapindex>"""


SITEMAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.org/about/</loc></url>
</urlset>"""


def test_urlset_returns_pages_with_whitespace_stripped():
    entries = parse_sitemap(URLSET.encode())

    assert entries.pages == ("https://example.org/one/", "https://example.org/two/")
    assert entries.sitemaps == ()


def test_index_returns_child_sitemaps():
    entries = parse_sitemap(INDEX.encode())

    assert entries.pages == ()
    assert entries.sitemaps == ("https://example.org/post-sitemap.xml",)


def test_gzipped_sitemap_is_decompressed():
    assert parse_sitemap(decompress(gzip.compress(SITEMAP))).pages == (
        "https://example.org/about/",
    )
    assert decompress(SITEMAP) == SITEMAP


def test_decompression_stops_at_the_limit():
    bomb = gzip.compress(b"\0" * 10_000)
    assert len(bomb) < 100

    with pytest.raises(SitemapError, match="larger than 1,000 bytes"):
        decompress(bomb, limit=1_000)


def test_corrupt_gzip_is_a_sitemap_error():
    with pytest.raises(SitemapError, match="couldn't decompress"):
        decompress(b"\x1f\x8b not really gzip")


def test_download_stops_at_the_limit():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 5_000))
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(SitemapError, match="larger than 1,000 bytes"),
    ):
        fetch_sitemap(client, "https://example.org/sitemap.xml", limit=1_000)


def test_fetch_handles_gzip_files():
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, content=gzip.compress(SITEMAP))
    )
    with httpx.Client(transport=transport) as client:
        assert fetch_sitemap(client, "https://example.org/sitemap.xml.gz") == SITEMAP
