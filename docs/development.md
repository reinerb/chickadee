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

That's possible because the code is split the same way throughout: small functions make the decisions, and a thin `run` function in each module under `commands/` fetches data, calls them, and saves the results. The decisions are what get tested:

- **Uptime and alerts:** reading settings, retrying failed checks, deciding what gets logged and when to alert, working out when an outage started, building alert payloads and tracking which were delivered, turning a log into outage and recovery events.
- **Content:** pulling text, links and dates out of HTML, ignoring configured sections, fingerprinting it, deciding what needs a review and why.
- **Reviews:** building prompts and schemas, cutting long pages down, reading and writing batch custom IDs, validating Claude's answers, matching topics, skipping pages that were deleted, fingerprinting the review setup, reading the site context and placing it in prompts.
- **Links:** finding links in a page, classifying results, spotting redirects to the homepage, pacing requests to each site.
- **Flags and the digest:** deciding which flags apply and which date a page was last updated, working out each page's status before the week, building the digest, turning it into safe email HTML.
- **Plumbing:** reading sitemaps (including compressed and oversized ones), matching URLs that are written differently, deciding what to import, building Airtable formulas and fields, wiring up the command line.

Network code is tested with httpx's `MockTransport`, which answers each request with whatever a test specifies: a 404, a redirect, a timeout. The uptime retry, the link checker, the sitemap download and the webhook senders are tested that way, so even the network code runs without a network.

Code that waits takes the waiting function as a parameter. The uptime retry normally calls `time.sleep`, but its test passes a function that just records how long it was asked to wait, so the test can confirm there was exactly one 30-second pause without spending 30 seconds.

A few habits the tests follow:

- **Test data looks like real data.** Fake Airtable records leave out unchecked checkboxes and empty fields, the way Airtable does.
- **Absence checks are paired with presence checks.** A test that only checks a key is missing would pass if the key were misspelled, so the same key is also checked where it should exist.
- **Each test fails for one reason.** A test for a bad score uses an otherwise valid review, so it can't pass because of some other problem.

## Project layout

```
src/chickadee/
  cli.py         the chickadee command: parses arguments and runs one subcommand
  __main__.py    lets python -m chickadee run the same command
  errors.py      ChickadeeError, the failures cli.py reports as a message instead of a traceback
  config.py      reads credentials and settings from the environment or .env
  commands/      one module per subcommand: its help, arguments, and the run function that wires it up
    import, uptime, audit, collect, links, flags, digest, prune, test-alert
    _args.py     argument types shared by more than one command
  alerts.py      alert rules, payloads and delivery
  webhooks.py    posts JSON to a webhook without exposing its URL in errors
  checker.py     the shared HTTP client, single-page check, the retry for failed checks, and what gets logged
  extractor.py   pulls the title, description, dates, headings, text and links from HTML, and fingerprints it
  importer.py    matches URLs that are written differently and decides which sitemap pages to add
  links.py       checks links and paces requests to each site
  reviewer.py    the review schema, prompt, topics, batch requests and validation, and what needs review
  flags.py       decides which pages need attention
  digest.py      builds the weekly digest and its email
  airtable.py    turns results into Airtable fields and builds formulas for filtering checks by date
  history.py     turns logged checks into outage and recovery events
  sitemap.py     reads sitemaps and sitemap indexes, including compressed ones and lastmod dates
  site_context.py  reads and checks the site context, and places it in prompts
  results.py     the link check result type, shared by links.py and airtable.py
```

`__init__.py` is deliberately empty. Python runs a package's `__init__.py` whenever anything in the package is imported, so code there gets loaded constantly and can create import loops.

`results.py` exists for the same reason: `links.py` and `airtable.py` both need the link result type, and putting it in either one made them import each other. A type both modules share belongs in a third module that imports neither.

## Adding a command

Every module in `commands/` has the same three things:

```python
HELP = "One line describing the command."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--example", action="store_true", help="...")


def run(args: argparse.Namespace) -> None: ...
```

To add one, write the module in `commands/` and add it to `COMMANDS` in `cli.py`. Keep it thin: decisions go in a module outside `commands/`, where they can be tested without Airtable or the network. A `Protocol` in `cli.py` describes this shape, so Pyright checks every command module has all three. `tests/test_cli.py` checks that every command's `--help` works.

Commands that print a report send messages about the run to stderr and the report itself to stdout, so the output can be redirected or written into a GitHub run summary without picking up noise.
