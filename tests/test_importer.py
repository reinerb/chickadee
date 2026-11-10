from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import pytest

from chickadee.importer import plan_import, run_import, url_key

SITEMAP = [
    "https://example.org/research/a/",
    "https://example.org/research/b/",
    "https://example.org/about/",
]
SITEMAP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.org/new/</loc><lastmod>2026-03-01</lastmod></url>
  <url><loc>https://example.org/undated/</loc></url>
  <url><loc>https://example.org/tracked/</loc></url>
</urlset>"""


class FakePages:
    def __init__(self, *tracked: str) -> None:
        self.tracked = set(tracked)
        self.added: dict[str, datetime | None] = {}

    def tracked_urls(self) -> set[str]:
        return self.tracked

    def add(self, pages: Mapping[str, datetime | None]) -> None:
        self.added = dict(pages)


def sitemap_client() -> httpx.Client:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=SITEMAP_XML)
    )
    return httpx.Client(transport=transport)


def test_only_untracked_pages_are_added():
    plan = plan_import(SITEMAP, {"https://example.org/about/"})

    assert plan.to_add == (
        "https://example.org/research/a/",
        "https://example.org/research/b/",
    )


def test_contains_filter_and_limit_apply_in_order():
    plan = plan_import(SITEMAP, set(), contains="/research/", limit=1)

    assert plan.to_add == ("https://example.org/research/a/",)


def test_missing_pages_are_reported_only_for_the_sitemaps_domain():
    tracked = {"https://example.org/old-page/", "https://other-site.com/page/"}

    plan = plan_import(SITEMAP, tracked)

    assert plan.no_longer_listed == ("https://example.org/old-page/",)


def test_contains_filter_does_not_flag_unfiltered_pages_as_missing():
    plan = plan_import(SITEMAP, {"https://example.org/about/"}, contains="/research/")

    assert plan.no_longer_listed == ()


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("https://example.org/page", "https://example.org/page/"),
        ("https://Example.ORG/page/", "https://example.org/page/"),
        ("http://example.org/page/", "https://example.org/page/"),
        ("https://example.org/page/#top", "https://example.org/page/"),
        ("https://example.org", "https://example.org/"),
        (" https://example.org/page/ ", "https://example.org/page/"),
    ],
)
def test_same_page_written_differently(a, b):
    assert url_key(a) == url_key(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("https://example.org/Page/", "https://example.org/page/"),
        ("https://example.org/page/?id=1", "https://example.org/page/?id=2"),
        ("https://www.example.org/page/", "https://example.org/page/"),
    ],
)
def test_different_pages_stay_different(a, b):
    assert url_key(a) != url_key(b)


def test_plan_matches_urls_written_differently():
    plan = plan_import(
        [
            "https://example.org/about/",
            "https://example.org/about",
            "https://example.org/new/",
        ],
        {"http://example.org/about", "https://example.org/gone/"},
    )

    assert plan.to_add == ("https://example.org/new/",)
    assert plan.no_longer_listed == ("https://example.org/gone/",)


def test_new_pages_are_added_with_their_lastmod():
    pages = FakePages("https://example.org/tracked/")

    report = run_import(
        pages,
        sitemap_client(),
        "https://example.org/sitemap.xml",
        sleep=lambda seconds: None,
    )

    assert report.found == 3
    assert pages.added == {
        "https://example.org/new/": datetime(2026, 3, 1, tzinfo=UTC),
        "https://example.org/undated/": None,
    }


def test_a_dry_run_adds_nothing():
    pages = FakePages()

    report = run_import(
        pages,
        sitemap_client(),
        "https://example.org/sitemap.xml",
        dry_run=True,
        sleep=lambda seconds: None,
    )

    assert len(report.plan.to_add) == 3
    assert pages.added == {}
