# Configuration

Chickadee reads its settings from environment variables. Locally, put them in a `.env` file in the project root. On GitHub, they come from the `production` environment (see [Automation](automation.md#credentials-and-settings)).

## Settings

| Setting | Required | Default | What it does |
|---|---|---|---|
| `AIRTABLE_TOKEN` | Yes | | Airtable personal access token |
| `AIRTABLE_BASE_ID` | Yes | | The `app...` part of the base's URL |
| `ANTHROPIC_API_KEY` | For `audit`, `collect`, `digest` | | Claude API key |
| `ALERT_WEBHOOK_URL` | No | | Where `uptime` sends alerts. Without it, there are no alerts. |
| `DIGEST_WEBHOOK_URL` | No | | Where `digest` sends the weekly email. Without it, the digest is only printed. |
| `CHECK_LOG` | No | `changes` | `changes` logs only when a page goes down or comes back. `all` logs every check. |
| `RETENTION_DAYS` | No | `90` | How many days of logged checks `prune` keeps |
| `STALE_AFTER_DAYS` | No | `365` | How long a page can go without an update before it's flagged as stale |
| `IGNORE_SELECTORS` | No | | CSS selectors for parts of a page that `audit` and `links` should skip, like `.related-posts, time` |

Only the commands that call Claude need the Claude key. `import`, `uptime`, `links`, `flags` and `prune` run without it.

Both webhook URLs are secrets. Anyone who has one can send fake alerts or emails, so keep them out of the repo and out of logs.

Settings are checked when a command starts. An unknown `CHECK_LOG` value, a number below 1 or an invalid CSS selector stops the command with a message saying what's wrong, instead of failing halfway through. An empty value counts as unset, so a GitHub variable that doesn't exist falls back to the default.

To try a setting for a single run, put it in front of the command:

```bash
CHECK_LOG=all uv run chickadee uptime
STALE_AFTER_DAYS=30 uv run chickadee flags
```

For `prune`, a `--days` flag on the command line overrides `RETENTION_DAYS`, which overrides the default. The most specific instruction wins.

## Storage and your Airtable plan

Airtable's free plan has a small record limit per base, so how much Chickadee stores matters.

Every page is one record, and so is every topic and every review batch. The one table that can grow quickly is **Checks**, the uptime log. Logging every check keeps this many rows in it:

**active pages × 24 checks a day × days kept**

Ten pages kept for 14 days is 3,360 rows, well past the free plan's limit. That's why `CHECK_LOG` defaults to `changes`: healthy pages add nothing to the log, so a stable site might log a few dozen rows a year. The current status of every page is stored on the page itself either way, so nothing about the present is lost.

| Your situation | Suggested settings |
|---|---|
| Free plan, or a large site | `CHECK_LOG=changes`, `RETENTION_DAYS=90` (the defaults) |
| Paid plan, and you want response-time history | `CHECK_LOG=all`, with `RETENTION_DAYS` set so the formula above fits your plan |

`prune` deletes logged checks older than `RETENTION_DAYS`, and the scheduled workflow runs it daily.

## Staleness

What counts as out of date depends on the site. A research summary might be fine for three years, and a news page might not last one. Set `STALE_AFTER_DAYS` to match. [Design](design.md#attention-flags) explains how a page's last update is worked out.

## Ignoring parts of a page

Some sections change every time a page loads: a "related posts" widget, a "last updated 3 minutes ago" line, a rotating quote. Each change makes the page look edited, so it gets sent to Claude for review every week. Navigation, headers and footers are already ignored. `IGNORE_SELECTORS` covers the rest.

It's a CSS selector, and commas combine several, the same as in a stylesheet:

```bash
IGNORE_SELECTORS=.related-posts, time, #newsletter-signup
```

To find what to ignore, look in Airtable for pages whose Content changed at moves every week while the page itself hasn't changed. Open one in a browser, right-click the part that changes, choose **Inspect**, and look for a class or tag that identifies it.

Things to know:

- **It only affects a page's content.** The title, description and declared modified date are read before anything is removed, so ignoring `time` doesn't hide a page's last update from the staleness check.
- **The link checker skips those sections too.** Links in a widget that changes on every load aren't really part of the page.
- **Changing it re-reviews some pages once.** Removing a section changes the fingerprint of every page that had it, so those pages are reviewed again on the next audit and appear as changed in that week's digest. After that they're stable.
- **Try it locally first.** Run `audit` twice with the new setting. The affected pages are sent for review on the first run and not on the second.
