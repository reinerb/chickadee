from datetime import UTC, datetime

from bs4 import BeautifulSoup

from chickadee.extractor import (
    HASH_LENGTH,
    content_hash,
    extract_content,
    extract_links,
    page_modified_at,
    parse_page_date,
)

SAMPLE = """
<html>
  <head>
    <title> Fish Welfare Study </title>
    <meta name="description" content="A summary of new research on fish welfare.">
    <script>var tracking = "these words should not count";</script>
  </head>
  <body>
    <nav>Home About Contact</nav>
    <main>
      <h1>Fish Welfare Study</h1>
      <p>Five words in this paragraph.</p>
      <h2>Key findings</h2>
    </main>
  </body>
</html>
"""
LINK_PAGE = """
<html><body>
  <nav><a href="/about/">About</a></nav>
  <main>
    <a href="/research/fish/">Fish</a>
    <a href="https://doi.org/10.1000/xyz#section-2">Study</a>
    <a href="https://doi.org/10.1000/xyz">Same study</a>
    <a href="#top">Back to top</a>
    <a href="mailto:hello@example.org">Email</a>
    <a>No link</a>
  </main>
</body></html>
"""
MONDAY = """
<html><head><title>Report</title></head><body><main>
  <h1>Report</h1>
  <p>Findings.</p>
  <p>Updated <time>Monday</time></p>
  <div class="related-posts"><a href="/post-a/">Post A</a></div>
</main></body></html>
"""
TUESDAY = MONDAY.replace("Monday", "Tuesday").replace("Post A", "Post B")


def page(title: str, body: str, nav: str = "Home") -> str:
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body><nav>{nav}</nav><main>{body}</main></body></html>"
    )


def head(tags: str) -> BeautifulSoup:
    return BeautifulSoup(
        f"<html><head>{tags}</head><body></body></html>", "html.parser"
    )


def fingerprint(html: str, ignore: str | None = None) -> str:
    return content_hash(extract_content(html, ignore=ignore))


def test_extracts_metadata_and_headings():
    content = extract_content(SAMPLE)

    assert content.title == "Fish Welfare Study"
    assert content.meta_description == "A summary of new research on fish welfare."
    assert content.h1s == ("Fish Welfare Study",)
    assert content.h2s == ("Key findings",)


def test_word_count_ignores_scripts_and_navigation():
    content = extract_content(SAMPLE)

    assert content.word_count == 10


def test_missing_metadata_comes_back_as_none():
    content = extract_content("<html><body><p>Hello</p></body></html>")

    assert content.title is None
    assert content.meta_description is None
    assert content.h1s == ()


def test_hash_ignores_whitespace_and_navigation():
    a = extract_content(page("Study", "<p>Same   words\n  here</p>"))
    b = extract_content(
        page("Study", "<p>Same words here</p>", nav="Home About Donate")
    )

    assert content_hash(a) == content_hash(b)


def test_hash_changes_when_the_text_or_title_changes():
    base = extract_content(page("Study", "<p>Words</p>"))
    edited = extract_content(page("Study", "<p>Different words</p>"))
    retitled = extract_content(page("New study", "<p>Words</p>"))

    assert content_hash(base) != content_hash(edited)
    assert content_hash(base) != content_hash(retitled)
    assert len(content_hash(base)) == HASH_LENGTH


def test_links_are_resolved_deduplicated_and_filtered():
    links = extract_links(LINK_PAGE, "https://example.org/library/page/")

    assert links == [
        "https://example.org/research/fish/",
        "https://doi.org/10.1000/xyz",
    ]


def test_modified_date_is_preferred_and_converted_to_utc():
    soup = head(
        '<meta property="article:published_time" content="2024-01-01T00:00:00+00:00">'
        '<meta property="article:modified_time" content="2025-06-01T09:30:00-04:00">'
    )

    assert page_modified_at(soup) == datetime(2025, 6, 1, 13, 30, tzinfo=UTC)


def test_missing_or_unreadable_dates_are_ignored():
    assert page_modified_at(head("")) is None
    assert parse_page_date("not a date") is None
    assert parse_page_date("2024-03-05") == datetime(2024, 3, 5, tzinfo=UTC)


def test_ignored_sections_dont_count_as_changes():
    assert fingerprint(MONDAY) != fingerprint(TUESDAY)
    ignore = ".related-posts, time"
    assert fingerprint(MONDAY, ignore) == fingerprint(TUESDAY, ignore)


def test_ignored_sections_links_arent_checked():
    page = "https://example.org/report/"
    assert extract_links(MONDAY, page) == ["https://example.org/post-a/"]
    assert extract_links(MONDAY, page, ignore=".related-posts") == []
