# Content Monitor

![CI](https://github.com/reinerb/content-monitor/actions/workflows/ci.yml/badge.svg)

Content Monitor keeps an eye on a list of web pages. Every hour it checks that each page is up, records the result in Airtable, and can send an alert the moment a page goes down or comes back. Once a week it reads each page's content, notes what has changed since the last audit, and sends new or changed pages to Claude, which summarizes each one, tags it by topic and reviews how easy it is to find. It also checks the links on every page each week and records any that are broken. Everything is written back to Airtable.

I built this to get hands-on understanding of the Airtable and Claude APIs, and I wanted it to solve a problem content teams really have: finding out which pages are broken, slow, or hard to find in search without someone checking them by hand.

## Commands

| Command | What it does |
|---|---|
| `content-import` | Reads a site's sitemap and adds any pages that aren't being tracked yet |
| `content-monitor` | Checks every active page, updates its current status, logs the check, and sends alerts for status changes |
| `content-summary` | Asks Claude for a short, plain-English report on current status and the past week's outages |
| `content-audit` | Reads each page's title, meta description, headings and main text, records whether it has changed, and sends new or changed pages to Claude for review |
| `content-collect` | Picks up finished review batches and saves Claude's summary, topics and review, along with which version of the page was reviewed |
| `content-links` | Checks the links in each page's main content and records the broken ones |
| `content-prune` | Deletes logged checks older than the retention period |
| `content-test-alert` | Sends a sample alert to the alert webhook |

Pages come into the Pages table from a sitemap or by hand. Each uptime check updates the page's current status and, depending on the logging mode, adds a row to Checks. When a page's status changes, the monitor posts an alert to a webhook. `content-summary` reads both tables. Each audit updates every page's content fingerprint, and only pages whose content has changed since their last review go to Claude's Message Batches API. The reviews come back onto Pages. A weekly link check records broken links on each page too.

## How it's built

### Data model

Every page stores its own current status: up or down, since when, and the latest status code and response time. Checks is a log, and how much goes into it is configurable (see [Storage settings](#storage-settings)). Reviews work like the current status: only the latest one matters, so each audit overwrites the fields on the page instead of adding rows.

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

### Tracking changes

Each audit fingerprints every page: a short hash of its title, meta description and main text. Whitespace is collapsed first, and navigation, headers and footers are stripped, so reformatting or a new menu item doesn't count as a change. The fingerprint is the first 16 characters of a SHA-256 hash, which is plenty to tell versions of a page apart.

The point is to review only what's new. Claude sees a page when it's first added and again whenever its content changes, rather than every page every week. For a stable site, a weekly batch is usually a handful of pages.

Each page keeps two hashes. **Content hash** is what the page looks like now, updated by every audit. **Reviewed hash** is what it looked like when Claude last reviewed it successfully, written by `content-collect`. A page needs a review whenever the two differ. That means a failed review fixes itself: if a batch errors or never gets collected, the hashes stay different and the next audit sends the page again, without anything having to remember that something went wrong.

The reviewed hash has to be the version Claude actually saw, not whatever the page looks like when the results come back. So the hash travels with the request, in the batch's custom ID next to the record ID. The API caps custom IDs at 64 characters, which is why the hash is short.

A page's first audit sets a baseline and doesn't count as a change. To review everything anyway, for example after changing the prompt, the model or the topic list, run `content-audit --all`.

### Working with Claude

Claude reads each page's title, description, headings and main text, and returns a review in a fixed shape: a short summary of what the page says, its main point and whether the opening paragraph states it, the topics it covers, and an SEO score with a suggested title, description and list of issues. Whether the main point comes first matters because AI search tools tend to quote a page's opening.

The review is defined once as a Pydantic model. Its schema is sent with every request, so Claude's answer always comes back in the same shape and maps straight onto Airtable columns. The descriptive fields come before the score in the schema, and structured output keeps that order, so Claude writes down what a page says before judging it. The API can't enforce number ranges, so the 1 to 10 score is checked with Pydantic when results come in.

Topics come from a Topics table in Airtable, so the list can change without touching code. Each audit loads the list and adds it to the schema as an enum, so Claude can only pick topics that exist. Topics on Pages are linked records, which means each topic's row lists every page tagged with it. The API doesn't guarantee the capitalization of enum values, so names are matched case-insensitively when reviews are saved, and any name that doesn't match is reported instead of quietly dropped.

Pages longer than 3,000 words are cut off at a word boundary, and the prompt says so. That keeps a review well under a cent at Sonnet's batch price, and since only new and changed pages are reviewed, a typical week costs very little. The content hash still covers the full text, so an edit past the cutoff still triggers a review.

Page text is written by people outside the project, so it's treated as untrusted. It goes inside its own tags, and the system prompt tells Claude to review it, not to follow any instructions in it. The fixed output shape also limits what a manipulated response could do.

Reviews go through the Message Batches API instead of one call per page. Nobody needs them instantly, and batch requests cost half as much. Each request's custom ID combines the page's Airtable record ID with its content hash, which is how a result finds its way back to the right row and records which version was reviewed. Batches waiting to be collected are tracked in Airtable rather than a local file, so collection works the same from a scheduled job as from my laptop.

I chose models by trying them. The uptime summary uses Claude Haiku because the task is simple and Haiku is the cheapest option. The page review uses Claude Sonnet: I ran both models on the same pages, and Sonnet's critiques were noticeably more useful.

### Checking links

`content-links` checks the links inside each page's main content. It uses the same definition of main content as change tracking: navigation, headers and footers are stripped first, so a broken menu link doesn't get reported on every page in the site. Relative links are resolved against the page's final address after any redirects, fragments like `#methods` are removed, and links that can't be checked over HTTP, such as `mailto:`, are skipped.

Each unique link is checked once, however many pages use it, and the result is shared. Requests to the same site wait a second between them, while links to different sites don't wait for each other. Each check streams the response and stops at the status code, so no page bodies are downloaded. That also works with servers that handle HEAD requests badly.

A link checker that flags working links quickly stops being trusted, so results are split three ways:

| Result | What counts |
|---|---|
| Broken | 404 or 410, a domain that doesn't exist or refuses connections, or a malformed link |
| Unverified | 403, 429, server errors and timeouts, which usually mean a site is blocking automated requests or is briefly down |
| OK | Anything that ends in success after following redirects |

Broken and unverified links go in separate fields, so the broken list stays reliable. Once a link is fixed, it drops off on the next run.

Link checking is its own command rather than part of the audit. It makes a lot of requests and no calls to Claude, so it gets its own schedule and timeout. Finding broken links doesn't fail the run, because they're findings about the content, not a fault in the tool.

### Fetching pages

Requests identify the tool with a User-Agent and give up after 10 seconds. Audits and sitemap imports wait a second between requests, and link checks wait a second between requests to the same site, so none of them hammer anyone's site.

## Setup

You'll need [uv](https://docs.astral.sh/uv/), which takes care of installing the right Python version and the dependencies.

1. Clone the repo and install:
   ```bash
   uv sync
   ```
2. Create an Airtable base with the four tables listed under [Airtable schema](#airtable-schema), and add a few topics to the Topics table. Give each one a sentence on what counts. The descriptions go into the prompt, and specific ones tag pages more accurately than vague ones.
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

Only the commands that talk to Claude need the Claude key. `content-import`, `content-monitor`, `content-links` and `content-prune` run without it.

To set up alerts, point `ALERT_WEBHOOK_URL` at your webhook and run `uv run content-test-alert`. If your tool learns the payload's structure from a sample, as Make does, send it this first sample: it fills in every field.

## Running it locally

```bash
uv run content-import https://example.org/sitemap.xml --dry-run    # preview new pages
uv run content-import https://example.org/sitemap.xml --contains /blog/ --limit 20

uv run content-monitor    # check every active page
uv run content-summary    # get Claude's take on current status and the past week

uv run content-audit        # check for changes and send new or changed pages for review
uv run content-audit --all  # review every page, changed or not
uv run content-collect    # save any reviews that are ready
uv run content-links      # check the links on every active page

uv run content-prune --dry-run    # count checks older than the retention period
uv run content-prune --days 30    # delete checks older than 30 days

uv run content-test-alert              # send a sample "down" alert
uv run content-test-alert --recovered  # send a sample "back up" alert
```

It's worth doing a dry run before every import. Real sitemaps often include tag, author and attachment pages you won't want to monitor, and `--contains` and `--limit` let you narrow things down. Run any command with `--help` to see its options.

Most review batches finish within an hour, though they can take up to 24. You can run `content-collect` as often as you like. It tells you which batches are still processing and skips any it has already saved.

Running `content-audit` twice in a row is a good check. The second run should report every page as unchanged. If one shows as changed when nobody edited it, something on it changes on every load, like a timestamp or a list of related posts, and the extractor needs to strip it.

When `content-links` lists a link as unverified, try opening it in a browser. Most load fine, and the site is just blocking automated requests.

`content-prune` permanently deletes records, so try `--dry-run` first. Without `--days`, it uses the `RETENTION_DAYS` setting, and it refuses a value below 1, which would delete everything. To try the other logging mode for a single run, set it in front of the command: `CHECK_LOG=all uv run content-monitor`.

When you change how alerts are routed, test both kinds. An outage and a recovery usually take different paths, and it's easy to break one while checking only the other.

## Automation

Five GitHub Actions workflows run the tool on a schedule. All times are UTC.

| Workflow | When it runs | Command |
|---|---|---|
| `monitor.yml` | Every hour at :17 | `content-monitor` |
| `audit.yml` | Mondays at 10:23 | `content-audit`, then `content-summary` |
| `collect.yml` | Every 6 hours | `content-collect` |
| `links.yml` | Thursdays at 09:37 | `content-links` |
| `prune.yml` | Daily at 04:43 | `content-prune` |

Each one can also be started by hand from the Actions tab. Importing isn't scheduled, since it's worth checking a dry run before adding pages. The weekly uptime summary appears on the audit run's page.

The credentials live in a GitHub environment called `production`, which only the `main` branch can use, so they're only ever available to code that's already been merged. Inside each workflow, credentials are passed only to the step that needs them. The uptime, link-check and prune workflows never get the Claude key, and only the uptime workflow gets the alert webhook. Each workflow has its own timeout and won't start a new run while the previous one is still going.

To turn on alerts for scheduled runs, add `ALERT_WEBHOOK_URL` as a secret in the `production` environment. To change the storage settings, add `CHECK_LOG` or `RETENTION_DAYS` as variables there. If they're not set, alerts are skipped and the defaults apply.

A separate `ci.yml` workflow runs linting, formatting checks, type checking and tests on every push and pull request. It has no access to any credentials. Dependabot opens pull requests when the GitHub Actions or Python dependencies have updates, and CI checks each one before it's merged.

## Development

```bash
uv run ruff check          # lint
uv run ruff format         # format
uv run pyright             # type check
uv run pytest              # test
```

The tests cover the pure functions: reading the storage settings, deciding when a check gets logged and when it triggers an alert, building alert payloads, turning a log into outage and recovery events, building Airtable formulas, turning results into Airtable fields, pulling content out of HTML and fingerprinting it, deciding which pages need review, building and reading batch custom IDs, reading sitemaps, deciding which pages to import, building review prompts and schemas, cutting long pages down, matching topics, validating Claude's reviews, finding the links in a page, classifying link checks, and pacing requests to each site. None of them touch the network, Airtable or Claude, so they run in a second and don't cost anything. The link checker is tested with httpx's `MockTransport`, which answers each request with whatever the test specifies, so even the network code runs without a network. That's also why CI can run them without credentials.

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
| Content summary | Long text |
| Key point | Long text |
| Key point up front | Single select, with the options `Yes` and `No` |
| Topics | Link to Topics, allowing multiple |
| SEO score | Number |
| SEO summary | Long text |
| Suggested title | Single line text |
| Suggested description | Long text |
| SEO issues | Long text |
| Last audited | Date with time |
| Content hash | Single line text |
| Content changed at | Date with time |
| Reviewed hash | Single line text |
| Broken links | Long text |
| Unverified links | Long text |
| Broken link count | Number |
| Links checked at | Date with time |

"Last checked" is written by the monitor. It used to be a rollup of Checks, but in `changes` mode the newest logged check usually isn't the newest check. "Key point up front" is a single select rather than a checkbox for the same reason Status is.

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

**Topics**

| Field | Type |
|---|---|
| Name | Single line text (primary) |
| Description | Long text |

## Project layout

```
src/content_monitor/
  __init__.py    content-monitor: uptime checks
  importer.py    content-import: decide which sitemap pages to add, and add them
  summary.py     content-summary: Claude's health report
  audit.py       content-audit: detect changes and submit reviews
  collect.py     content-collect: save finished reviews
  prune.py       content-prune: delete old checks
  links.py       content-links: check the links in each page
  alerts.py      alert rules, payloads and delivery, plus content-test-alert
  config.py      reads credentials and settings from the environment or .env
  checker.py     the shared HTTP client and single-page check
  history.py     turns logged checks into outage and recovery events
  formulas.py    Airtable formulas for filtering checks by date
  sitemap.py     reads sitemaps and sitemap indexes
  extractor.py   pulls the title, description, headings, main text and links from HTML, and fingerprints the content
  reviewer.py    the review schema, prompt, topics, batch requests, custom IDs and validation
  store.py       turns results into Airtable fields, matches topics, and decides what gets logged and what needs review
tests/
make/
  alerts.blueprint.json   sample Make scenario for routing alerts
.github/
  workflows/     CI plus the five scheduled jobs
  dependabot.yml
```

## Limitations and next steps

- One failed check is enough to send a "down" alert, so a brief blip produces a down alert followed by a recovery an hour later. Waiting for two failures in a row before alerting would cut out the noise.
- A failed alert isn't retried. The run fails so I find out, but by the next run the new status is already saved, so that change won't be sent again.
- Once an alert is accepted, delivering it is up to the receiver. Most webhook endpoints, Make's included, reply as soon as they've queued a request, so problems further along show up in that tool's own logs, not here.
- Imports match URLs exactly, so `https://example.org/page` and `https://example.org/page/` count as two different pages. Compressed (`.xml.gz`) sitemaps aren't supported, and an import stops after reading 50 sitemaps.
- If a page went down more than a week ago and has since recovered, the summary doesn't list it as an event. Its current status still shows how long it's been back up.
- Every page is a record too, so very large imports can still reach the free plan's limit, whatever the logging mode.
- Claude reads only the first 3,000 words of a page, so very long pages are reviewed on their opening.
- Changing the topic list doesn't retag existing pages until they change or `content-audit --all` runs.
- Anything that changes every time a page loads, like a timestamp, makes the page look edited and sends it for review every week. The extractor strips navigation, headers and footers, but other changing sections have to be added by hand.
- If a page is deleted from Airtable between `content-audit` and `content-collect`, saving that batch fails.
- GitHub doesn't guarantee exact start times for scheduled runs, and they can be delayed when it's busy. On public repos, scheduled workflows also pause after 60 days without any repository activity.
- Every scheduled run counts as a deployment to the `production` environment, which clutters the repo's deployment history.
- Link checks only catch links that fail outright. A link that redirects to a site's homepage, or to a "page not found" message sent with a success code, looks fine.
- Each page's link check stops after its first 100 links.
