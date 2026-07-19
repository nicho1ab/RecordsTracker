# Issue #490 Workstream A Codex prompt — technical source profiling

## Dispatch instructions

Use this prompt only after the Issue #490 planning package has merged to `main`.
Before dispatch, replace every `{{...}}` value. Do not dispatch with a placeholder.
Recommended Codex effort: `xhigh`.

---

Task name: Issue #490 Workstream A — technical statewide facility source profile

Repository: RecordsTracker

Base branch: `main`

Verified base SHA: `{{ISSUE_490_PLANNING_MERGE_SHA}}`

Granted capabilities:

- `RO` for read-only inspection of the exact public-source and GitHub URLs in
  the network allowlist below.
- `II` for isolated implementation and validation only in the assigned
  worktree and owned files below.

Continuous execution is authorized only for this phase sequence:

1. Read-only preflight and governed source discovery.
2. Controlled public snapshot retrieval into existing ignored local paths.
3. Isolated profiler, fixture, output-contract, and test implementation.
4. Focused local validation and handoff.

Do not stop between those phases unless a stop condition below is met. Stop
after the II handoff. `RL-PREPARE`, `RL-MERGE`, `HV-READ`, `HV-WORKFLOW`, and HQ
are not granted.

Exact branch: `issue-490-technical-source-profile`

Exact worktree: `<repo-parent>\CCLD-complaints-poc-issue-490-profile`

The dispatcher must substitute the same local repository parent used for the
other RecordsTracker worktrees without adding that personal path to tracked
content.

Allowed network access is unauthenticated read-only `GET`/metadata access to:

- `https://github.com/nicho1ab/RecordsTracker/issues/490` and its comments.
- `https://data.chhs.ca.gov/dataset/ccl-facilities`.
- `{{APPROVED_CATALOG_RESOURCE_ENDPOINTS}}`.
- `{{APPROVED_ARCGIS_ENDPOINTS}}`.

Each replacement must be an explicit newline-separated URL list. Do not use a
wildcard, arbitrary redirect target, search engine, unrelated site, or link not
in the dispatched allowlist. Redirects outside the allowlist are a stop
condition.

Browser/computer-use allowlist: none. Do not use browser or computer-use tools.

## Goal

Implement the isolated, reproducible technical evaluation required by Issue
#490. Discover and preserve controlled public evidence for the statewide
ArcGIS-backed CCLD facility dataset; profile its schema, records, identifiers,
facility attributes, pagination, downloads, and change behavior; compare it with
the existing program-specific facility sources; and emit deterministic
machine-readable results plus a technical report.

This work evaluates a candidate. It does not approve or activate it.

## Required context before editing

Read from the assigned worktree:

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `PROJECT_CHARTER.md`
- `ARCHITECTURE.md`
- `DATA_CONTRACT.md`
- `SOURCE_CONNECTOR_CONTRACT.md`
- `PUBLIC_SOURCE_DATA_INVENTORY.md`
- `GOVERNANCE_INVENTORY.md`
- `SECURITY_AND_PRIVACY.md`
- `TESTING_STRATEGY.md`
- `KNOWN_LIMITATIONS.md`
- `ROADMAP.md`
- `docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md`
- `docs/planning/issue-490-statewide-facility-source-evaluation-plan.md`
- `docs/planning/issue-490-parallel-work-ownership.md`

Read Issue #490 and its comments from the allowlisted GitHub URL. Do not inspect
or modify a different worktree.

## Preflight

Before any network retrieval or write:

1. Confirm the current worktree path and branch are exact.
2. Confirm `HEAD`, local `main`, and `origin/main` all equal
   `{{ISSUE_490_PLANNING_MERGE_SHA}}`.
3. Confirm the assigned worktree is clean.
4. Inspect branches, worktrees, unpushed commits, active ownership, and possible
   file overlap.
5. Confirm Workstream B does not have write authority over any Workstream A path.
6. Confirm every network placeholder has been replaced by exact URLs.
7. Confirm the raw, processed, and log output locations below are ignored before
   writing any source artifact.

Stop and report any mismatch. Do not create a different branch or worktree and
do not change global Git configuration.

## Exclusive tracked-file ownership

You may create or edit only:

- `src/ccld_complaints/source_profiling.py`
- `src/ccld_complaints/statewide_facility_source_evaluation.py`
- `scripts/profile_statewide_facility_source.py`
- `schemas/issue-490-statewide-facility-source-profile.schema.json`
- `tests/unit/test_source_profiling.py`
- `tests/unit/test_statewide_facility_source_evaluation.py`
- `tests/fixtures/source_profiling/issue_490/**`
- `docs/analysis/issue-490-technical-source-profile.md`

Use the smallest subset needed. Prefer a new isolated evaluation module over
expanding production behavior in an existing module. The schema path is for the
evaluation output only; do not modify canonical schemas.

You may write generated local artifacts only to these existing ignored paths:

- `data/raw/source-profiling/issue-490/**`
- `data/processed/source-profiling/issue-490/**`
- `data/logs/issue-490-source-profiling/**`

Do not track those generated artifacts. If a path is not ignored, stop; do not
edit `.gitignore` unless a new task assigns it.

## Prohibited files and actions

Do not edit:

- `docs/analysis/issue-490-governance-source-qualification.md`
- `docs/analysis/issue-490-governance-recommendation.md`
- Any `docs/planning/issue-490-*.md` file
- `CHANGELOG.md`
- `ROADMAP.md`
- `PUBLIC_SOURCE_DATA_INVENTORY.md`
- `GOVERNANCE_INVENTORY.md`
- Any final Issue #490 completion report
- Any shared index or decision-summary file
- Hosted application, reviewer UI, operator UI, canonical schema, migration,
  database initialization, import, backfill, schedule, QNAP, deployment, or
  Cloudflare files

Do not:

- Implement or activate a production connector, source replacement, importer,
  canonical bridge, backfill, renderer mapping, or scheduled refresh.
- Add a page-local or application-wide `733` dictionary.
- Modify SQLite or PostgreSQL data.
- Commit a statewide source snapshot or generated profiling output.
- Use browser/computer-use, SSH, QNAP, Docker, Compose, database, deployment,
  rollback, restore, or Cloudflare operations.
- Access any URL outside the exact allowlist, authenticate, accept new terms on
  behalf of the user, bypass a control, or stress/load test a public source.
- Read or expose secrets, tokens, cookies, private headers, `.env` values,
  private URLs, private host details, personal paths, or unnecessary narrative.
- Commit, stage, push, create/update/monitor a PR, merge, clean up, close Issue
  #490, or begin #482, #453, #477, #478, or another roadmap task.

## Technical implementation requirements

Implement an evaluation-only path that follows and tests this sequence without
adding a production connector:

`discover -> fetch -> store raw -> extract -> normalize -> validate -> emit`

### Discovery and endpoint identity

- Record the exact catalog, dataset, resource/download, ArcGIS item, service,
  layer, metadata, and query endpoints.
- Record public identifiers, titles, publisher labels, service/layer versions,
  capabilities, fields, domains, object-ID field, maximum record count,
  supported formats, and pagination/order support.
- Never infer a service URL or follow an endpoint outside the allowlist.

### Controlled snapshots and preservation

- Preserve original download bytes and original JSON response bytes before
  parsing.
- Preserve service and layer metadata plus every page needed to reconstruct the
  evaluated query.
- Record UTC retrieval time, exact request URL and safe parameters, status,
  content type, byte count, SHA-256, source version metadata, warnings, and a
  repository-relative artifact reference.
- Never overwrite a prior snapshot. Repeated retrieval must create a new
  manifest or prove identical content through the hash.
- Hash original bytes and a documented canonical row representation separately.

### Schema and record profiling

Profile at least:

- Raw and parsed row/column counts, encoding, field order, field types, domains,
  geometry behavior, null markers, date formats, and parser warnings.
- Facility/license number, missing identifiers, duplicate identifiers, object
  IDs, and row cardinality per facility.
- Facility type raw codes, descriptive labels, program types, and unresolved
  code/label relationships.
- Status, name, address, city, state, ZIP, county, geography, latitude/longitude,
  capacity, licensee/operator, administrator, telephone, first-license date,
  closed date, and source/snapshot dates where present.
- Per-field populated, blank, null, invalid, distinct-value, and normalization-
  warning counts.
- Active, inactive, closed, and other observed status values without treating a
  missing or disappearing row as closure.
- Same-source duplicates and cross-source conflicting nonblank values.

Keep original values. Evaluation-only normalization must be explicit,
deterministic, and non-canonical. Distinguish blank, absent, invalid,
unavailable, and conflicting states.

### ArcGIS pagination and equivalence

- Exercise the documented maximum page size, a smaller page size, stable order
  where supported, object-ID batching where supported, and the terminal short or
  empty page.
- Detect result caps, duplicate pages, duplicate records, gaps, unstable order,
  changed schemas, malformed responses, rate limits, and timeouts.
- Prove no duplicate or omitted row across page boundaries.
- Compare a stable full download with a complete paginated service query using
  facility identifiers and canonical row fingerprints. A matching row count
  alone is insufficient.
- Record additions, omissions, duplicates, field differences, schema
  differences, and a finite equivalence verdict.
- Compare repeated retrievals and separate catalog metadata change, byte change,
  schema change, row-set change, and field-value change.
- Observe limits safely. Use bounded requests; do not load test or bypass
  throttling.

### Existing source comparison

Compare the statewide candidate with controlled evidence for the existing
program-specific facility sources:

- Source/resource/snapshot identity, schema, and counts.
- Facility-number set intersection and one-side-only rows.
- Duplicate and missing identifiers.
- Type codes, labels, program types, and unresolved mappings.
- Status and inactive/closed representation.
- Name, address, geography, capacity, licensee/operator, and identity-field
  coverage.
- Differing nonblank values with source/time context.
- Scope differences that explain apparent omissions.

Do not treat existing PostgreSQL rows as the public source of truth.

### Code 733

Treat `733` as unexplained until verified. Inventory every exact source field,
record/domain/metadata context, observed descriptive label, record count, and
cross-source occurrence. Accept a mapping only when official source evidence
shows a stable, unique relationship. Otherwise emit an unresolved or conflicting
status. Do not write application mapping logic.

## Required fixtures and mocks

Automated tests must make zero live network calls.

Create only small, safe, documented, synthetic or minimized fixtures covering:

- Catalog/item/service/layer metadata.
- Full-download shape.
- Multiple pages and a terminal page.
- Field domains and code/label relationships.
- Duplicate and missing facility identifiers.
- Blank, null, invalid, inactive/closed, and conflicting values.
- Schema drift and changed field domain.
- Result caps, duplicate/missing pages, timeout, rate-limit, malformed response,
  redirect, and unsupported format behavior.
- Matching counts with one omitted or changed row so equivalence correctly fails.

Expected hashes must use Git-normalized bytes. Fixtures must not contain secrets,
private values, unnecessary person-level content, or enough real source data to
become a statewide data dump.

## Required generated outputs

Emit deterministic, schema-validated files under the ignored processed path:

- `source-endpoints.json`
- `snapshot-manifest.json`
- `schema-profile.json`
- `pagination-equivalence.json`
- `facility-profile.json`
- `facility-type-code-label.csv`
- `coverage-comparison.csv`
- `source-conflicts.csv`
- `content-change.json`
- `validation-summary.json`

Use UTC timestamps, stable row ordering, finite status values, relative artifact
references, and a versioned output contract. Do not include raw statewide rows
when aggregate counts, bounded conflict categories, identifiers, or fingerprints
are sufficient.

Create `docs/analysis/issue-490-technical-source-profile.md` with:

- Exact endpoint and snapshot identities.
- Reproducible commands using placeholders, not personal paths.
- Technical method and output contract version.
- Hash, schema, pagination, equivalence, change, coverage, facility type, `733`,
  and warning findings.
- Comparison with existing program-specific sources.
- Tests and validation results.
- Explicit pass/fail/blocked/inconclusive findings and unresolved technical
  questions.
- A statement that the report does not approve adoption, production import,
  backfill, UI, scheduling, deployment, or QNAP changes.

Do not write the governance recommendation.

## Required automated tests

Add focused tests proving:

- Raw bytes are stored before parsing and hashes match stored bytes.
- Endpoint and metadata parsing is deterministic.
- Schema fingerprints and output ordering are deterministic.
- Pagination covers all records exactly once and terminates safely.
- Query/download equivalence checks identifiers and row fingerprints, not only
  counts.
- Omission, duplication, value change, and schema mismatch fail equivalence.
- Code/label inventory preserves raw codes and does not assume `733`.
- Cross-source comparison distinguishes blank, absent, invalid, unavailable,
  conflict, and scope difference.
- Repeated runs produce equivalent content except documented retrieval metadata.
- Output files validate against the evaluation contract.
- All tests use fixtures/mocks and fail on an unexpected live call.
- Output contains no secret-like values, private URLs, absolute/personal paths,
  raw exception dumps, or unnecessary narrative.

## Validation

Run the smallest checks that prove this work. At minimum:

1. The new Workstream A regression/test module independently.
2. `tests/unit/test_source_profiling.py` and the new module together.
3. Targeted Ruff for changed Python files.
4. Targeted mypy for changed Python modules/scripts where supported by the
   repository configuration.
5. `.\scripts\docs.ps1`.
6. Affected documentation-check unit tests only if documentation checks require
   them.
7. `git diff --check`.
8. A changed/untracked-file audit proving all tracked changes are Workstream A
   owned and all source/generated artifacts are ignored.
9. A scan proving no Workstream B or reserved integration file changed.

Do not run the complete test suite unless a focused or CI-equivalent failure
demonstrates that broader local validation is necessary. Do not use live network
access in automated tests.

## Stop conditions

Stop before further access or editing and report if:

- The branch, worktree, base SHA, clean state, ownership, or dispatch placeholder
  is wrong.
- A required endpoint or redirect is outside the exact network allowlist.
- Source access requires authentication, credentials, new terms acceptance,
  CAPTCHA bypass, or non-public data.
- An ignored output path is not ignored or source/generated data would become
  tracked.
- Required work crosses the exclusive file list or needs a reserved file.
- The service cannot be profiled safely within bounded rate/timeout limits.
- Code `733` cannot be verified; report it unresolved rather than guessing.
- A production connector, importer, schema, migration, backfill, app/UI,
  scheduler, deployment, QNAP, or downstream issue change would be required.
- Technical findings conflict in a way that requires a governance decision.

An unavailable or failing source is a valid measured result. Do not substitute
an unapproved source or expand scope.

## Final handoff

Stop after implementation and focused local validation. Report:

1. Verified base SHA, branch, worktree template, capabilities used, and exact
   endpoint allowlist.
2. Exact tracked files changed and ignored artifacts created.
3. Snapshot/output manifest paths, contract version, hashes, and safe statuses.
4. Summary of endpoint, schema, count, pagination, equivalence, change,
   comparison, facility type, and `733` findings.
5. Validation commands and pass/fail results, including intentionally unrun
   checks.
6. Documentation and security/privacy impact.
7. Unresolved evidence and exact stop conditions.
8. Confirmation that Workstream B and reserved integration files were untouched.
9. Confirmation that no production source, data store, app, schema, migration,
   UI, backfill, scheduler, branch lifecycle, PR, QNAP, deployment, or external
   mutable state changed.

Do not commit, stage, push, create or update a PR, merge, clean up, close Issue
#490, or begin another issue.

---
