import httpx
import pytest

from content_monitor.links import check_link, classify, wait_needed


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
