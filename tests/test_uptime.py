from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from chickadee.alerts import PendingAlert
from chickadee.checker import CheckResult
from chickadee.models import Page, Status
from chickadee.uptime import StatusUpdate, run_uptime, send_alerts

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
EARLIER = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def page(record_id: str, path: str, **fields: Any) -> Page:
    return Page(
        id=record_id, created_at=EARLIER, url=f"https://example.org{path}", **fields
    )


class FakePages:
    def __init__(self, *pages: Page) -> None:
        self.pages = pages
        self.statuses: list[StatusUpdate] = []
        self.alerted: dict[str, Status] = {}

    def active(self) -> tuple[Page, ...]:
        return self.pages

    def save_statuses(
        self, updates: Sequence[StatusUpdate], checked_at: datetime
    ) -> None:
        self.statuses = list(updates)

    def save_alerted(self, statuses: Mapping[str, Status]) -> None:
        self.alerted = dict(statuses)


class FakeLog:
    def __init__(self) -> None:
        self.logged: dict[str, CheckResult] = {}

    def record(self, results: Mapping[str, CheckResult], checked_at: datetime) -> None:
        self.logged = dict(results)


def site(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503 if request.url.path == "/down" else 200)


def client_for(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def run(pages: FakePages, checks: FakeLog):
    return run_uptime(
        pages,
        checks,
        client_for(site),
        check_log="changes",
        checked_at=NOW,
        sleep=lambda seconds: None,
    )


def test_a_page_going_down_is_logged_and_alerted():
    pages = FakePages(
        page("recDown", "/down", name="Library", status="Up", alerted_status="Up")
    )
    checks = FakeLog()

    report = run(pages, checks)

    assert set(checks.logged) == {"recDown"}
    [update] = pages.statuses
    assert (update.page_id, update.previous_status) == ("recDown", "Up")
    [alert] = report.alerts
    assert alert.status == "Down"
    assert alert.payload["event"] == "down"
    assert alert.payload["page"] == "Library"


def test_an_unchanged_page_is_not_logged_or_alerted():
    pages = FakePages(page("recUp", "/up", status="Up", alerted_status="Up"))
    checks = FakeLog()

    report = run(pages, checks)

    assert checks.logged == {}
    assert report.alerts == ()
    assert report.checked == 1


def test_a_new_page_that_is_up_is_recorded_without_an_alert():
    pages = FakePages(page("recNew", "/up"))

    report = run(pages, FakeLog())

    assert report.alerts == ()
    [update] = pages.statuses
    assert update.alerted_status == "Up"


def test_an_outage_alert_knows_when_it_started():
    pages = FakePages(
        page(
            "recDown",
            "/down",
            status="Down",
            status_since=EARLIER,
            alerted_status="Up",
        )
    )

    [alert] = run(pages, FakeLog()).alerts

    assert alert.payload["duration"] == "3h 0m"


def test_only_delivered_alerts_are_remembered():
    alerts = [
        PendingAlert("recA", "Down", {"page": "A"}),
        PendingAlert("recB", "Up", {"page": "B"}),
    ]

    def webhook(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500 if b'"page":"B"' in request.content else 200)

    pages = FakePages()
    sent = send_alerts(
        pages, client_for(webhook), "https://hooks.example.org/x", alerts
    )

    assert sent == 1
    assert pages.alerted == {"recA": "Down"}
