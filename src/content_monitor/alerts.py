from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from content_monitor.checker import CheckResult, make_client
from content_monitor.config import load_alert_webhook
from content_monitor.history import describe_duration
from content_monitor.store import status_of


def should_alert(previous_status: str | None, status: str) -> bool:
    if status == previous_status:
        return False

    return not (previous_status is None and status == "Up")


def build_alert(
    *,
    name: str,
    url: str,
    result: CheckResult,
    previous_since: datetime | None,
    checked_at: datetime,
    test: bool = False,
) -> dict[str, Any]:
    status = status_of(result)
    duration = describe_duration(previous_since, checked_at) if previous_since else None

    if status == "Down":
        reason = result.status_code or result.error or "no response"
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


def send_alerts(
    client: httpx.Client, webhook_url: str, alerts: Sequence[dict[str, Any]]
) -> int:
    failures = 0

    for alert in alerts:
        try:
            response = client.post(webhook_url, json=alert)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            failures += 1
            print(
                f"  alert failed for {alert['page']}: HTTP {exc.response.status_code}"
            )
        except httpx.RequestError as exc:
            failures += 1
            print(f"  alert failed for {alert['page']}: {type(exc).__name__}")

    return failures


def main() -> None:
    webhook_url = load_alert_webhook()
    if not webhook_url:
        raise SystemExit("Set ALERT_WEBHOOK_URL in .env first.")

    now = datetime.now(UTC)
    sample = build_alert(
        name="Example page",
        url="https://example.org/",
        result=CheckResult(
            url="https://example.org/",
            ok=False,
            status_code=503,
            response_time_ms=1200,
            error="Example error",
        ),
        previous_since=now.replace(hour=0, minute=0),
        checked_at=now,
        test=True,
    )
    with make_client() as client:
        failures = send_alerts(client, webhook_url, [sample])
    print("Sent a test alert." if not failures else "Test alert failed.")
