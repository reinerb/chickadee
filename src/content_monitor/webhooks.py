from collections.abc import Mapping
from typing import Any

import httpx


def post_json(client: httpx.Client, url: str, payload: Mapping[str, Any]) -> str | None:
    try:
        response = client.post(url, json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return f"HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        return type(exc).__name__
    return None
