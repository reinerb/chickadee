from anthropic import Anthropic
from pydantic import BaseModel, Field

from content_monitor.extractor import PageContent

MODEL = "claude-sonnet-5-5"

SYSTEM_PROMPT = """You review web pages. Judge the page's metadata and structure for both
traditional search engines and AI search tools that summarize and cite pages.
Be specific and practical: refer to the actual text that should change.
You are only given metadata and headings, not the body text, so don't comment on body content."""


class SeoReview(BaseModel):
    score: int = Field(
        ge=1, le=10, description="Overall SEO quality from 1 (poor) to 10 (excellent)"
    )
    summary: str = Field(
        description="One or two sentences on the main strengths and weaknesses"
    )
    suggested_title: str = Field(
        description="An improved page title, under 60 characters"
    )
    suggested_description: str = Field(
        description="An improved meta description, under 160 characters"
    )
    issues: list[str] = Field(
        description="Specific, actionable problems, most important first"
    )


def format_page_for_review(url: str, content: PageContent) -> str:
    h1s = "\n".join(f"  - {h}" for h in content.h1s) or None
    h2s = "\n".join(f"  - {h}" for h in content.h2s) or None

    return (
        f"URL: {url}\n"
        f"Title: {content.title or '(missing)'}\n"
        f"Meta description: {content.meta_description or '(missing)'}\n"
        f"Word count: {content.word_count}\n"
        f"H1 headings:\n{h1s}\n"
        f"H2 headings:\n{h2s}"
    )


def review_page(client: Anthropic, url: str, content: PageContent) -> SeoReview | None:
    response = client.messages.parse(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"<page>\n{format_page_for_review(url, content)}\n</page>",
            }
        ],
        output_format=SeoReview,
    )

    if response.stop_reason != "end_turn":
        print(f"  review incomplete: {response.stop_reason}")
        return None

    return response.parsed_output
