# Runbook

## Validate changes

Run the full local validation set before completing a task:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```

For changes to Datasette views, generated metadata, saved queries, CSV exports,
review bundle files, or script output, also review the local output checklist in
`docs/developer/accessibility.md`.

For changes to Docker runtime files, validate the static Docker/env tests and,
when Docker is available, run a bounded Compose configuration check against the
no-secret example environment before relying on the runtime.

## Run QNAP-first Docker runtime

The first production-like runtime target is QNAP Docker with PostgreSQL in
Docker. The configuration remains portable and must not hard-code QNAP paths in
application code.

On the Docker host, copy `.env.example` to `.env`, replace placeholder values,
and run:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env up --build -d
```

Check the health route:

```text
http://<host-name-or-ip>:<CCLD_HOSTED_PORT>/health
```

Run migrations manually when needed:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env run --rm app alembic upgrade head
```

Back up PostgreSQL with `pg_dump` from the `postgres` service and store dumps
outside the repository. Restore only into a maintenance window or stopped app
container so application writes cannot race with restore. Detailed QNAP volume,
backup, restore, and portability guidance lives in
[docs/developer/qnap-docker-runtime.md](docs/developer/qnap-docker-runtime.md).
For a later move to AWS, Azure, DigitalOcean, Render, Fly.io, Railway,
Supabase/Neon, or another host, use
[docs/developer/cloud-portability-deployment.md](docs/developer/cloud-portability-deployment.md)
to keep app runtime, PostgreSQL, raw files, secrets, backups, and future retrieval
jobs separated.

## Future controlled CCLD retrieval jobs

ADR-0016 approves controlled browser-triggered, server-executed CCLD retrieval
jobs, but this branch does not implement them. When implemented, operators must
verify before enabling the workflow that production mode requires authenticated
tester access, retrieval trigger permission and scope checks are enforced,
server-side CCLD source allowlists are configured, date range and request limits
are conservative, rate limits, timeout limits, and retry limits are active, raw
source artifact storage is mounted and backed up, PostgreSQL migrations have
run, and logs/status output are secret-safe.

During operation, treat job states such as queued, running, completed,
completed_with_warnings, failed, blocked_by_validation, and rate_limited as
workflow states only. They are not public-source completeness, legal, harm,
abuse, neglect, liability, or facility-wide conclusions. For failed jobs, check
safe job status first, then operator logs. Do not expose raw stack traces,
tokens, cookies, private headers, connection strings, provider claims, GitHub
tokens, private URLs, or unnecessary narrative content in support notes.

Backups for retrieval-enabled deployments must cover both PostgreSQL and raw
source artifacts. A database backup alone is not enough when source-derived rows
reference raw artifact paths or raw hashes.

## Run fixture-backed sample ingestion

Use committed fixtures to populate the local sample database without making live
web requests:

```powershell
.\scripts\run-ccld-sample.ps1
```

The script prints the SQLite database path, generated Datasette metadata path,
the Datasette command to open, and grouped next steps for what to open first,
delay triage, source verification, and CSV export.

## Run controlled live fetch

Live fetch is explicitly user-invoked and must be scoped to provided facility
numbers. Use conservative limits while testing:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098 -Limit 5 -MaxRequests 10
```

The command prints a live fetch summary with facilities requested, report
candidates discovered, selected, skipped by limit, fetched, written, and failed.
It also prints facility identifier intake feedback before discovery, including
accepted identifiers, duplicate identifiers ignored, and ignored blank, comment,
or header values. The facility summary also labels per-facility run states such
as records written, no records discovered, skipped by limit, and partial report
failures. Check these summaries before opening logs when a run produces fewer
records than expected. After the summary, the command prints grouped next steps
for opening Datasette review paths, delay triage, source verification, and CSV
export.

## Run multi-facility live fetch

Provide multiple explicit facility numbers when you need a multi-facility local
review database:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098,157806097 -Limit 5 -MaxRequests 20
```

This workflow does not perform statewide crawling or automatic search expansion.
The printed facility summary is the first place to check for partial discovery,
no-record, skipped-by-limit, fetch, extraction, validation, or write outcomes
across multiple facilities.

## Browse with Datasette

Prefer the Datasette command printed by the sample or live fetch script because
it includes the generated metadata file.

Manual command:

```powershell
.\.venv\Scripts\datasette.exe data\processed\ccld.sqlite --metadata data\processed\ccld.datasette-metadata.json
```

Open the local URL shown in PowerShell and start with these saved queries and
views:

1. Saved query `review_home`
2. Saved query `complaint_review_start_here`
3. `complaint_first_pass_review`
4. `complaint_review_summary`
5. `facility_complaint_summary`
6. `delay_review_flags`
7. `source_traceability_review`

The `review_home` saved query groups the local review paths by task: review
complaints, find records needing closer review, compare facilities, verify
sources, and export CSVs.

The sample and live fetch scripts also print grouped next steps: open first,
delay triage, source verification, CSV export, and other useful review paths.
Use those groups as the first navigation guide after each run.

If saved queries are unavailable, start with these views:

1. `complaint_first_pass_review`
2. `complaint_review_summary`
3. `facility_complaint_summary`
4. `delay_review_flags`
5. `source_traceability_review`

## Export review bundle

After populating the database, export standard source-traceable CSV review outputs:

```powershell
.\scripts\export-review-bundle.ps1
```

For a custom database or output folder:

```powershell
.\scripts\export-review-bundle.ps1 -DbPath data\processed\live-ccld.sqlite -OutputDir data\processed\live-review-bundle
```

The bundle includes complaint review, delay triage, and source traceability CSVs plus a README with caution language. Delay review flags are screening aids only; verify important details against source documents.

## Add a fixture

1. Save raw source content under `tests/fixtures/<source>/raw/`.
2. Add expected output under `tests/fixtures/<source>/expected/`.
3. Verify the raw fixture uses the line endings required by `.gitattributes`.
4. If expected output includes `raw_sha256`, compute it from the Git-normalized
	fixture bytes that CI will read, not from a platform-specific working-tree
	copy.
5. Run tests.
6. Commit raw fixture and expected JSON together.

## Recover from failed extraction

1. Check `data/raw/` for the source file.
2. Check logs under `data/logs/`.
3. Run the extractor against the raw file only.
4. Add or update a fixture reproducing the failure.
5. Fix the smallest amount of extraction logic needed.
6. Review the root cause for a missing or unclear governance rule. Add or update
	governance, testing, fixture, connector, or workflow documentation when a new
	rule would prevent recurrence.
7. Run full regression tests and documentation checks.

## Recover from a CI failure

1. Identify the exact workflow step and command that failed.
2. Run the same command locally when it does not require secrets or live external
	requests.
3. If local results differ from CI, check cross-platform behavior such as line
	endings, path separators, locale-sensitive output, and Git-normalized fixture
	bytes.
4. If the failure involved expected raw hashes, verify fixture line endings with:

```powershell
git ls-files --eol tests\fixtures\ccld\raw\<fixture-name>.html
```

5. Fix the smallest root cause, rerun the exact failing command, then run the
	standard validation set.
6. Add or update a governance rule if the root cause exposed a missing rule.

## PR and merge cleanup

Before opening a PR, include the validation results, a concise PR title, and a PR
body that states whether user-facing or documentation-impacting behavior changed.

The repository `main` branch must be protected by a GitHub branch protection rule or repository ruleset.
The rule must require pull requests and must require these status-check contexts
to pass before squash merge:

- `validate`
- `docs-check`
- `fixtures`
- `security`

If GitHub allows a PR to merge before those required checks pass, treat that as a
repository governance configuration issue. Fix the branch protection rule or
ruleset before the next merge.

When GitHub CLI is installed and authenticated, prefer `gh` for repeatable PR
steps. Keep token values and authentication details out of docs, handoffs, logs,
and commits.

Verify `gh` is available in the VS Code terminal before relying on automation:

```powershell
gh --version
```

```powershell
gh auth status
```

Check the active PR state:

```powershell
gh pr view --json number,state,isDraft,mergeStateStatus,baseRefName,headRefName,url,statusCheckRollup
```

Check required checks with a non-interactive snapshot:

```powershell
gh pr view --json number,state,isDraft,mergeStateStatus,baseRefName,headRefName,url,statusCheckRollup
```

The checks output must include passing `validate`, `docs-check`, `fixtures`, and
`security` contexts before merge. Do not rely only on local validation when
deciding whether the PR is merge-ready. Avoid watch commands in the VS Code
terminal; refresh with another JSON snapshot instead.

Squash merge after required checks pass and no conflicts remain:

```powershell
gh pr merge --squash --delete-branch
```

If repository auto-merge is enabled, prefer setting auto-merge after required
checks have started:

```powershell
gh pr merge --squash --auto --delete-branch
```

After the PR merges, clean up the local branch:

```powershell
git switch main
git pull --ff-only
git branch --delete <merged-branch-name>
git remote prune origin
```

Start follow-up work from an updated `main` branch:

```powershell
git switch main
git pull --ff-only
git switch -c <next-branch-name>
```
