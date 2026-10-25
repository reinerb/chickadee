from datetime import UTC, datetime


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def checked_before(cutoff: datetime) -> str:
    return f"IS_BEFORE({{Checked at}}, DATETIME_PARSE('{_stamp(cutoff)}'))"


def checked_after(cutoff: datetime) -> str:
    return f"IS_AFTER({{Checked at}}, DATETIME_PARSE('{_stamp(cutoff)}'))"
