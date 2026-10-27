import httpx

from chickadee.checker import check_pages


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
