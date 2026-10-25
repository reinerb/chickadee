# Content Monitor

![CI](https://github.com/reinerb/content-monitor/actions/workflows/ci.yml/badge.svg)

Content Monitor keeps an eye on a list of web pages. Every hour it checks that each page is up, records the result in Airtable, and can send an alert the moment a page goes down or comes back. Once a week it pulls each page's title, description and headings, asks Claude to review them for search, and writes the score and suggestions back to Airtable.

I built this to get hands-on understanding of the Airtable and Claude APIs, and I wanted it to solve a problem content teams really have: finding out which pages are broken, slow, or hard to find in search without someone checking them by hand.

## Commands

| Command | What it does |
|---|---|
| `content-import` | Reads a site's sitemap and adds any pages that aren't being tracked yet |
| `content-monitor` | Checks every active page, updates its current status, logs the check, and sends alerts for status changes |
| `content-summary` | Asks Claude for a short, plain-English report on current status and the past week's outages |
| `content-audit` | Pulls each page's title, meta description, headings and word count, saves them, and sends a batch of SEO reviews to Claude |
| `content-collect` | Picks up finished review batches and saves Claude's score, suggested title and description, and list of issues |
| `content-prune` | Deletes logged checks older than the retention period |
| `content-test-alert` | Sends a sample alert to the alert webhook |

Pages come into the Pages table from a sitemap or by hand. Each uptime check updates the page's current status and, depending on the logging mode, adds a row to Checks. When a page's status changes, the monitor posts an alert to a webhook. `content-summary` reads both tables. SEO data goes from Pages to Claude's Message Batches API and comes back onto Pages.

## How it's built

### Data model

Every page stores its own current status: up or down, since when, and the latest status code and response time. Checks is a log, and how much goes into it is configurable (see [Storage settings](#storage-settings)). SEO results work like the current status: only the latest review matters, so each audit overwrites the fields on the page instead of adding rows.

Status is a single select rather than a checkbox. Airtable leaves unchecked checkboxes out of API responses, so an empty checkbox could mean either "down" or "never checked." With a single select, empty only ever means "never checked."

Creating and updating records needs slightly different handling. When a new check is created, empty values are simply left out. When a page is updated, a missing value is sent as empty on purpose, so if a page loses its title, the old title gets cleared instead of hanging around.

Airtable can't save to two tables in one all-or-nothing operation, so the monitor writes the log before it updates the page. If the second write fails, the next run notices the same change again and logs it twice. Doing it the other way round would risk an outage never being logged at all, and a duplicate entry is the better failure.

### Storage settings

The free Airtable plan has a small record limit per base, and logging every check fills it quickly. Logging every check keeps this many rows in Checks:

**active pages × 24 checks a day × days kept**

So 10 pages kept for 14 days is 3,360 rows. To make the tool usable on any plan, two settings control storage:

| Setting | Values | Default |
|---|---|---|
| `CHECK_LOG` | `changes` logs only when a page goes down or comes back up. `all` logs every check. | `changes` |
| `RETENTION_DAYS` | How many days of logged checks `content-prune` keeps | `90` |

The defaults suit the free plan. In `changes` mode, healthy pages add nothing to the log, so a stable site might log a few dozen rows in a year. Switch to `all` if your plan has room and you want detailed response-time history.

### Alerts

When a page goes down or comes back up, the monitor sends a JSON payload to whatever URL is in `ALERT_WEBHOOK_URL`. It works with anything that accepts a webhook: an automation platform like Make, Zapier or n8n, a chat tool's incoming webhook, or a small service of your own. Leave the setting out and the monitor runs exactly the same, just without alerts.

I tested it with [Make](https://www.make.com/). The `make/` folder has the scenario I use, as a sample to import and adapt: it posts every alert to Discord and emails outages. Each channel is on its own route, so a failure in one can't block the other, and a failed email is retried three times, 15 minutes apart. You'll need to create your own webhook and connect your own accounts, since connections don't carry over between Make accounts. Routing could just as easily send outages to Slack, open a ticket, or text whoever's on call.

The split is deliberate. Python decides when to alert and what the message says, in code that's tested. The webhook's receiver decides where alerts go, so someone without access to the code can change that.

It pushes alerts rather than having an automation tool watch Airtable for changes. Polling Airtable every 15 minutes would cost credits on every check, even when nothing has happened, and would use up a free Make plan's monthly allowance before sending a single alert. A webhook only fires when something actually changes.

A few details:

- A page's first check only alerts if the page is down. "It's up, and we've never checked it before" isn't news.
- Alerts are sent after the results are saved to Airtable. If saving fails, no alert goes out, and the next run spots the same change and alerts then.
- If an alert can't be delivered, the monitor still saves everything and then exits with an error, so a scheduled run shows as failed and GitHub emails me.
- The webhook URL is treated as a secret, since anyone who has it can send fake alerts. Delivery errors report only the status code, because the full error text would include the URL.

Each payload looks like this:

```json
{
  "event": "recovered",
  "page": "Research library",
  "url": "https://example.org/library/",
  "status_code": 200,
  "error": null,
  "duration": "2h 15m",
  "checked_at": "2026-10-24T15:17:02+00:00",
  "message": "🟢 Research library is back up after 2h 15m down. https://example.org/library/",
  "test": false
}
```

| Field | Meaning |
|---|---|
| `event` | `down` or `recovered` |
| `page` | The page's name, or its URL if it has no name |
| `url` | The page's URL |
| `status_code` | The HTTP status code, or `null` if the page didn't respond |
| `error` | What went wrong when there was no response, such as a timeout |
| `duration` | How long the previous status lasted: on recovery, how long the page was down |
| `checked_at` | When the check ran, in UTC |
| `message` | A ready-to-post summary, so a receiver can forward it without formatting anything |
| `test` | `true` for alerts from `content-test-alert` |

Every payload has every field, even when the value is `null`. Tools like Make learn a webhook's structure from a sample, so the shape has to stay the same.

### Summaries

The summary works the same whichever logging mode is in use. It sends Claude two things: each active page's current status, and the outages and recoveries from the past week. Those events are worked out in Python from whatever is in the log. In `all` mode, a run of hourly checks collapses into a single "went down" and a single "came back up," so the cost of a summary stays small however much is stored.

Durations are calculated in code, not by Claude. Language models are unreliable at date arithmetic, so the prompt hands over finished durations and tells Claude to use them as given. Empty sections are sent as "(none)" rather than left blank, so Claude can tell "nothing happened" from "no data."

### Importing pages

`content-import` reads a sitemap, follows any sitemap indexes down to the actual lists of pages, and adds the pages that aren't tracked yet. It only ever creates records. An upsert would have been simpler, but it would also have switched monitoring back on for pages I'd deliberately paused, so existing rows are left alone.

It also lists pages I'm tracking that have dropped out of the sitemap, since those may have been moved or deleted. A `--dry-run` flag shows exactly what would be added before anything changes. Sitemaps come from sites I don't control, so they're parsed with `defusedxml`, which blocks the malicious-XML tricks that Python's standard parser is open to.

### Working with Claude

The SEO review is defined once as a Pydantic model. Its schema is sent with every request, so Claude's answer always comes back in the same shape and maps straight onto Airtable columns. The API can't enforce number ranges, so the 1 to 10 score is checked with Pydantic when results come in.

Reviews go through the Message Batches API instead of one call per page. Nobody needs them instantly, and batch requests cost half as much. Each request uses the page's Airtable record ID as its custom ID, which is how a result finds its way back to the right row. Batches waiting to be collected are tracked in Airtable rather than a local file, so collection works the same from a scheduled job as from my laptop.

I chose models by trying them. The uptime summary uses Claude Haiku because the task is simple and Haiku is the cheapest option. The SEO review uses Claude Sonnet: I ran both models on the same pages, and Sonnet's critiques were noticeably more useful.

### Fetching pages

Requests identify the tool with a User-Agent and give up after 10 seconds. Audits and sitemap imports also wait a second between requests so they don't hammer anyone's site.

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

   # Optional
   ALERT_WEBHOOK_URL=https://...
   CHECK_LOG=changes
   RETENTION_DAYS=90
   ```
   The base ID is just the `app...` part of the base's URL.

Only the commands that talk to Claude need the Claude key. `content-import`, `content-monitor` and `content-prune` run without it.

To set up alerts, point `ALERT_WEBHOOK_URL` at your webhook and run `uv run content-test-alert`. If your tool learns the payload's structure from a sample, as Make does, send it this first sample: it fills in every field.

## Running it locally

```bash
uv run content-import https://example.org/sitemap.xml --dry-run    # preview new pages
uv run content-import https://example.org/sitemap.xml --contains /blog/ --limit 20

uv run content-monitor    # check every active page
uv run content-summary    # get Claude's take on current status and the past week

uv run content-audit      # gather page content and send it for review
uv run content-collect    # save any reviews that are ready

uv run content-prune --dry-run    # count checks older than the retention period
uv run content-prune --days 30    # delete checks older than 30 days

uv run content-test-alert              # send a sample "down" alert
uv run content-test-alert --recovered  # send a sample "back up" alert
```

It's worth doing a dry run before every import. Real sitemaps often include tag, author and attachment pages you won't want to monitor, and `--contains` and `--limit` let you narrow things down. Run any command with `--help` to see its options.

Most review batches finish within an hour, though they can take up to 24. You can run `content-collect` as often as you like. It tells you which batches are still processing and skips any it has already saved.

`content-prune` permanently deletes records, so try `--dry-run` first. Without `--days`, it uses the `RETENTION_DAYS` setting, and it refuses a value below 1, which would delete everything. To try the other logging mode for a single run, set it in front of the command: `CHECK_LOG=all uv run content-monitor`.

When you change how alerts are routed, test both kinds. An outage and a recovery usually take different paths, and it's easy to break one while checking only the other.

## Automation

Four GitHub Actions workflows run the tool on a schedule. All times are UTC.

| Workflow | When it runs | Command |
|---|---|---|
| `monitor.yml` | Every hour at :17 | `content-monitor` |
| `audit.yml` | Mondays at 10:23 | `content-audit`, then `content-summary` |
| `collect.yml` | Every 6 hours | `content-collect` |
| `prune.yml` | Daily at 04:43 | `content-prune` |

Each one can also be started by hand from the Actions tab. Importing isn't scheduled, since it's worth checking a dry run before adding pages. The weekly uptime summary appears on the audit run's page.

The credentials live in a GitHub environment called `production`, which only the `main` branch can use, so they're only ever available to code that's already been merged. Inside each workflow, credentials are passed only to the step that needs them. The uptime and prune workflows never get the Claude key, and only the uptime workflow gets the alert webhook. Each workflow has its own timeout and won't start a new run while the previous one is still going.

To turn on alerts for scheduled runs, add `ALERT_WEBHOOK_URL` as a secret in the `production` environment. To change the storage settings, add `CHECK_LOG` or `RETENTION_DAYS` as variables there. If they're not set, alerts are skipped and the defaults apply.

A separate `ci.yml` workflow runs linting, formatting checks, type checking and tests on every push and pull request. It has no access to any credentials. Dependabot opens pull requests when the GitHub Actions or Python dependencies have updates, and CI checks each one before it's merged.

## Development

```bash
uv run ruff check          # lint
uv run ruff format         # format
uv run pyright             # type check
uv run pytest              # test
```

The tests cover the pure functions: reading the storage settings, deciding when a check gets logged and when it triggers an alert, building alert payloads, turning a log into outage and recovery events, building Airtable formulas, turning results into Airtable fields, pulling content out of HTML, reading sitemaps, deciding which pages to import, and validating Claude's reviews. None of them touch the network, Airtable or Claude, so they run in a second and don't cost anything. That's also why CI can run them without credentials.

## Airtable schema

Field names are case-sensitive and need to match exactly.

**Pages**

| Field | Type |
|---|---|
| URL | URL (primary) |
| Name | Single line text |
| Active | Checkbox |
| Status | Single select, with the options `Up` and `Down` |
| Status since | Date with time |
| Last checked | Date with time |
| Last status code | Number |
| Last response time (ms) | Number |
| Current title | Single line text |
| Current description | Long text |
| Word count | Number |
| SEO score | Number |
| SEO summary | Long text |
| Suggested title | Single line text |
| Suggested description | Long text |
| SEO issues | Long text |
| Last audited | Date with time |

"Last checked" is written by the monitor. It used to be a rollup of Checks, but in `changes` mode the newest logged check usually isn't the newest check.

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
  importer.py    content-import: decide which sitemap pages to add, and add them
  summary.py     content-summary: Claude's health report
  audit.py       content-audit: gather page content and submit reviews
  collect.py     content-collect: save finished reviews
  prune.py       content-prune: delete old checks
  alerts.py      alert rules, payloads and delivery, plus content-test-alert
  config.py      reads credentials and settings from the environment or .env
  checker.py     the shared HTTP client and single-page check
  history.py     turns logged checks into outage and recovery events
  formulas.py    Airtable formulas for filtering checks by date
  sitemap.py     reads sitemaps and sitemap indexes
  extractor.py   pulls the title, description, headings and word count from HTML
  reviewer.py    the review schema, prompt, batch requests and validation
  store.py       turns results into Airtable fields and decides what gets logged
tests/
make/
  alerts.blueprint.json   sample Make scenario for routing alerts
.github/
  workflows/     CI plus the four scheduled jobs
  dependabot.yml
```

## Limitations and next steps

- One failed check is enough to send a "down" alert, so a brief blip produces a down alert followed by a recovery an hour later. Waiting for two failures in a row before alerting would cut out the noise.
- A failed alert isn't retried. The run fails so I find out, but by the next run the new status is already saved, so that change won't be sent again.
- Once an alert is accepted, delivering it is up to the receiver. Most webhook endpoints, Make's included, reply as soon as they've queued a request, so problems further along show up in that tool's own logs, not here.
- Imports match URLs exactly, so `https://example.org/page` and `https://example.org/page/` count as two different pages. Compressed (`.xml.gz`) sitemaps aren't supported, and an import stops after reading 50 sitemaps.
- If a page went down more than a week ago and has since recovered, the summary doesn't list it as an event. Its current status still shows how long it's been back up.
- Every page is a record too, so very large imports can still reach the free plan's limit, whatever the logging mode.
- Claude only sees metadata and headings, not the body text, so reviews cover how findable and well-structured a page is rather than how well it's written.
- If a page is deleted from Airtable between `content-audit` and `content-collect`, saving that batch fails.
- GitHub doesn't guarantee exact start times for scheduled runs, and they can be delayed when it's busy. On public repos, scheduled workflows also pause after 60 days without any repository activity.
- Every scheduled run counts as a deployment to the `production` environment, which clutters the repo's deployment history.
- Links within pages aren't checked yet.
