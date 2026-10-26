from dataclasses import dataclass
from typing import Literal

import httpx

LinkStatus = Literal["ok", "broken", "unverified"]

BROKEN_CODES = {404, 410}
MAX_LINKS_PER_PAGE = 100
PER_HOST_INTERVAL = 1.0


@dataclass(frozen=True)
class LinkResult:
    url: str
    status: LinkStatus
    detail: str


def classify(status_code: int) -> LinkStatus:
    if status_code < 400:
        return "ok"

    if status_code in BROKEN_CODES:
        return "broken"

    return "unverified"


def check_link(client: httpx.Client, url: str) -> LinkResult:
    try:
        with client.stream("GET", url) as response:
            code = response.status_code
    except (httpx.ConnectError, httpx.InvalidURL, httpx.UnsupportedProtocol) as exc:
        return LinkResult(url, "broken", type(exc).__name__)
    except httpx.HTTPError as exc:
        return LinkResult(url, "unverified", type(exc).__name__)

    return LinkResult(url, classify(code), str(code))


def wait_needed(last_request: float | None, now: float, interval: float) -> float:
    if last_request is None:
        return 0.0

    return max(0.0, interval - (now - last_request))
