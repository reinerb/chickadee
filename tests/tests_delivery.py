from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from content_monitor.digest import build_digest_payload, digest_html
from content_monitor.webhooks import post_json

NOW = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
SINCE = NOW - timedelta(days=7)
SECRET_URL = "https://hook.example.com/abc123secret"


def test_page_content_cannot_inject_html():
    html = digest_html(
        "- [Fish <script>x</script>](https://example.org/)\n"
        "- [Bad](javascript:alert(1))"
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert 'href="javascript' not in html


def make_payload(test: bool) -> dict[str, Any]:
    return build_digest_payload(
        markdown_text="# Hi",
        since=SINCE,
        until=NOW,
        new=1,
        changed=2,
        needs_attention=3,
        down=0,
        test=test,
    )


def test_test_digests_are_marked_but_shaped_the_same():
    real, test = make_payload(False), make_payload(True)

    assert real["subject"] == "Content digest: Oct 20 to Oct 27, 2026"
    assert test["subject"] == "[TEST] Content digest: Oct 20 to Oct 27, 2026"
    assert real.keys() == test.keys()
    assert "<h1>Hi</h1>" in real["html"]


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_webhook_failures_are_described_without_the_url():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"could not reach {request.url}", request=request)

    with client_for(lambda request: httpx.Response(200)) as client:
        assert post_json(client, SECRET_URL, {}) is None
    with client_for(lambda request: httpx.Response(500)) as client:
        assert post_json(client, SECRET_URL, {}) == "HTTP 500"
    with client_for(refuse) as client:
        error = post_json(client, SECRET_URL, {})

    assert error == "ConnectError"
    assert "secret" not in (error or "")
