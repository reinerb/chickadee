from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from anthropic import Anthropic
from pyairtable import Api
from pyairtable.api.types import RecordDict

from content_monitor.config import load_anthropic_key, load_settings
from content_monitor.formulas import checked_after
from content_monitor.history import Event, describe_duration, find_events

MODEL = "claude-haiku-5-5"
SUMMARY_DAYS = 7

SYSTEM_PROMPT = """You review website uptime for their content team. You'll get each monitored
page's current status and a list of outages and recoveries from the past week.
Write for a non-technical reader:
- Start with one sentence on overall health right now.
- Then mention any pages that are down now, and any outages during the week, using the times and durations given.
- If everything is up and nothing happened this week, say so in one sentence. Don't pad.
Use only the data provided. Durations are already calculated, so use them exactly as given."""


def page_name(page: RecordDict) -> str:
    fields = page["fields"]
    return fields.get("Name") or fields.get("URL") or "(unnamed page)"


def format_status(pages: Sequence[RecordDict], now: datetime) -> str:
    lines = []
    for page in pages:
        fields = page["fields"]
        status = fields.get("Status", "not checked yet")
        since = fields.get("Status since")
        duration = (
            f" for {describe_duration(datetime.fromisoformat(since), now)}"
            if since
            else ""
        )
        lines.append(
            f"{page_name(page)} | {status}{duration} | "
            f"status code {fields.get('Last status code', '-')} | "
            f"{fields.get('Last response time (ms)', '-')} ms"
        )
    return "\n".join(lines) or "(no active pages)"


def format_events(events: Sequence[Event], names: dict[str, str]) -> str:
    lines = []
    for event in events:
        if event.status == "Up":
            what = "came back up"
        else:
            what = f"went down ({event.status_code or event.error or 'no response'})"
        name = names.get(event.page_id, "(unknown page)")
        lines.append(f"{event.at:%Y-%m-%d %H:%M} UTC | {name} | {what}")
    return "\n".join(lines) or "(none)"


def main() -> None:
    settings = load_settings()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    checks = api.table(settings.airtable_base_id, "Checks")
    now = datetime.now(UTC)

    all_pages = pages.all(
        fields=[
            "Name",
            "URL",
            "Active",
            "Status",
            "Status since",
            "Last status code",
            "Last response time (ms)",
        ]
    )
    active = [page for page in all_pages if page["fields"].get("Active")]
    names = {page["id"]: page_name(page) for page in all_pages}

    recent = checks.all(
        formula=checked_after(now - timedelta(days=SUMMARY_DAYS)),
        fields=["Page", "Checked at", "Ok", "Status code", "Error"],
    )
    events = find_events(recent)

    content = (
        f"<current_status>\n{format_status(active, now)}\n</current_status>\n"
        f"<events_past_week>\n{format_events(events, names)}\n</events_past_week>"
    )

    client = Anthropic(api_key=load_anthropic_key())
    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    for block in message.content:
        if block.type == "text":
            print(block.text)

    print(
        f"\n[{MODEL}: {message.usage.input_tokens} in / "
        f"{message.usage.output_tokens} out tokens]"
    )
