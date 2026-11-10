import argparse
from datetime import UTC, datetime

from chickadee.app import App
from chickadee.errors import ChickadeeError
from chickadee.uptime import run_uptime, send_alerts

HELP = "Check that every active page is up, and send alerts for changes."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace, app: App) -> None:
    check_log = app.settings.check_log
    report = run_uptime(
        app.pages,
        app.checks,
        app.http,
        check_log=check_log,
        checked_at=datetime.now(UTC),
    )
    print(
        f"Updated {report.checked} page(s); logged {report.logged} check(s) "
        f"in '{check_log}' mode."
    )

    if not report.alerts:
        return
    webhook_url = app.settings.alert_webhook_url
    if not webhook_url:
        print(f"{len(report.alerts)} alert(s) due, but ALERT_WEBHOOK_URL isn't set.")
        return

    sent = send_alerts(app.pages, app.http, webhook_url, report.alerts)
    print(f"Sent {sent} of {len(report.alerts)} alert(s).")
    if sent < len(report.alerts):
        raise ChickadeeError(
            "Some alerts weren't delivered. The next run retries them."
        )
