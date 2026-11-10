from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from chickadee.models import Check, Status


@dataclass(frozen=True)
class Event:
    page_id: str
    at: datetime
    status: Status
    status_code: int | None
    error: str | None


def latest_status(
    checks_newest_first: Iterable[Check], page_ids: Collection[str]
) -> dict[str, Status]:
    statuses: dict[str, Status] = {}
    if not page_ids:
        return statuses
    for check in checks_newest_first:
        if check.page_id not in page_ids or check.page_id in statuses:
            continue
        statuses[check.page_id] = check.status
        if len(statuses) == len(page_ids):
            break
    return statuses


def find_events(
    checks: Iterable[Check], initial: Mapping[str, Status] | None = None
) -> list[Event]:
    last_status: dict[str, Status] = dict(initial or {})
    events: list[Event] = []

    for check in sorted(checks, key=lambda check: check.checked_at):
        previous = last_status.get(check.page_id)
        last_status[check.page_id] = check.status

        went_down = check.status == "Down" and previous != "Down"
        came_back = check.status == "Up" and previous == "Down"

        if went_down or came_back:
            events.append(
                Event(
                    page_id=check.page_id,
                    at=check.checked_at,
                    status=check.status,
                    status_code=check.status_code,
                    error=check.error,
                )
            )

    return events


def describe_duration(start: datetime, end: datetime) -> str:
    minutes = int((end - start).total_seconds() // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
