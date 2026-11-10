import argparse
from datetime import UTC, datetime

from chickadee.alerts import build_test_alert
from chickadee.app import App
from chickadee.config import required
from chickadee.errors import ChickadeeError
from chickadee.webhooks import post_json

HELP = "Send a sample alert to the alert webhook."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--recovered",
        action="store_true",
        help="send a 'back up' alert instead of a 'down' alert",
    )


def run(args: argparse.Namespace, app: App) -> None:
    webhook_url = required(app.settings.alert_webhook_url, "ALERT_WEBHOOK_URL")

    sample = build_test_alert(recovered=args.recovered, now=datetime.now(UTC))
    error = post_json(app.http, webhook_url, sample)
    if error:
        raise ChickadeeError(f"Test alert failed: {error}")
    print(f"Sent a test '{sample['event']}' alert.")
