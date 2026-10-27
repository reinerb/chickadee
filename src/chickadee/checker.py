import time
from dataclasses import dataclass

import httpx


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


def make_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": "Chickadee (+https://github.com/reinerb/chickadee)"},
    )
