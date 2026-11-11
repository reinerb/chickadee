import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx

from chickadee.config import CheckLog
from chickadee.models import Status

log = logging.getLogger(__name__)

RETRY_DELAY = 30.0


@dataclass(frozen=True)
class CheckResult:
    url: str
    ok: bool
    status_code: int | None
    response_time_ms: int | None
    error: str | None


def check_url(client: httpx.Client, url: str) -> CheckResult:
    start = time.perf_counter()

    try:
        response = client.get(url)
    except httpx.RequestError as exc:
        return CheckResult(
            url=url,
            ok=False,
            status_code=None,
            response_time_ms=None,
            error=f"{type(exc).__name__}: {exc}",
        )

    elapsed_ms = round((time.perf_counter() - start) * 1000)
    return CheckResult(
        url=url,
        ok=response.is_success,
        status_code=response.status_code,
        response_time_ms=elapsed_ms,
        error=None,
    )


def fetch_html(client: httpx.Client, url: str) -> httpx.Response | None:
    """The response for an HTML page, or None if the page can't be read."""
    try:
        response = client.get(url)
    except httpx.RequestError as exc:
        log.warning("SKIP %s: %s", url, type(exc).__name__)
        return None

    content_type = response.headers.get("content-type", "")
    if not response.is_success or "text/html" not in content_type:
        log.warning(
            "SKIP %s: status %s, %s",
            url,
            response.status_code,
            content_type or "no content type",
        )
        return None

    return response


def status_of(result: CheckResult) -> Status:
    return "Up" if result.ok else "Down"


def should_log(
    previous_status: Status | None, result: CheckResult, check_log: CheckLog
) -> bool:
    if check_log == "all":
        return True

    return previous_status != status_of(result)


def check_pages(
    client: httpx.Client,
    urls: Mapping[str, str],
    retry_delay: float = RETRY_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, CheckResult]:
    results = {key: check_url(client, url) for key, url in urls.items()}
    failing = [key for key, result in results.items() if not result.ok]

    if failing:
        sleep(retry_delay)
        for key in failing:
            results[key] = check_url(client, urls[key])

    return results


def make_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": "Chickadee (+https://github.com/reinerb/chickadee)"},
    )
