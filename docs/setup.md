# Setup

This walks through everything needed to run Chickadee on your own computer. To run it on a schedule once it's working, see [Automation](automation.md).

## What you'll need

- [uv](https://docs.astral.sh/uv/), which installs the right Python version and all the dependencies.
- An [Airtable](https://airtable.com/) account. The free plan works. See [Configuration](configuration.md#storage-and-your-airtable-plan) for how to stay within its record limit.
- A Claude API key from the [Claude Console](https://platform.claude.com/).
- Optionally, somewhere to receive webhooks for alerts and the digest email. I use [Make](https://www.make.com/), but anything that accepts a webhook works.

## 1. Install

```bash
git clone https://github.com/reinerb/chickadee.git
cd chickadee
uv sync
```

## 2. Build the Airtable base

Create a base with four tables: **Pages**, **Checks**, **Audit batches** and **Topics**. [Airtable schema](airtable-schema.md) lists every field. The names are case-sensitive and have to match exactly.

Then:

- **Add a few topics** to the Topics table, each with a sentence describing what counts. The descriptions go into the review prompt, and specific ones ("Research on the welfare of farmed fish, including slaughter and stocking density") tag pages more accurately than vague ones ("Fish").
- **Create a "Needs attention" view** on Pages: filter to Active is checked and Attention count is greater than 0, sorted by Attention count, highest first. That view is your to-do list.

## 3. Get credentials

- **Airtable:** create a personal access token with the scopes `data.records:read`, `data.records:write` and `schema.bases:read`, limited to your Chickadee base. Giving it access to only that base means a leaked token can't touch anything else.
- **Claude:** create an API key in the Claude Console.

The base ID is the `app...` part of the base's URL. Copy only that part, not the table or view IDs that follow it.

## 4. Create a `.env` file

In the project root (it's already in `.gitignore`):

```
AIRTABLE_TOKEN=pat...
AIRTABLE_BASE_ID=app...
ANTHROPIC_API_KEY=sk-ant-...
```

Everything else is optional and listed in [Configuration](configuration.md).

## 5. First run

```bash
uv run chickadee import https://example.org/sitemap.xml --dry-run
```

Most sites list their sitemap in `/robots.txt`. WordPress sites usually have one at `/wp-sitemap.xml`. Read the dry run's output before importing: real sitemaps often include tag, author and attachment pages you won't want to monitor. Narrow it down with `--contains` and `--limit`:

```bash
uv run chickadee import https://example.org/sitemap.xml --contains /blog/ --limit 20
```

Then run each step once:

```bash
uv run chickadee uptime    # check every page
uv run chickadee audit     # read every page and send it for review
```

Reviews go through Claude's batch API, so they come back later, usually within an hour and always within a day. Run `collect` until it says everything is saved:

```bash
uv run chickadee collect
```

Then the rest:

```bash
uv run chickadee links                          # check every link
uv run chickadee flags                          # flag pages that need attention
uv run chickadee digest --no-send --no-overview # print a digest, free
```

Your Pages table should now have a status, a summary, topics, a review, link results and flags for every page.

## Optional: alerts

Set `ALERT_WEBHOOK_URL` in `.env` to your webhook's URL, then send a test:

```bash
uv run chickadee test-alert              # a sample "down" alert
uv run chickadee test-alert --recovered  # a sample "back up" alert
```

If your tool learns a payload's shape from a sample, as Make does, send the first one. It fills in every field. Always test both kinds after changing how alerts are routed: outages and recoveries usually take different paths, and it's easy to break one while only checking the other.

To use the sample Make scenario:

1. In Make, create a scenario and import `make/alerts.blueprint.json`.
2. Replace its webhook with a new one of your own, and copy that webhook's URL into `.env`.
3. Reconnect the Discord and email modules to your own accounts, since connections don't carry over between Make accounts. Change the channel and email addresses.
4. Click **Run once**, then run `chickadee test-alert` so Make learns the payload.
5. Turn the scenario on, set to run immediately.

[Webhooks](webhooks.md) has the payload format and more on how the sample scenario is built.

## Optional: emailing the digest

Set `DIGEST_WEBHOOK_URL` to a **second** webhook, separate from the alerts one, then:

1. In Make, create a scenario and import `make/digest.blueprint.json`, or build it from scratch: a **Custom webhook** followed by an email module.
2. Replace the webhook with your own and reconnect the email module.
3. Click **Run once**, then run:
   ```bash
   uv run chickadee digest --test --no-overview
   ```
   That sends a real digest built from your data, marked `[TEST]` in the subject, without calling Claude.
4. If you built the scenario yourself, map the email's subject to `subject` and its HTML body to `html`.
5. Turn the scenario on.

Make's free plan allows two active scenarios, which alerts and the digest use exactly.

## Everyday use

```bash
uv run chickadee uptime
uv run chickadee audit          # reviews new and changed pages, and all pages after a topic or prompt change
uv run chickadee audit --all    # review every page once, regardless
uv run chickadee collect        # safe to run as often as you like
uv run chickadee links
uv run chickadee flags
uv run chickadee digest
uv run chickadee prune --dry-run
```

Some habits worth keeping:

- **Run `audit` twice in a row** after setting up a new site. The second run should report every page as unchanged. If a page shows as changed when nobody edited it, something on it changes on every load, like a timestamp or a "related posts" list. See [Design](design.md#tracking-changes).
- **Open unverified links in a browser.** Most load fine, and the site is just blocking automated requests.
- **Run `flags` twice in a row.** The second run should update nothing.
- **Use `prune --dry-run` first.** Pruning permanently deletes records.
- **Try a setting for one run** by putting it in front of the command: `CHECK_LOG=all uv run chickadee uptime`, or `STALE_AFTER_DAYS=30 uv run chickadee flags`.
