from content_monitor.extractor import extract_content

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
