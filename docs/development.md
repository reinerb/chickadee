# Development

## Tools

```bash
uv run ruff check          # lint
uv run ruff format         # format
uv run pyright             # type check
uv run pytest              # test
```

All four run in CI on every push and pull request (see [Automation](automation.md#ci)), with the exact versions pinned in `uv.lock`, so they behave the same locally as in CI.

To add a dependency, use `uv add` (or `uv add --dev` for tools) and commit the updated `uv.lock` alongside `pyproject.toml`. CI installs with `--locked` and fails if the two don't match.

## Tests

The tests cover the logic that decides things, and none of them touch the network, Airtable or Claude. They run in about a second, cost nothing, and run in CI without any credentials.

That's possible because the code is split the same way throughout: small functions make the decisions, and a thin `run` function in each command fetches data, calls them, and saves the results. The decisions are what get tested:

- **Uptime and alerts:** reading settings, deciding what gets logged and when to alert, building alert payloads, turning a log into outage and recovery events.
- **Content:** pulling text, links and dates out of HTML, fingerprinting it, deciding what needs a review.
- **Reviews:** building prompts and schemas, cutting long pages down, reading and writing batch custom IDs, validating Claude's answers, matching topics.
- **Links:** finding links in a page, classifying results, pacing requests to each site.
- **Flags and the digest:** deciding which flags apply, building the digest, turning it into safe email HTML.
- **Plumbing:** reading sitemaps, deciding what to import, building Airtable formulas and fields, wiring up the command line.

Network code is tested with httpx's `MockTransport`, which answers each request with whatever a test specifies: a 404, a redirect, a timeout. The link checker and the webhook sender are tested that way, so even the network code runs without a network.

A few habits the tests follow:

- **Test data looks like real data.** Fake Airtable records leave out unchecked checkboxes and empty fields, the way Airtable does.
- **Absence checks are paired with presence checks.** A test that only checks a key is missing would pass if the key were misspelled, so the same key is also checked where it should exist.
- **Each test fails for one reason.** A test for a bad score uses an otherwise valid review, so it can't pass because of some other problem.

## Project layout

```
src/chickadee/
  cli.py         the chickadee command and its subcommands
  uptime.py      chickadee uptime: check pages and record their status
  importer.py    chickadee import: add pages from a sitemap
  audit.py       chickadee audit: detect changes and submit reviews
  collect.py     chickadee collect: save finished reviews
  links.py       chickadee links: check the links in each page
  flags.py       chickadee flags: decide which pages need attention
  digest.py      chickadee digest: the weekly digest and its email
  prune.py       chickadee prune: delete old checks
  alerts.py      alert rules and payloads, plus chickadee test-alert
  webhooks.py    posts JSON to a webhook without exposing its URL in errors
  config.py      reads credentials and settings from the environment or .env
  checker.py     the shared HTTP client and single-page check
  extractor.py   pulls the title, description, dates, headings, text and links from HTML, and fingerprints it
  reviewer.py    the review schema, prompt, topics, batch requests and validation
  store.py       turns results into Airtable fields, and decides what gets logged and what needs review
  history.py     turns logged checks into outage and recovery events
  formulas.py    Airtable formulas for filtering checks by date
  sitemap.py     reads sitemaps and sitemap indexes
  results.py     the link check result type, shared by links.py and store.py
tests/
make/
  alerts.blueprint.json   sample Make scenario for routing alerts
  digest.blueprint.json   sample Make scenario for emailing the digest
.github/
  workflows/     CI plus the seven scheduled jobs
  dependabot.yml
```

`__init__.py` is deliberately empty. Python runs a package's `__init__.py` whenever anything in the package is imported, so code there gets loaded constantly and can create import loops.

`results.py` exists for the same reason: `links.py` and `store.py` both need the link result type, and putting it in either one made them import each other. A type both modules share belongs in a third module that imports neither.

## Adding a command

Every command module has the same three things:

```python
HELP = "One line describing the command."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--example", action="store_true", help="...")


def run(args: argparse.Namespace) -> None:
    ...
```

To add one, write the module and add it to `COMMANDS` in `cli.py`. A `Protocol` in `cli.py` describes this shape, so Pyright checks every command module has all three. `tests/test_cli.py` checks that every command's `--help` works.

Commands that print a report send messages about the run to stderr and the report itself to stdout, so the output can be redirected or written into a GitHub run summary without picking up noise.
