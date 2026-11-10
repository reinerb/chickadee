import httpx

from chickadee.extractor import extract_links
from chickadee.models import LinkResult, LinkStatus

BROKEN_CODES = {404, 410}
MAX_LINKS_PER_PAGE = 100
PER_HOST_INTERVAL = 1.0


def classify(status_code: int) -> LinkStatus:
    if status_code < 400:
        return "ok"

    if status_code in BROKEN_CODES:
        return "broken"

    return "unverified"


def redirected_home(requested: httpx.URL, final: httpx.URL) -> bool:
    return requested.path not in ("", "/") and final.path in ("", "/")


def check_link(client: httpx.Client, url: str) -> LinkResult:
    try:
        with client.stream("GET", url) as response:
            code = response.status_code
            final = response.url
    except (httpx.ConnectError, httpx.InvalidURL, httpx.UnsupportedProtocol) as exc:
        return LinkResult(url, "broken", type(exc).__name__)
    except httpx.HTTPError as exc:
        return LinkResult(url, "unverified", type(exc).__name__)

    status = classify(code)
    if status == "ok" and redirected_home(httpx.URL(url), final):
        return LinkResult(url, "unverified", "redirects to homepage")

    return LinkResult(url, status, str(code))


def wait_needed(last_request: float | None, now: float, interval: float) -> float:
    if last_request is None:
        return 0.0

    return max(0.0, interval - (now - last_request))


def links_on_page(
    client: httpx.Client, url: str, *, ignore: str | None
) -> list[str] | None:
    """The links in a page's main content, or None if it can't be read."""
    try:
        response = client.get(url)
    except httpx.RequestError as exc:
        print(f"SKIP {url}: {type(exc).__name__}")
        return None

    if not response.is_success or "text/html" not in response.headers.get(
        "content-type", ""
    ):
        print(f"SKIP {url}: status {response.status_code}")
        return None

    links = extract_links(response.text, str(response.url), ignore=ignore)
    return links[:MAX_LINKS_PER_PAGE]
