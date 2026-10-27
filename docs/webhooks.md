# Webhooks

Chickadee sends two kinds of messages to webhooks: **alerts**, when a page goes down or comes back, and the **weekly digest**. Each has its own URL setting and its own fixed payload, so they can be routed independently.

They work with anything that accepts a JSON POST: an automation platform like Make, Zapier or n8n, a chat tool's incoming webhook, or a small service of your own. I tested both with [Make](https://www.make.com/), and the `make/` folder has the two scenarios I use as samples.

Python decides *when* to send something and *what* it says, in code that's tested. The receiver decides *where* it goes, so routing can change without touching the code.

## Alerts

Set `ALERT_WEBHOOK_URL`, and `chickadee uptime` posts an alert whenever a page's status changes.

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
| `duration` | How long the page has been down. On recovery, that's the whole outage. On a down alert, it's `null` unless the alert is a retry from an earlier run. It's also `null` when a recovery alert is retried, because the start of the outage is no longer known. |
| `checked_at` | When the check ran, in UTC |
| `message` | A ready-to-post summary, so a receiver can forward it without formatting anything |
| `test` | `true` for alerts sent by `chickadee test-alert` |

Every payload has every field, even when a value is `null`. Tools like Make learn a webhook's structure from a sample, so the shape has to stay the same.

When alerts are sent:

- **Only on a change.** A page that stays down doesn't alert every hour.
- **Only once a failure is confirmed.** A page that fails its check is checked again 30 seconds later, and it only counts as down if it fails both times. A dropped connection or a slow response that clears up in seconds never becomes an alert.
- **A page's first check only alerts if it's down.** "It's up, and we've never checked it before" isn't news.
- **After results are saved.** If saving to Airtable fails, no alert goes out, and the next run spots the same change and alerts then.
- **Failed alerts are retried on the next run.** Each page remembers the last status that was successfully announced, in its "Alerted status" field. An alert is due whenever that differs from the current status, so an alert that didn't go through is sent next time.
- **Stale alerts are never sent.** If a "down" alert fails and the page recovers before the next run, the two statuses match again and nothing is sent. Nobody hears a page is down after it's already back.
- **Failures are loud.** If an alert can't be delivered, `uptime` still saves everything, then exits with an error so a scheduled run shows as failed.

A run that crashes after sending an alert but before recording it will send that alert again next time. That's the deliberate trade-off: an occasional duplicate is better than a missed outage.

`chickadee test-alert` sends a sample "down" alert, and `--recovered` sends a sample "back up" one. Both are marked `"test": true`.

### Sample scenario: `make/alerts.blueprint.json`

```
Custom webhook ─┬─ (event = down) ─▶ Email     [retries on failure]
                └─ (everything) ───▶ Discord   [failures ignored]
```

Every alert goes to Discord, and outages also go out by email. Each channel is on its own route, so a failure in one can't stop the other. A failed email is retried three times, 15 minutes apart, which needs **Allow storing of incomplete executions** turned on in the scenario's settings. The email subject adds `[TEST]` for test alerts.

Routing could just as easily send outages to Slack, open a ticket, or text whoever's on call.

## Weekly digest

Set `DIGEST_WEBHOOK_URL`, and `chickadee digest` posts the digest after printing it.

```json
{
  "subject": "Content digest: Oct 20 to Oct 27, 2026",
  "markdown": "# Content digest: Oct 20 to Oct 27, 2026\n\nTwo new pages...",
  "html": "<div style=\"font-family: sans-serif; ...\"><h1>Content digest: ...</h1>...</div>",
  "week_start": "2026-10-20T10:47:12+00:00",
  "week_end": "2026-10-27T10:47:12+00:00",
  "new_pages": 2,
  "changed_pages": 3,
  "needs_attention": 5,
  "down_now": 0,
  "test": false
}
```

| Field | Meaning |
|---|---|
| `subject` | A ready-to-use subject line, starting with `[TEST]` for test digests |
| `markdown` | The digest as Markdown |
| `html` | The same digest as email-ready HTML |
| `week_start`, `week_end` | The period it covers, in UTC |
| `new_pages`, `changed_pages`, `needs_attention`, `down_now` | Counts, for a receiver that wants to route or label on them |
| `test` | `true` for digests sent with `--test` |

The HTML is built with raw HTML turned off. Page names and summaries come from other people's websites, so a tag like `<script>` in a page title is escaped instead of ending up live in the email, and `javascript:` links aren't turned into links.

The digest is printed before it's sent, so a failed send never loses it. A failed send still exits with an error.

### Sample scenario: `make/digest.blueprint.json`

```
Custom webhook ──▶ Email (HTML)   [retries on failure]
```

The email's subject is `subject` and its body is `html`. Give the email module a Break error handler with retries, as in the alerts scenario, so a short outage at the email service delays the digest instead of losing it.

## Why two webhooks

The alert payload promises one fixed shape, and the alerts scenario posts every message to Discord. The digest has a different shape and is far longer than a chat message allows. Separate webhooks keep each scenario simple. On Make's free plan, which allows two active scenarios, they use both.

## Why webhooks instead of watching Airtable

An automation tool could watch Airtable for changes instead, with no Python involved. But polling costs a credit on every check, even when nothing has happened. Checking every 15 minutes would use up a free Make plan's monthly allowance before a single alert went out. A webhook only fires when something actually changes.

## Keeping webhook URLs secret

Anyone with a webhook URL can send messages through it, so both URLs are treated as secrets: kept in `.env` or GitHub secrets, never committed. Errors from posting to a webhook report only the status code or the type of failure, never the URL itself, since the full error text from the HTTP library includes it. Alerts and the digest share one small function for this, so the rule lives in one place.

## What happens after a webhook accepts a message

Most webhook endpoints, Make's included, reply as soon as they've queued a request, before doing anything with it. Chickadee only knows the message was accepted. Problems further along, like an email service being down, show up in the receiving tool's own history and error notifications, so turn those on.
