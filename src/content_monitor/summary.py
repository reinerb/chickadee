from collections.abc import Sequence

from anthropic import Anthropic
from pyairtable import Api
from pyairtable.api.types import RecordDict

from content_monitor.config import load_anthropic_key, load_settings

MODEL = "claude-haiku-5-5"

SYSTEM_PROMPT = """You review website uptime data for a website's content team.
Summarize the checks you're given for a non-technical reader:
- Start with one sentence on overall health.
- Then list any pages that are failing or unusually slow, with what the data shows.
- If everything is fine, say so briefly. Don't pad.
Use only the data provided. Don't guess at causes the data doesn't support."""


def format_checks(checks: Sequence[RecordDict], page_names: dict[str, str]) -> str:
    lines = []

    for check in checks:
        fields = check["fields"]
        page_ids = fields.get("Page", [])
        name = (
            page_names.get(page_ids[0], "(unknown page)") if page_ids else "(no page)"
        )
        lines.append(
            f"{fields.get('Checked at')} | {name} | "
            f"ok={fields.get('Ok', False)} | "
            f"status={fields.get('Status code', '-')} | "
            f"{fields.get('Response time (ms)', '-')} ms | "
            f"{fields.get('Error', '')}"
        )

    return "\n".join(lines)


def main() -> None:
    settings = load_settings()

    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")
    checks = api.table(settings.airtable_base_id, "Checks")

    page_names = {
        record["id"]: record["fields"].get("Name", record["fields"]["URL"])
        for record in pages.all()
    }
    recent = checks.all(sort=["-Checked at"], max_records=50)

    client = Anthropic(api_key=load_anthropic_key())
    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"<checks>\n{format_checks(recent, page_names)}\n</checks>",
            }
        ],
    )

    for block in message.content:
        if block.type == "text":
            print(block.text)

    print(
        f"\n[{MODEL}]: {message.usage.input_tokens} in / "
        f"{message.usage.output_tokens} out tokens"
    )
