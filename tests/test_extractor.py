from content_monitor.extractor import (
    HASH_LENGTH,
    content_hash,
    extract_content,
    extract_links,
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


def page(title: str, body: str, nav: str = "Home") -> str:
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body><nav>{nav}</nav><main>{body}</main></body></html>"
    )


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
