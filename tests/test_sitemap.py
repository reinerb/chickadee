from content_monitor.sitemap import parse_sitemap

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.org/one/</loc></url>
  <url><loc>https://example.org/two/</loc></url>
</urlset>"""

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.org/post-sitemap.xml</loc></sitemap>
</sitemapindex>"""


def test_urlset_returns_pages_with_whitespace_stripped():
    entries = parse_sitemap(URLSET.encode())

    assert entries.pages == ("https://example.org/one/", "https://example.org/two/")
    assert entries.sitemaps == ()


def test_index_returns_child_sitemaps():
    entries = parse_sitemap(INDEX.encode())

    assert entries.pages == ()
    assert entries.sitemaps == ("https://example.org/post-sitemap.xml",)
