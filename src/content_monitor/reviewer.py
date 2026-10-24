from pydantic import BaseModel, Field

from content_monitor.extractor import PageContent


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
