from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class PageContent:
    title: str | None
    meta_description: str | None
    h1s: tuple[str, ...]
    h2s: tuple[str, ...]
    word_count: int


def _meta_description(soup: BeautifulSoup) -> str | None:
    tag = soup.select_one('meta[name="description"]')

    if tag is None:
        return None

    content = tag.get("content")

    if isinstance(content, str) and content.strip():
        return content.strip()

    return None


def extract_content(html: str) -> PageContent:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else ""
    h1s = tuple(h.get_text(" ", strip=True) for h in soup.select("h1"))
    h2s = tuple(h.get_text(" ", strip=True) for h in soup.select("h2"))
    description = _meta_description(soup)

    for tag in soup.select("script, style, noscript, nav, header, footer"):
        tag.decompose()

    body = soup.select_one("main") or soup.body or soup
    word_count = len(body.get_text(" ", strip=True).split())

    return PageContent(
        title=title or None,
        meta_description=description,
        h1s=h1s,
        h2s=h2s,
        word_count=word_count,
    )
