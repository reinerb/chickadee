from typing import Any


def format_checks(checks: list[dict[str, Any]], page_names: dict[str, str]) -> str:
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
