# Automation

GitHub Actions runs Chickadee on a schedule, so it keeps watch without anyone's computer being on. Each command has its own workflow, schedule and timeout.

## Scheduled workflows

All times are UTC.

| Workflow | When it runs | Command |
|---|---|---|
| `monitor.yml` | Every hour at :17 | `chickadee uptime` |
| `audit.yml` | Mondays at 10:23 | `chickadee audit` |
| `collect.yml` | Every 6 hours | `chickadee collect` |
| `digest.yml` | Tuesdays at 10:47 | `chickadee digest` |
| `links.yml` | Thursdays at 09:37 | `chickadee links` |
| `prune.yml` | Daily at 04:43 | `chickadee prune` |
| `flags.yml` | Daily at 06:13 | `chickadee flags` |

Why these times:

- **Odd minutes.** Most scheduled jobs on GitHub start on the hour, and runs are delayed or occasionally dropped when it's busy. Running at :17 or :23 avoids the rush.
- **The audit runs Monday and the digest Tuesday**, so the digest includes Monday's reviews. `collect` runs every six hours, and since it's safe to run repeatedly, it doesn't need to be timed to the audit. It picks up each batch once it's ready.
- **Flags run every morning**, after the night's prune, so the "Needs attention" view is current each day.
- **The link check runs midweek**, away from the audit, since both make a lot of requests to the same sites.

Each workflow can also be run by hand from the Actions tab. Importing isn't scheduled, because it's worth reading a dry run before adding pages. The weekly digest appears on its run's summary page as well as in the email.

Every workflow has a timeout, so a stuck run can't quietly use up Actions minutes, and won't start a new run while the previous one is still going. Two overlapping `collect` runs could otherwise save the same batch twice.

## Credentials and settings

Credentials live in a GitHub environment called `production`, and only the `main` branch can use it. Secrets are only ever available to code that has been reviewed and merged, never to a branch that's still in progress.

Inside each workflow, credentials are given only to the step that needs them, and each workflow gets only what it uses:

| Workflow | Airtable | Claude key | Webhook | Settings |
|---|---|---|---|---|
| `monitor.yml` | ✓ | | Alerts | `CHECK_LOG` |
| `audit.yml` | ✓ | ✓ | | `IGNORE_SELECTORS` |
| `collect.yml` | ✓ | ✓ | | |
| `digest.yml` | ✓ | ✓ | Digest | |
| `links.yml` | ✓ | | | `IGNORE_SELECTORS` |
| `prune.yml` | ✓ | | | `RETENTION_DAYS` |
| `flags.yml` | ✓ | | | `STALE_AFTER_DAYS` |

To set it up, create the `production` environment under **Settings → Environments**, restrict it to the `main` branch, and add:

- **Secrets:** `AIRTABLE_TOKEN`, `ANTHROPIC_API_KEY`, and optionally `ALERT_WEBHOOK_URL` and `DIGEST_WEBHOOK_URL`.
- **Variables:** `AIRTABLE_BASE_ID`, and optionally `CHECK_LOG`, `RETENTION_DAYS`, `STALE_AFTER_DAYS` and `IGNORE_SELECTORS`.

Secrets are encrypted and hidden in logs. Variables are plain configuration that isn't sensitive. Settings that aren't set fall back to their defaults, and alerts and emails are skipped without their webhooks.

Use separate Airtable and Claude credentials for GitHub from the ones on your own computer. If one leaks, it can be revoked without breaking the other, and the Claude Console shows exactly what the automation costs. A spend limit on the Claude workspace puts a ceiling on what unattended code can spend.

## CI

`ci.yml` runs on every push and pull request: Ruff for linting and formatting, Pyright for type checking, and the tests. It runs every check even if an earlier one fails, so one run shows everything that's wrong. It has no access to any credentials, which matters because pull requests can contain code nobody has reviewed yet.

`uv sync --locked` installs exactly what's in `uv.lock`, and fails if the lockfile is out of date with `pyproject.toml`. That catches a dependency added without its lockfile.

Dependabot opens pull requests when GitHub Actions or Python dependencies have new versions, and CI checks each one before it's merged.

## Things to know about scheduled runs

- GitHub doesn't guarantee exact start times, and runs can be delayed when it's busy.
- On public repos, scheduled workflows pause after 60 days without any repository activity. If Chickadee goes quiet months from now, check whether it was paused.
- GitHub emails the repo owner when a scheduled run fails, which is how failed alerts and failed digest emails get noticed.
- Every run that uses the `production` environment counts as a deployment. Deployments can be hidden from the repo's front page in the About settings, but they still fill the environment's history.
- Public repos run on GitHub's standard runners for free. Private repos get a monthly allowance, and the hourly uptime check uses the most of it.
