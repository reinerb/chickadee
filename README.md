# Content Monitor

![CI](https://github.com/reinerb/content-monitor/actions/workflows/ci.yml/badge.svg)

Content Monitor keeps an eye on a list of web pages. Every hour it checks that each page is up and logs the result in Airtable. Once a week it pulls each page's title, description and headings, asks Claude to review them for search, and writes the score and suggestions back to Airtable.

I built this to get hands-on understanding of the Airtable and Claude APIs, and I wanted it to solve a problem content teams really have: finding out which pages are broken, slow, or hard to find in search without someone checking them by hand.

## Commands

| Command | What it does |
|---|---|
| `content-monitor` | Checks every active page and records the status code, response time and any error |
| `content-summary` | Reads the most recent checks and asks Claude for a short, plain-English health report |
| `content-audit` | Pulls each page's title, meta description, headings and word count, saves them, and sends a batch of SEO reviews to Claude |
| `content-collect` | Picks up finished review batches and saves Claude's score, suggested title and description, and list of issues |

Uptime data flows from the Pages table into Checks, and `content-summary` reads it from there. SEO data goes from Pages to Claude's Message Batches API and comes back onto Pages.

## How it's built

### Data model

Uptime checks get their own table because one page builds up many checks over time, and that history is worth keeping. SEO results are different. Only the latest review matters, so each audit overwrites the fields on the page instead of adding rows.

Creating and updating records needs slightly different handling. When a new check is created, empty values are simply left out. When a page is updated, a missing value is sent as empty on purpose, so if a page loses its title, the old title gets cleared instead of hanging around.

### Working with Claude

The SEO review is defined once as a Pydantic model. Its schema is sent with every request, so Claude's answer always comes back in the same shape and maps straight onto Airtable columns. The API can't enforce number ranges, so the 1 to 10 score is checked with Pydantic when results come in.

Reviews go through the Message Batches API instead of one call per page. Nobody needs them instantly, and batch requests cost half as much. Each request uses the page's Airtable record ID as its custom ID, which is how a result finds its way back to the right row. Batches waiting to be collected are tracked in Airtable rather than a local file, so collection works the same from a scheduled job as from my laptop.

I chose models by trying them. The uptime summary uses Claude Haiku because the task is simple and Haiku is the cheapest option. The SEO review uses Claude Sonnet: I ran both models on the same pages, and Sonnet's critiques were noticeably more useful.

### Fetching pages

Requests identify the tool with a User-Agent and give up after 10 seconds. Audits also wait a second between pages so they don't hammer anyone's site.

## Setup

You'll need [uv](https://docs.astral.sh/uv/), which takes care of installing the right Python version and the dependencies.

1. Clone the repo and install:
   ```bash
   uv sync
   ```
2. Create an Airtable base with the three tables listed under [Airtable schema](#airtable-schema).
3. Create an Airtable personal access token with the scopes `data.records:read`, `data.records:write` and `schema.bases:read`, limited to that base.
4. Create a Claude API key in the [Claude Console](https://platform.claude.com/).
5. Add a `.env` file to the project root. It's already in `.gitignore`.
   ```
   AIRTABLE_TOKEN=pat...
   AIRTABLE_BASE_ID=app...
   ANTHROPIC_API_KEY=sk-ant-...
   ```
   The base ID is just the `app...` part of the base's URL.

Only the commands that talk to Claude need the Claude key. `content-monitor` runs without it.

## Running it locally

```bash
uv run content-monitor    # check every active page
uv run content-summary    # get Claude's take on recent checks

uv run content-audit      # gather page content and send it for review
uv run content-collect    # save any reviews that are ready
```

Most batches finish within an hour, though they can take up to 24. You can run `content-collect` as often as you like. It tells you which batches are still processing and skips any it has already saved.

## Automation

Three GitHub Actions workflows run the tool on a schedule. All times are UTC.

| Workflow | When it runs | Command |
|---|---|---|
| `monitor.yml` | Every hour at :17 | `content-monitor` |
| `audit.yml` | Mondays at 10:23 | `content-audit` |
| `collect.yml` | Every 6 hours | `content-collect` |

Each one can also be started by hand from the Actions tab.

The credentials live in a GitHub environment called `production`, which only the `main` branch can use, so they're only ever available to code that's already been merged. Inside each workflow, credentials are passed only to the step that needs them, and the uptime workflow never gets the Claude key at all. Each workflow has its own timeout and won't start a new run while the previous one is still going.

A separate `ci.yml` workflow runs linting, formatting checks, type checking and tests on every push and pull request. It has no access to any credentials. Dependabot opens pull requests when the GitHub Actions or Python dependencies have updates, and CI checks each one before it's merged.

An uptime summary is presented directly within the weekly audit run.

## Development

```bash
uv run ruff check          # lint
uv run ruff format         # format
uv run pyright             # type check
uv run pytest              # test
```

The tests cover the pure functions: turning results into Airtable fields, pulling content out of HTML, and validating Claude's reviews. None of them touch the network, Airtable or Claude, so they run in a second and don't cost anything. That's also why CI can run them without credentials.

## Airtable schema

Field names are case-sensitive and need to match exactly.

**Pages**

| Field | Type |
|---|---|
| URL | URL (primary) |
| Name | Single line text |
| Active | Checkbox |
| Current title | Single line text |
| Current description | Long text |
| Word count | Number |
| SEO score | Number |
| SEO summary | Long text |
| Suggested title | Single line text |
| Suggested description | Long text |
| SEO issues | Long text |
| Last audited | Date with time |
| Last checked | Rollup of Checks → Checked at, using `MAX(values)` (optional) |

**Checks**

| Field | Type |
|---|---|
| Check ID | Autonumber (primary) |
| Page | Link to Pages |
| Checked at | Date with time |
| Status code | Number |
| Response time (ms) | Number |
| Ok | Checkbox |
| Error | Long text |

**Audit batches**

| Field | Type |
|---|---|
| Batch ID | Single line text (primary) |
| Submitted at | Date with time |
| Pages | Number |
| Collected | Checkbox |

## Project layout

```
src/content_monitor/
  __init__.py    content-monitor: uptime checks
  summary.py     content-summary: Claude's health report
  audit.py       content-audit: gather page content and submit reviews
  collect.py     content-collect: save finished reviews
  config.py      reads settings and credentials from the environment or .env
  checker.py     the shared HTTP client and single-page check
  extractor.py   pulls the title, description, headings and word count from HTML
  reviewer.py    the review schema, prompt, batch requests and validation
  store.py       turns results into Airtable fields
tests/
.github/
  workflows/     CI plus the three scheduled jobs
  dependabot.yml
```

## Limitations and next steps

- Claude only sees metadata and headings, not the body text, so reviews cover how findable and well-structured a page is rather than how well it's written.
- If a page is deleted from Airtable between `content-audit` and `content-collect`, saving that batch fails.
- GitHub doesn't guarantee exact start times for scheduled runs, and they can be delayed when it's busy. On public repos, scheduled workflows also pause after 60 days without any repository activity.
- Every scheduled run counts as a deployment to the `production` environment, which clutters the repo's deployment history.
- Links within pages aren't checked yet.
- `content-summary` only looks at the 50 most recent checks.
