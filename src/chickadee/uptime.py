import logging
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx

from chickadee.alerts import (
    PendingAlert,
    build_alert,
    decide_alert,
    deliver_alerts,
    down_since,
)
from chickadee.checker import CheckResult, check_pages, should_log, status_of
from chickadee.config import CheckLog
from chickadee.models import Page, Status

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StatusUpdate:
    page_id: str
    result: CheckResult
    previous_status: Status | None
    # Set when a page's first status is recorded without sending an alert.
    alerted_status: Status | None = None


@dataclass(frozen=True)
class UptimeReport:
    checked: int
    logged: int
    alerts: tuple[PendingAlert, ...]


class UptimePages(Protocol):
    """What run_uptime and send_alerts need from wherever pages are kept."""

    def active(self) -> Iterable[Page]: ...

    def save_statuses(
        self, updates: Sequence[StatusUpdate], checked_at: datetime
    ) -> None: ...

    def save_alerted(self, statuses: Mapping[str, Status]) -> None: ...


class UptimeLog(Protocol):
    """Where logged checks are kept."""

    def record(
        self, results: Mapping[str, CheckResult], checked_at: datetime
    ) -> None: ...


def run_uptime(
    pages: UptimePages,
    checks: UptimeLog,
    client: httpx.Client,
    *,
    check_log: CheckLog,
    checked_at: datetime,
    sleep: Callable[[float], None] = time.sleep,
) -> UptimeReport:
    active = list(pages.active())
    results = check_pages(client, {page.id: page.url for page in active}, sleep=sleep)

    updates: list[StatusUpdate] = []
    logged: dict[str, CheckResult] = {}
    alerts: list[PendingAlert] = []

    for page in active:
        result = results[page.id]
        status = status_of(result)
        log.info(
            "%s %s -> %s (%s ms) %s",
            "OK  " if result.ok else "FAIL",
            page.url,
            result.status_code,
            result.response_time_ms,
            result.error or "",
        )

        action = decide_alert(page.alerted_status, status)
        updates.append(
            StatusUpdate(
                page.id,
                result,
                page.status,
                alerted_status=status if action == "record" else None,
            )
        )
        if action == "send":
            payload = build_alert(
                name=page.label,
                url=page.url,
                result=result,
                down_since=down_since(
                    page.status,
                    page.status_since,
                    ok=result.ok,
                    checked_at=checked_at,
                ),
                checked_at=checked_at,
            )
            alerts.append(PendingAlert(page.id, status, payload))

        if should_log(page.status, result, check_log):
            logged[page.id] = result

    checks.record(logged, checked_at)
    pages.save_statuses(updates, checked_at)
    return UptimeReport(checked=len(updates), logged=len(logged), alerts=tuple(alerts))


def send_alerts(
    pages: UptimePages,
    client: httpx.Client,
    webhook_url: str,
    alerts: Sequence[PendingAlert],
) -> int:
    """Send each alert, and remember the ones that arrived.

    Alerts that fail aren't recorded, so the next run sends them again.
    """
    delivered = deliver_alerts(client, webhook_url, alerts)
    pages.save_alerted({alert.page_id: alert.status for alert in delivered})
    return len(delivered)
