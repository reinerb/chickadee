from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import httpx

from chickadee.checker import CheckResult, status_of
from chickadee.history import describe_duration
from chickadee.webhooks import post_json

AlertAction = Literal["send", "record", "none"]


@dataclass(frozen=True)
class PendingAlert:
    record_id: str
    status: str
    payload: dict[str, Any]


def decide_alert(alerted: str | None, status: str) -> AlertAction:
    if status == alerted:
        return "none"

    if alerted is None and status == "Up":
        return "record"

    return "send"


def down_since(
    previous_status: str | None,
    status_since: datetime | None,
    *,
    ok: bool,
    checked_at: datetime,
) -> datetime | None:
    if previous_status == "Down":
        return status_since

    if not ok:
        return checked_at

    return None


def build_alert(
    *,
    name: str,
    url: str,
    result: CheckResult,
    down_since: datetime | None,
    checked_at: datetime,
    test: bool = False,
) -> dict[str, Any]:
    status = status_of(result)
    duration = (
        describe_duration(down_since, checked_at)
        if down_since is not None and down_since < checked_at
        else None
    )

    if status == "Down":
        reason = result.status_code or result.error or "no response"
        if duration:
            message = f"{name} has been down for {duration} ({reason}). {url}"
        else:
            message = f"{name} is down ({reason}). {url}"
    elif duration:
        message = f"{name} is back up after {duration} down. {url}"
    else:
        message = f"{name} is back up. {url}"

    return {
        "event": "down" if status == "Down" else "recovered",
        "page": name,
        "url": url,
        "status_code": result.status_code,
        "error": result.error,
        "duration": duration,
        "checked_at": checked_at.isoformat(),
        "message": message,
        "test": test,
    }


def build_test_alert(*, recovered: bool, now: datetime) -> dict[str, Any]:
    if recovered:
        result = CheckResult(
            url="https://example.org/",
            ok=True,
            status_code=200,
            response_time_ms=180,
            error=None,
        )
    else:
        result = CheckResult(
            url="https://example.org/",
            ok=False,
            status_code=503,
            response_time_ms=1200,
            error="Example error",
        )

    return build_alert(
        name="Example page",
        url="https://example.org/",
        result=result,
        down_since=now - timedelta(hours=2, minutes=15),
        checked_at=now,
        test=True,
    )


def deliver_alerts(
    client: httpx.Client, webhook_url: str, pending: Sequence[PendingAlert]
) -> list[PendingAlert]:
    delivered = []

    for alert in pending:
        error = post_json(client, webhook_url, alert.payload)
        if error:
            print(f"  alert failed for {alert.payload['page']}: {error}")
        else:
            delivered.append(alert)

    return delivered
