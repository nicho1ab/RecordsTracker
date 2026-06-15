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

On the Docker host, use this QNAP pilot setup path:

Start with the ordered readiness index in
[docs/developer/qnap-pilot-readiness-index.md](docs/developer/qnap-pilot-readiness-index.md).
Use the full operator checklist in
[docs/developer/qnap-pilot-operator-checklist.md](docs/developer/qnap-pilot-operator-checklist.md)
before inviting early testers.
Use
[docs/developer/qnap-pilot-auth-readiness.md](docs/developer/qnap-pilot-auth-readiness.md)
to capture the current production-mode auth boundary, deferred login/OIDC work,
and no-secret host-local provider settings before inviting testers.
Use
[docs/developer/qnap-pilot-tester-invitation-decision.md](docs/developer/qnap-pilot-tester-invitation-decision.md)
to record the invitation/access-control decision, tester role/scope, revocation
plan, and required evidence packet before inviting testers.
Use
[docs/developer/qnap-pilot-seeded-import-evidence.md](docs/developer/qnap-pilot-seeded-import-evidence.md)
to capture proof that validated CCLD source-derived rows are imported into
PostgreSQL before treating the pilot as tester-ready.
Use the optional local evidence packet command only after the separate verifier,
seeded evidence, route evidence, auth readiness, tester invitation, feedback,
retrieval, backup, and known-limitation decisions are understood. It assembles a
redacted Markdown packet under ignored `data/processed/qnap-pilot-evidence/` for
operator review; generated packets must not be committed.

1. Copy `.env.example` to `.env` and keep `.env` untracked.
2. Replace the PostgreSQL password placeholder.
3. Keep `CCLD_HOSTED_PAGE_DATA_MODE=postgres`.
4. Keep `CCLD_HOSTED_TESTER_AUTH_MODE=production` and
	`CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled`.
5. Keep `CCLD_RETRIEVAL_DEMO_MODE=` blank for QNAP pilot mode.
6. Keep `CCLD_RETRIEVAL_ENABLED=disabled` until live retrieval is intentionally
	configured, or set it to `enabled` only with persistent raw artifact storage.
7. Leave both `GITHUB_FEEDBACK_REPO` and `GITHUB_FEEDBACK_TOKEN` blank to disable
	GitHub feedback, or configure both values server-side to enable it.
8. Run the verifier:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env
```

The pilot check validates the required untracked environment shape, PostgreSQL
page-data mode, production auth boundary defaults, retrieval raw artifact path,
GitHub feedback configuration state, and Docker Compose configuration before
containers are started. It warns about placeholder values that must be replaced
before inviting testers.
Record `/auth/status` output only as a safe capability summary; do not treat it
as real login/session evidence, and do not capture provider secrets or callback
URLs in readiness notes.

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

After importing a validated CCLD hosted artifact or seeded corpus, capture
validated import batch counts, source-derived row counts, safe traceability
linkage counts, route results, feedback configuration decision, retrieval
configuration decision, and backup acknowledgements using the seeded import
evidence guide.

Optional read-only evidence summary command:

```powershell
.\scripts\summarize-qnap-pilot-seeded-import-evidence.ps1 -EnvFile .env
```

The command does not run imports, retrieval, live CCLD calls, GitHub calls, or
print secrets, raw artifact contents, raw server-specific paths, or legal/source-
completeness conclusions.

After containers are running, verify the pilot workflow:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -CheckContainers -BaseUrl http://<host-name-or-ip>:<CCLD_HOSTED_PORT>
```

Optional GET-only route evidence summary after the app is running:

```powershell
.\scripts\summarize-qnap-pilot-route-evidence.ps1 -BaseUrl http://<host-name-or-ip>:<CCLD_HOSTED_PORT>
```

The route evidence command accepts expected protected, setup-required, safe-empty,
and missing-job states. It does not run imports, retrieval, feedback submission,
live CCLD calls, GitHub calls, or reviewer-created writes, and it must not print
secrets, raw artifacts, raw server paths, cookies, provider subjects, provider
issuers, or response bodies.

The route probe checks the landing page, health, auth status, feedback, CCLD
facility/request/retrieval/history/help surfaces, and reviewer route status
without making live CCLD or GitHub calls. Protected routes may return setup or
sign-in-required states until production auth and imported data are configured.

Optional local redacted evidence packet assembly:

```powershell
.\scripts\build-qnap-pilot-evidence-packet.ps1 -EnvFile .env -BaseUrl http://<host-name-or-ip>:<CCLD_HOSTED_PORT> -KnownLimitationsAcknowledged
```

For placeholder/template validation without Docker/PostgreSQL checks or a
running server:

```powershell
.\scripts\build-qnap-pilot-evidence-packet.ps1 -EnvFile .env.example -SkipDatabaseCheck -AllowRouteUnavailable -BaseUrl http://127.0.0.1:9
```

The packet command is read-only and local. It runs the existing verifier, seeded
evidence, and route evidence scripts, redacts captured output defensively, and
writes Markdown under ignored `data/processed/qnap-pilot-evidence/`. It does not
run imports, retrieval, feedback submission, live CCLD calls, GitHub calls, POST
requests, product exports, audit exports, public reports, or certifications.
Operators must review generated packets before sharing them.

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

## Controlled CCLD retrieval jobs

ADR-0016 controlled browser-triggered, server-executed CCLD retrieval now has a
first implementation slice for complaint records. Operators must
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

Use `/ccld/retrieval/jobs` for a small browser-visible history/status view over
existing retrieval job metadata. It shows recent job request context, state,
timestamps, imported-record counts, safe warnings/errors, status messages, and
review links when records were imported. It is not an audit export, CSV export,
scheduler, worker console, or source-completeness report. If the history page is
empty, confirm retrieval is configured and that jobs were submitted in the same
authorized scope.

Use `/ccld/retrieval/jobs/detail?job_id=<job-id>` from a history-row detail link
when a tester or operator needs one-job context. The detail page repeats safe
request context, state, created/updated/completed timing, imported counts,
warnings/errors, raw-artifact-preserved status, and next-step links without
showing raw artifact contents, raw server paths, stack traces, or private values.

For local scaffold validation only, developers can set
`CCLD_RETRIEVAL_DEMO_MODE=mock-success` together with explicit local-dev auth,
`CCLD_RETRIEVAL_ENABLED=enabled`, and `CCLD_RETRIEVAL_RAW_DIR` to run a
fixture-backed successful retrieval from the browser. This mode uses committed
fixtures, does not make live CCLD calls, does not call GitHub, and must not be
enabled in production or QNAP/pilot-like runtime. It proves the local-dev
successful job/import/history/detail/queue path only; it does not prove public-
source completeness.

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
