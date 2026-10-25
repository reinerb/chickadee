from datetime import datetime
from typing import Any

from content_monitor.checker import CheckResult
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
