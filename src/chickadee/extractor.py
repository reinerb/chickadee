import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

HASH_LENGTH = 16
STRIPPED = "script, style, noscript, nav, header, footer"
MODIFIED_META = (
    'meta[property="article:modified_time"]',
    'meta[property="og:updated_time"]',
    'meta[property="article:published_time"]',
)


@dataclass(frozen=True)
class PageContent:
    title: str | None
    meta_description: str | None
    h1s: tuple[str, ...]
    h2s: tuple[str, ...]
    word_count: int
    text: str
    modified_at: datetime | None


def _main_element(soup: BeautifulSoup) -> Tag:
    for tag in soup.select(STRIPPED):
        tag.decompose()

    return soup.select_one("main") or soup.body or soup


def _meta_content(soup: BeautifulSoup, selector: str) -> str | None:
    tag = soup.select_one(selector)
    if tag is None:
        return None

    content = tag.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()

    return None


def content_hash(content: PageContent) -> str:
    parts = [content.title or "", content.meta_description or "", content.text]
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest[:HASH_LENGTH]


def parse_page_date(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def page_modified_at(soup: BeautifulSoup) -> datetime | None:
    for selector in MODIFIED_META:
        parsed = parse_page_date(_meta_content(soup, selector))
        if parsed is not None:
            return parsed

    return None


def strip_ignored(soup: BeautifulSoup, ignore: str | None) -> None:
    if ignore:
        for element in soup.select(ignore):
            element.decompose()


def extract_content(html: str, ignore: str | None = None) -> PageContent:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else ""
    modified_at = page_modified_at(soup)
    description = _meta_content(soup, 'meta[name="description"]')

    strip_ignored(soup, ignore)

    h1s = tuple(h.get_text(" ", strip=True) for h in soup.select("h1"))
    h2s = tuple(h.get_text(" ", strip=True) for h in soup.select("h2"))
    body = _main_element(soup)
    text = " ".join(body.get_text(" ", strip=True).split())

    return PageContent(
        title=title or None,
        meta_description=description,
        h1s=h1s,
        h2s=h2s,
        word_count=len(text.split()),
        text=text,
        modified_at=modified_at,
    )


def extract_links(html: str, page_url: str, ignore: str | None = None) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    page, _ = urldefrag(page_url)

    strip_ignored(soup, ignore)

    links: list[str] = []

    for anchor in _main_element(soup).select("a[href]"):
        href = anchor.get("href")

        if not isinstance(href, str):
            continue

        url, _ = urldefrag(urljoin(page_url, href.strip()))

        if urlparse(url).scheme in ("http", "https") and url != page:
            links.append(url)

    return list(dict.fromkeys(links))
