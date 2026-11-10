from collections.abc import Sequence

from chickadee.errors import ConfigError

MAX_CONTEXT_CHARS = 2000


def parse_site_context(contexts: Sequence[str | None]) -> str | None:
    """The site context from the Site table's rows, or None if there isn't one."""
    texts = [text for context in contexts if (text := (context or "").strip())]
    if not texts:
        return None
    if len(texts) > 1:
        raise ConfigError(
            f"The Site table has {len(texts)} rows with Context filled in. "
            "Keep it to one."
        )
    context = texts[0]
    if len(context) > MAX_CONTEXT_CHARS:
        raise ConfigError(
            f"The site context is {len(context):,} characters. "
            f"Keep it under {MAX_CONTEXT_CHARS:,}: it's sent with every review."
        )
    return context


def with_context(role: str, rules: str, context: str | None) -> str:
    if not context:
        return f"{role}\n{rules}"
    return (
        f"{role}\n\n"
        "About this site, from the people who run it:\n"
        f"<site_context>\n{context}\n</site_context>\n\n"
        f"{rules}"
    )
