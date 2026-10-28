from collections.abc import Sequence

from pyairtable import Api
from pyairtable.api.types import RecordDict

MAX_CONTEXT_CHARS = 2000


def parse_site_context(records: Sequence[RecordDict]) -> str | None:
    texts = [
        text
        for record in records
        if (text := (record["fields"].get("Context") or "").strip())
    ]
    if not texts:
        return None
    if len(texts) > 1:
        raise SystemExit(
            f"The Site table has {len(texts)} rows with Context filled in. "
            "Keep it to one."
        )
    context = texts[0]
    if len(context) > MAX_CONTEXT_CHARS:
        raise SystemExit(
            f"The site context is {len(context):,} characters. "
            f"Keep it under {MAX_CONTEXT_CHARS:,}: it's sent with every review."
        )
    return context


def load_site_context(api: Api, base_id: str) -> str | None:
    return parse_site_context(api.table(base_id, "Site").all(fields=["Context"]))


def with_context(role: str, rules: str, context: str | None) -> str:
    if not context:
        return f"{role}\n{rules}"
    return (
        f"{role}\n\n"
        "About this site, from the people who run it:\n"
        f"<site_context>\n{context}\n</site_context>\n\n"
        f"{rules}"
    )
