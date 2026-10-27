import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx

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


def check_pages(
    client: httpx.Client,
    urls: Mapping[str, str],
    retry_delay: float = 30.0,
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
