# Airtable schema

Chickadee uses one base with four tables. Field names are case-sensitive and need to match exactly, including select options.

## Pages

One row per page. Each command writes its own group of fields, so the table reads left to right in roughly the order things happen.

| Field | Type | Written by |
|---|---|---|
| URL | URL (primary) | You, or `import` |
| Name | Single line text | You |
| Active | Checkbox | You, or `import` |
| Status | Single select: `Up`, `Down` | `uptime` |
| Status since | Date with time | `uptime` |
| Last checked | Date with time | `uptime` |
| Last status code | Number | `uptime` |
| Last response time (ms) | Number | `uptime` |
| Alerted status | Single select: `Up`, `Down` | `uptime` |
| Current title | Single line text | `audit` |
| Current description | Long text | `audit` |
| Word count | Number | `audit` |
| Page modified at | Date with time | `audit` |
| Content hash | Single line text | `audit` |
| Content changed at | Date with time | `audit` |
| Content summary | Long text | `collect` |
| Key point | Long text | `collect` |
| Key point up front | Single select: `Yes`, `No` | `collect` |
| Topics | Link to Topics, allowing multiple | `collect` |
| SEO score | Number | `collect` |
| SEO summary | Long text | `collect` |
| Suggested title | Single line text | `collect` |
| Suggested description | Long text | `collect` |
| SEO issues | Long text | `collect` |
| Last audited | Date with time | `collect` |
| Reviewed hash | Single line text | `collect` |
| Review version | Single line text | `collect`, or `audit` for pages reviewed before versions existed |
| Broken links | Long text | `links` |
| Unverified links | Long text | `links` |
| Broken link count | Number | `links` |
| Links checked at | Date with time | `links` |
| Attention | Multiple select: `Down`, `Has broken links`, `Stale`, `Low SEO score`, `Missing metadata`, `Key point buried` | `flags` |
| Attention count | Number | `flags` |

A few notes:

- **Status, Alerted status and Key point up front are single selects, not checkboxes.** Airtable leaves unchecked checkboxes out of API responses, so an empty checkbox could mean "no" or "never checked." With a single select, empty only ever means "not checked yet."
- **Select options must already exist.** The API rejects values that aren't one of a field's options, so create them exactly as listed.
- **Last checked is a plain date, not a rollup of Checks.** When only status changes are logged, the newest row in Checks usually isn't the newest check.
- **Name is optional.** Anywhere a page is shown, its URL stands in when it has no name.

Two pairs of fields compare what's true now with what was last acted on:

- **Content hash and Reviewed hash:** the page as it is now, and as Claude last saw it. A page needs a review when they differ. See [Tracking changes](design.md#tracking-changes).
- **Status and Alerted status:** what the page is doing now, and what was last announced. An alert is due when they differ. See [Uptime](design.md#uptime).

Review version works the same way, compared against the current review setup rather than another field: a page is reviewed again when its version doesn't match. See [When the review itself changes](design.md#when-the-review-itself-changes).

Leave Reviewed hash, Review version and Alerted status empty when adding pages. Chickadee fills them in.

### Views

**Needs attention:** filter to Active is checked and Attention count is greater than 0, then sort by Attention count, highest first. It's the to-do list that `flags` keeps up to date.

## Checks

The uptime log. What goes into it depends on the `CHECK_LOG` setting: every check, or only changes in status. See [Configuration](configuration.md#storage-and-your-airtable-plan).

| Field | Type |
|---|---|
| Check ID | Autonumber (primary) |
| Page | Link to Pages |
| Checked at | Date with time |
| Status code | Number |
| Response time (ms) | Number |
| Ok | Checkbox |
| Error | Long text |

`uptime` creates the rows and `prune` deletes old ones.

## Audit batches

Review batches waiting to be collected. `audit` adds a row for each batch it submits, and `collect` checks the box once the results are saved, so running `collect` again never saves the same batch twice. Keeping this in Airtable rather than a local file means collection works the same from a scheduled job as from a laptop.

| Field | Type |
|---|---|
| Batch ID | Single line text (primary) |
| Submitted at | Date with time |
| Pages | Number |
| Collected | Checkbox |

## Topics

The topics Claude can tag pages with. You manage this table, and each audit reads it.

| Field | Type |
|---|---|
| Name | Single line text (primary) |
| Description | Long text |

Because Topics on Pages is a linked record field, each topic's row automatically lists every page tagged with it. Adding, renaming, removing or describing a topic changes the review setup, so the next audit sends every page for review again and retags it. Reordering topics doesn't. The audit's summary says when this is happening.
