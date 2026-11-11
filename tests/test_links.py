from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import httpx
import pytest

from chickadee.links import (
    LinksReport,
    check_link,
    classify,
    links_on_page,
    redirected_home,
    run_links,
    wait_needed,
)
from chickadee.models import LinkResult, Page

PAGE = '<main><a href="/one">One</a> <a href="https://other.org/two">Two</a></main>'
NOW = datetime(2026, 11, 10, tzinfo=UTC)


class FakePages:
    def __init__(self, *pages: Page) -> None:
        self.pages = pages
        self.saved: dict[str, Sequence[LinkResult]] = {}
        self.saves = 0
        self.checked_at: datetime | None = None

    def active(self) -> tuple[Page, ...]:
        return self.pages

    def save_links(
        self, results: Mapping[str, Sequence[LinkResult]], checked_at: datetime
    ) -> None:
        self.saved.update(results)
        self.saves += 1
        self.checked_at = checked_at


def fake_site(request: httpx.Request) -> httpx.Response:
    routes = {
        "/post": httpx.Response(200, html=PAGE),
        "/missing": httpx.Response(404, html='<main><a href="/never">x</a></main>'),
        "/one": httpx.Response(200, html="fine"),
        "/two": httpx.Response(404, html="gone"),
    }
    return routes[request.url.path]


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_status_codes_are_classified_cautiously():
    assert classify(200) == "ok"
    assert classify(301) == "ok"
    assert classify(404) == "broken"
    assert classify(410) == "broken"
    assert classify(403) == "unverified"
    assert classify(503) == "unverified"


def test_missing_page_is_broken():
    with client_for(lambda request: httpx.Response(404)) as client:
        assert check_link(client, "https://example.org/gone").status == "broken"


def test_rate_limited_link_is_unverified():
    with client_for(lambda request: httpx.Response(429)) as client:
        result = check_link(client, "https://example.org/busy")

    assert (result.status, result.detail) == ("unverified", "429")


def test_redirects_are_followed():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"Location": "https://example.org/new"})
        return httpx.Response(200)

    with client_for(handler) as client:
        assert check_link(client, "https://example.org/old").status == "ok"


def test_connection_failures_are_broken_but_timeouts_are_not():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no such host", request=request)

    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with client_for(refuse) as client:
        assert check_link(client, "https://gone.invalid/").status == "broken"
    with client_for(stall) as client:
        assert check_link(client, "https://slow.example/").status == "unverified"


def test_waits_only_for_the_rest_of_the_interval():
    assert wait_needed(None, 100.0, 1.0) == 0.0
    assert wait_needed(99.7, 100.0, 1.0) == pytest.approx(0.7)
    assert wait_needed(90.0, 100.0, 1.0) == 0.0


@pytest.mark.parametrize(
    ("requested", "final", "expected"),
    [
        ("https://example.org/old-report/", "https://example.org/", True),
        ("https://old.example.org/report", "https://example.org", True),
        ("https://example.org/", "https://example.org/", False),
        ("https://example.org", "https://www.example.org/", False),
        ("https://example.org/old/", "https://example.org/new/", False),
    ],
)
def test_redirect_to_homepage(requested, final, expected):
    assert redirected_home(httpx.URL(requested), httpx.URL(final)) is expected


def test_link_that_lands_on_the_homepage_is_unverified():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200)
        return httpx.Response(301, headers={"Location": "https://example.org/"})

    with client_for(handler) as client:
        result = check_link(client, "https://example.org/retired-page/")
        home = check_link(client, "https://example.org/")

    assert (result.status, result.detail) == ("unverified", "redirects to homepage")
    assert (home.status, home.detail) == ("ok", "200")


def test_links_come_from_the_page():
    client = client_for(lambda request: httpx.Response(200, html=PAGE))

    links = links_on_page(client, "https://example.org/post", ignore=None)

    assert links == ["https://example.org/one", "https://other.org/two"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, html=PAGE),
        httpx.Response(500, html=PAGE),
        httpx.Response(200, json={"links": ["/one"]}),
    ],
    ids=["missing", "server-error", "not-html"],
)
def test_unreadable_pages_are_skipped(response: httpx.Response):
    client = client_for(lambda request: response)

    assert links_on_page(client, "https://example.org/post", ignore=None) is None


def test_unreachable_pages_are_skipped():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = client_for(handler)

    assert links_on_page(client, "https://example.org/post", ignore=None) is None


def test_run_links_saves_results_for_readable_pages_only():
    store = FakePages(
        Page(id="recPost", created_at=NOW, url="https://example.org/post"),
        Page(id="recMissing", created_at=NOW, url="https://example.org/missing"),
    )
    client = client_for(fake_site)

    report = run_links(
        store,
        client,
        ignore=None,
        checked_at=NOW,
        sleep=lambda seconds: None,
    )

    # The 404 page is skipped, not mined for links.
    assert set(store.saved) == {"recPost"}
    assert [(r.url, r.status) for r in store.saved["recPost"]] == [
        ("https://example.org/one", "ok"),
        ("https://other.org/two", "broken"),
    ]
    assert store.checked_at == NOW
    assert report == LinksReport(pages=1, links=2, broken=1)


def test_results_are_saved_as_the_run_goes_and_links_checked_once():
    requested: list[str] = []

    def site(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path.startswith("/post"):
            return httpx.Response(200, html='<main><a href="/shared">s</a></main>')
        return httpx.Response(200, html="fine")

    store = FakePages(
        *(
            Page(id=f"rec{n}", created_at=NOW, url=f"https://example.org/post{n}")
            for n in range(3)
        )
    )

    run_links(
        store,
        client_for(site),
        ignore=None,
        checked_at=NOW,
        save_every=2,
        sleep=lambda seconds: None,
    )

    assert store.saves == 2  # two pages, then the last one
    assert set(store.saved) == {"rec0", "rec1", "rec2"}
    assert requested.count("/shared") == 1
