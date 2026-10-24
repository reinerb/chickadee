from datetime import datetime
from typing import Any

from content_monitor.checker import CheckResult


def to_check_fields(
    page_id: str, result: CheckResult, checked_at: datetime
) -> dict[str, Any]:
    fields = {
        "Page": [page_id],
        "Checked at": checked_at.isoformat(),
        "Status code": result.status_code,
        "Response time (ms)": result.response_time_ms,
        "Ok": result.ok,
        "Error": result.error,
    }

    # drop any None values
    return {name: value for name, value in fields.items() if value is not None}
