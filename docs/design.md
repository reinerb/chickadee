# Design

How each part of Chickadee works, and why it works that way.

## Principles

A few ideas come up again and again:

- **Airtable is the hub.** Each command does one job and writes its results to the page's row. Anything that needs the full picture, like the flags and the digest, reads it back from there.
- **Code handles facts, Claude handles judgment.** Counts, dates, durations, lists and links come from Python, where they're exact. Claude writes summaries, reviews and the digest's opening, the parts that need judgment.
- **Only report what the evidence supports.** A link is only "broken" when it's definitely broken, and a page is only flagged when the data backs it up. A tool that cries wolf stops being trusted.
- **Failures either fix themselves or get noticed.** Missed reviews and undelivered alerts are retried on the next run without any bookkeeping. Failed deliveries also fail the run so GitHub reports them.
- **Other people's content is untrusted.** Sitemaps, page text and page titles come from sites Chickadee doesn't control, so they're handled as data, never as instructions or live HTML.
- **Be polite to websites.** Requests identify the tool, give up after a while, and never pile onto one site.

## Data model

Every page stores its own current state on its row: up or down, since when, its latest review, its broken links, its flags. Only the uptime log, Checks, keeps history, because that history is useful and nothing else's is. A page's current review is the only one that matters, so each review overwrites the last instead of adding rows. [Airtable schema](airtable-schema.md) lists every field.

Creating and updating records need slightly different handling. When a check is created, empty values are left out. When a page is updated, a missing value is sent as empty on purpose, so if a page loses its title, the old one gets cleared instead of hanging around.

Status fields are single selects, not checkboxes. Airtable leaves unchecked checkboxes out of API responses, so an empty checkbox could mean either "no" or "never checked."

## Uptime

`chickadee uptime` checks every active page, updates its current status, and, depending on the `CHECK_LOG` setting, logs the check. By default it only logs changes, since logging every check would quickly fill an Airtable free plan. [Configuration](configuration.md#storage-and-your-airtable-plan) has the details.

Airtable can't save to two tables in one all-or-nothing operation, so the log is written before the page is updated. If the second write fails, the next run notices the same change again and logs it twice. Doing it the other way around would risk an outage never being logged at all, and a duplicate entry is the better failure.

**Failed checks are retried before they count.** Most one-off failures are a dropped connection or a slow response that's gone seconds later. Any page that fails gets checked again after 30 seconds, and only a page that fails both times is recorded as down. The usual fix, alerting only after two failed runs in a row, would make every real outage at least an hour late with hourly checks. The retry has no such delay and needs nothing stored. All failing pages share a single pause, so if a whole site goes down, the run takes 30 seconds longer, not 30 seconds per page. A blip that clears on the retry is never recorded, so the status, log, flags and digest all agree it didn't happen.

**Alerts use the same idea as review hashes.** Each page keeps two statuses:

- **Status** is what the page is doing now, updated by every check.
- **Alerted status** is the last status that was successfully announced, written only after an alert is delivered.

An alert is due whenever the two differ. That means a failed alert is sent again on the next run, and if the page recovers before then, the two match again and the outdated alert is never sent. As with reviews, nothing has to remember that something went wrong.

Alerts go out after both writes, so a failed save never produces an alert for a change that wasn't recorded. Alerted status is written last, after delivery. If a run crashes between sending and recording, the next run sends the alert again, and a duplicate is the better failure here too. [Webhooks](webhooks.md) covers when alerts fire and what they contain.

## Importing pages

`chickadee import` reads a sitemap, follows any sitemap indexes down to the actual lists of pages, and adds the pages that aren't tracked yet. It only ever creates records. An upsert would have been simpler, but it would also have switched monitoring back on for any page I'd deliberately paused, so existing rows are left alone.

It also lists tracked pages that have dropped out of the sitemap, since those may have moved or been deleted. Pages tracked from other sites aren't counted, and a `--contains` filter narrows what gets added without making the rest of the sitemap look missing. `--dry-run` shows exactly what would happen before anything changes.

Sitemaps come from sites I don't control, so they're parsed with `defusedxml`, which blocks the malicious-XML tricks Python's standard parser is open to. Following indexes stops after 50 sitemaps, and a sitemap that points back to one already read is skipped, so a badly built sitemap can't send the importer in circles.

## Tracking changes

Each audit fingerprints every page: a short hash of its title, meta description and main text. Navigation, headers and footers are stripped and whitespace is collapsed first, so reformatting or a new menu item doesn't count as a change. The fingerprint is the first 16 characters of a SHA-256 hash, which is plenty to tell versions of a page apart.

The point is to only review what's new. Claude sees a page when it's first added and again whenever its content changes, not every page every week. For a stable site, a weekly batch is usually a handful of pages.

Each page keeps two hashes:

- **Content hash** is what the page looks like now, updated by every audit.
- **Reviewed hash** is what it looked like when Claude last reviewed it successfully, written by `collect`.

A page needs a review whenever the two differ. That makes failed reviews fix themselves: if a batch errors or never gets collected, the hashes stay different, and the next audit sends the page again. Nothing has to remember that something went wrong.

The reviewed hash has to be the version Claude actually saw, not whatever the page looks like when the results come back. So the hash travels with the request, in the batch's custom ID next to the page's record ID. The API caps custom IDs at 64 characters, which is why the hash is short.

A page's first audit sets a baseline and doesn't count as a change. `chickadee audit --all` reviews everything regardless, for when the review itself has changed: a new prompt, model or topic list.

## Reviews with Claude

Claude reads each page's title, description, headings and main text, and returns a review in a fixed shape:

- a short summary of what the page says
- its main point, and whether the opening paragraph states it
- the topics it covers
- an SEO score from 1 to 10, with a suggested title, a suggested description, and a list of issues

Whether the main point comes first matters because AI search tools tend to quote a page's opening.

**The shape is a Pydantic model.** Its schema is sent with every request using structured outputs, so the answer always comes back in the same shape and maps straight onto Airtable fields. The descriptive fields come before the score in the schema, and structured output keeps that order, so Claude writes down what a page says before judging it. The API can't enforce number ranges, so the score's 1 to 10 range is checked with Pydantic when results come in.

**Topics come from Airtable,** so the list can change without touching code. Each audit loads it and adds it to the schema as an enum, so Claude can only choose topics that exist. The API doesn't guarantee the capitalization of enum values, so names are matched case-insensitively when reviews are saved, and any name that doesn't match is reported instead of dropped silently.

**Long pages are cut off at 3,000 words,** at a word boundary, and the prompt says so. That keeps a review well under a cent at Sonnet's batch price. The content hash still covers the full text, so an edit past the cutoff still triggers a review.

**Page text is treated as untrusted.** It goes inside its own tags, and the system prompt tells Claude to review it, not follow any instructions in it. The fixed output shape also limits what a manipulated response could do.

**Reviews go through the Message Batches API** instead of one call per page. Nobody needs them instantly, and batch requests cost half as much. Batches waiting to be collected are tracked in Airtable, so `collect` works the same from a scheduled job as from a laptop, and it's safe to run as often as you like.

**Models were chosen by trying them.** The page review uses Claude Sonnet: I ran Haiku and Sonnet on the same pages, and Sonnet's critiques were noticeably more useful. The digest's opening paragraph uses Claude Haiku, because the task is simple and Haiku is the cheapest option.

## Checking links

`chickadee links` checks the links inside each page's main content, using the same definition of main content as change tracking. That way a broken menu link doesn't get reported on every page in the site. Relative links are resolved against the page's final address after any redirects, fragments like `#methods` are removed, and links that can't be checked over HTTP, such as `mailto:`, are skipped.

Each unique link is checked once, however many pages use it. Requests to the same site wait a second between them, while links to different sites don't wait for each other. Each check streams the response and stops at the status code, so no page bodies are downloaded. That also works with servers that handle HEAD requests badly.

A link checker that flags working links quickly stops being trusted, so results are split three ways:

| Result | What counts |
|---|---|
| Broken | 404 or 410, a domain that doesn't exist or refuses connections, or a malformed link |
| Unverified | 403, 429, server errors and timeouts, which usually mean a site is blocking automated requests or is briefly down |
| OK | Anything that ends in success after following redirects |

Broken and unverified links go in separate fields, so the broken list stays reliable. Once a link is fixed, it drops off on the next run.

Link checking is its own command rather than part of the audit. It makes a lot of requests and no calls to Claude, so it gets its own schedule and timeout. Finding broken links doesn't fail the run, because they're findings about the content, not a fault in the tool.

## Attention flags

`chickadee flags` turns everything the other commands record into one list. Each active page is checked against six rules:

| Flag | When it's raised |
|---|---|
| Down | The page's current status is down |
| Has broken links | The link check found at least one broken link |
| Stale | The page hasn't been updated within the staleness period, a year by default |
| Low SEO score | Claude's review scored it 4 or lower |
| Missing metadata | The page has been audited and has no title or no meta description |
| Key point buried | Claude's review found the opening doesn't state the main point |

**Flags only fire when the data supports them.** A page that hasn't been audited isn't missing metadata, and one that hasn't been reviewed doesn't have a low score.

**Staleness uses the most recent of three dates:** the modified date the page declares in its own metadata, the last change Chickadee detected, and, if there's neither, when the page was added to Airtable. Change tracking only knows about changes since monitoring started, so without the page's own date, nothing could be flagged as stale for a year. Most CMSs, WordPress included, publish that date. The fallback is deliberately cautious: without evidence a page is old, it isn't flagged.

**The rules live in Python, not Airtable formula fields,** so they're tested, versioned, and shared with the digest. The command runs daily and only writes to pages whose flags have changed, so most runs touch almost nothing. The staleness period is a setting because it differs between sites. The score threshold isn't.

## The weekly digest

`chickadee digest` writes a weekly report with four sections: new pages, changed pages, what needs attention, and uptime. Each new or changed page is listed with Claude's summary of it. If a page changed and its new review hasn't come back yet, it says "review pending" rather than showing a summary of the old version.

**Python writes the lists, and Claude writes only the opening.** A digest is mostly names, links, dates and counts. Those have to be exact, so they come straight from the data. Claude's part is the judgment call: two to four sentences on what changed and what most needs attention. It works from the same lists that appear below its paragraph, so it can only mention pages that are actually there, and the page summaries it reads are passed as data, not instructions.

**The facts never depend on the AI.** If the API call fails, the digest still goes out without its opening paragraph, and `--no-overview` skips Claude entirely. Messages about the run go to stderr, so the digest is the only thing on stdout. That's what lets the scheduled workflow write it straight into the GitHub run summary.

**Uptime events are worked out in Python** from whatever is in the log, so the digest works the same with either logging setting. When every check is logged, a run of hourly failures collapses into one "went down" and one "came back up." Durations are calculated in code, because language models are unreliable at date arithmetic, and empty sections are sent to Claude as "(none)" so it can tell "nothing happened" from "no data."

The digest runs on Tuesdays, so it includes Monday's reviews, that morning's flags and the latest link check. [Webhooks](webhooks.md#weekly-digest) covers how it's emailed and how its HTML is kept safe.

## Fetching pages politely

Requests identify the tool with a User-Agent that links back to this repo, so a site owner who sees Chickadee in their logs can find out what it is. Requests give up after 10 seconds, and a failed uptime check is retried only once. Audits and imports wait a second between pages, and link checks wait a second between requests to the same site.

## Limitations

- Once a webhook accepts a message, delivering it is up to the receiver. Problems after that point show up in the receiving tool's logs, not here.
- Imports match URLs exactly, so `https://example.org/page` and `https://example.org/page/` count as different pages. Compressed (`.xml.gz`) sitemaps aren't supported.
- Claude reads only the first 3,000 words of a page, so very long pages are reviewed on their opening.
- Changing the topic list doesn't retag existing pages until they change or `audit --all` runs.
- Anything that changes every time a page loads, like a timestamp, makes the page look edited and sends it for review every week. Navigation, headers and footers are stripped, but other changing sections have to be added to the extractor by hand.
- Link checks only catch links that fail outright. A link that redirects to a site's homepage, or to a "page not found" message sent with a success code, looks fine. Each page's check stops after its first 100 links.
- Pages that don't declare a modified date can't be flagged as stale until they've gone unchanged for the full staleness period after being added.
- If a page went down more than a week ago and has since recovered, the digest doesn't list it as an event. Its current status still shows how long it's been back up.
- If a page is deleted from Airtable between `audit` and `collect`, saving that batch fails.
- Every page is a record too, so very large imports can still reach the free plan's limit, whatever the logging setting.
