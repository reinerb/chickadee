import httpx
import pytest

from chickadee.checker import CheckResult, check_pages, fetch_html, should_log


def make_result(ok: bool) -> CheckResult:
    return CheckResult(
        url="https://example.org",
        ok=ok,
        status_code=200 if ok else 503,
        response_time_ms=100,
        error=None,
    )


def serving(response: httpx.Response) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda request: response))


def test_changes_mode_logs_only_when_status_changes():
    assert should_log("Up", make_result(ok=False), "changes")
    assert not should_log("Up", make_result(ok=True), "changes")


def test_first_check_is_always_logged():
    assert should_log(None, make_result(ok=True), "changes")


def test_all_mode_logs_every_check():
    assert should_log("Up", make_result(ok=True), "all")


def test_failed_pages_are_checked_once_more_after_one_pause():
    calls: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls[path] = calls.get(path, 0) + 1
        if path == "/blip" and calls[path] == 1:
            raise httpx.ConnectError("dropped", request=request)
        if path == "/down":
            return httpx.Response(503)
        return httpx.Response(200)

    pauses: list[float] = []
    urls = {
        "a": "https://example.org/ok",
        "b": "https://example.org/blip",
        "c": "https://example.org/down",
    }
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        results = check_pages(client, urls, retry_delay=30, sleep=pauses.append)

    assert [results[key].ok for key in "abc"] == [True, True, False]
    assert pauses == [30]
    assert calls == {"/ok": 1, "/blip": 2, "/down": 2}


def test_no_pause_when_everything_is_up():
    pauses: list[float] = []
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200))
    ) as client:
        check_pages(client, {"a": "https://example.org/"}, sleep=pauses.append)

    assert pauses == []


def test_fetch_html_returns_html_pages():
    response = fetch_html(
        serving(httpx.Response(200, html="<p>Hi</p>")), "https://example.org"
    )

    assert response is not None
    assert response.text == "<p>Hi</p>"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, html="<p>Gone</p>"),
        httpx.Response(200, json={"not": "html"}),
    ],
    ids=["error-status", "not-html"],
)
def test_fetch_html_skips_pages_it_cant_read(response: httpx.Response):
    assert fetch_html(serving(response), "https://example.org") is None


def test_fetch_html_skips_unreachable_pages():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(refuse))

    assert fetch_html(client, "https://example.org") is None
