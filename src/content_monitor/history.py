from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from pyairtable.api.types import RecordDict


@dataclass(frozen=True)
class Event:
    page_id: str
    at: datetime
    status: str
    status_code: int | None
    error: str | None


def find_events(checks: Sequence[RecordDict]) -> list[Event]:
    usable = [
        c for c in checks if c["fields"].get("Checked at") and c["fields"].get("Page")
    ]
    usable.sort(key=lambda c: datetime.fromisoformat(c["fields"]["Checked at"]))

    last_status: dict[str, str] = {}
    events: list[Event] = []

    for check in usable:
        fields = check["fields"]
        page_id = fields["Page"][0]
        status = "Up" if fields.get("Ok") else "Down"
        previous = last_status.get(page_id)
        last_status[page_id] = status

        went_down = status == "Down" and previous != "Down"
        came_back = status == "Up" and previous == "Down"

        if went_down or came_back:
            events.append(
                Event(
                    page_id=page_id,
                    at=datetime.fromisoformat(fields["Checked at"]),
                    status=status,
                    status_code=fields.get("Status code"),
                    error=fields.get("Error"),
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
