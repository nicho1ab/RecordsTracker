# Issue #490 Workstream B Codex prompt — governance and source qualification

## Dispatch instructions

Use this prompt only after the Issue #490 planning package has merged to `main`.
Before dispatch, replace every `{{...}}` value. Do not dispatch with a placeholder.
Recommended Codex effort: `high`.

---

Task name: Issue #490 Workstream B — governance and statewide source qualification

Repository: RecordsTracker

Base branch: `main`

Verified base SHA: `{{ISSUE_490_PLANNING_MERGE_SHA}}`

Granted capabilities:

- `RO` for read-only inspection of the exact public-source and GitHub URLs in
  the network allowlist below.
- `II` for isolated documentation implementation and validation only in the
  assigned worktree and owned files below.

Continuous execution is authorized only for this phase sequence:

1. Read-only preflight and official public-source qualification research.
2. Isolated governance analysis and recommendation documentation.
3. Focused local documentation validation and handoff.

Do not stop between those phases unless a stop condition below is met. Stop
after the II handoff. `RL-PREPARE`, `RL-MERGE`, `HV-READ`, `HV-WORKFLOW`, and HQ
are not granted.

Exact branch: `issue-490-governance-source-qualification`

Exact worktree: `<repo-parent>\CCLD-complaints-poc-issue-490-governance`

The dispatcher must substitute the same local repository parent used for the
other RecordsTracker worktrees without adding that personal path to tracked
content.

Allowed network access is unauthenticated read-only `GET`/metadata access to:

- `https://github.com/nicho1ab/RecordsTracker/issues/490` and its comments.
- `https://github.com/nicho1ab/RecordsTracker/issues/482` and its comments.
- `https://github.com/nicho1ab/RecordsTracker/issues/453` and its comments.
- `https://github.com/nicho1ab/RecordsTracker/issues/477` and its comments.
- `https://github.com/nicho1ab/RecordsTracker/issues/478` and its comments.
- `https://data.chhs.ca.gov/dataset/ccl-facilities`.
- `{{APPROVED_PUBLISHER_TERMS_LICENSE_ENDPOINTS}}`.
- `{{APPROVED_CATALOG_RESOURCE_ENDPOINTS}}`.
- `{{APPROVED_ARCGIS_METADATA_ENDPOINTS}}`.

Each replacement must be an explicit newline-separated URL list. Do not use a
wildcard, arbitrary redirect target, search engine, unrelated site, or link not
in the dispatched allowlist. Redirects outside the allowlist are a stop
condition.

Browser/computer-use allowlist: none. Do not use browser or computer-use tools.

## Goal

Qualify the statewide ArcGIS-backed CCLD facility dataset as a governed public
source candidate. Establish publisher and represented system-of-record evidence,
terms/license/attribution and public-use constraints, authority and scope
limitations, precedence and conflict options, current-versus-historical identity
rules, freshness and change-detection requirements, and a cautious human-readable
adopt, supplement, reject, or inconclusive recommendation.

This work does not activate a source or approve implementation.

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

Read Issues #490, #482, #453, #477, and #478 plus their comments from the
allowlisted GitHub URLs. Do not inspect or modify a different worktree.

If available, read but do not edit these Workstream A evidence inputs:

- `docs/analysis/issue-490-technical-source-profile.md`
- The exact Workstream A `snapshot-manifest.json` and
  `validation-summary.json` paths and hashes supplied in its handoff.
- Other machine-readable outputs only through the versioned manifest supplied by
  Workstream A.

Record the exact A commit, output-contract version, manifest path/hash, and
validation status consumed. If the evidence is absent or fails validation, the
recommendation must remain conditional or `inconclusive pending technical
evidence`.

## Preflight

Before any network access or write:

1. Confirm the current worktree path and branch are exact.
2. Confirm `HEAD`, local `main`, and `origin/main` all equal
   `{{ISSUE_490_PLANNING_MERGE_SHA}}`.
3. Confirm the assigned worktree is clean.
4. Inspect branches, worktrees, unpushed commits, active ownership, and possible
   file overlap.
5. Confirm Workstream A does not have write authority over either Workstream B
   document.
6. Confirm every network placeholder has been replaced by exact URLs.
7. Confirm no private source, credentials, account session, or terms acceptance
   is needed.

Stop and report any mismatch. Do not create a different branch or worktree and
do not change global Git configuration.

## Exclusive tracked-file ownership

You may create or edit only:

- `docs/analysis/issue-490-governance-source-qualification.md`
- `docs/analysis/issue-490-governance-recommendation.md`

Do not add a documentation index or validation test unless the current
documentation check fails solely because these files require one. Such a change
would cross ownership: stop and return it as an integration dependency rather
than editing the extra file.

## Prohibited files and actions

Do not edit:

- `src/ccld_complaints/source_profiling.py`
- `src/ccld_complaints/statewide_facility_source_evaluation.py`
- `scripts/profile_statewide_facility_source.py`
- `schemas/issue-490-statewide-facility-source-profile.schema.json`
- `tests/unit/test_source_profiling.py`
- `tests/unit/test_statewide_facility_source_evaluation.py`
- `tests/fixtures/source_profiling/issue_490/**`
- `docs/analysis/issue-490-technical-source-profile.md`
- Any raw or generated Workstream A profiling output
- Any `docs/planning/issue-490-*.md` file
- `CHANGELOG.md`
- `ROADMAP.md`
- `PUBLIC_SOURCE_DATA_INVENTORY.md`
- `GOVERNANCE_INVENTORY.md`
- Any final Issue #490 completion report
- Any shared index or decision-summary file
- Application code, tests, fixtures, schemas, migrations, database
  initialization, generated profiling output, reviewer UI, operator UI, QNAP,
  deployment, backfill, or scheduled-refresh files

Do not:

- Implement or activate a connector, downloader, profiler, importer, source
  replacement, canonical bridge, backfill, renderer mapping, operator workflow,
  or scheduled refresh.
- Add a page-local or application-wide `733` dictionary.
- Modify SQLite or PostgreSQL data.
- Use browser/computer-use, SSH, QNAP, Docker, Compose, database, deployment,
  rollback, restore, or Cloudflare operations.
- Access any URL outside the exact allowlist, authenticate, accept new terms on
  behalf of the user, bypass a control, or use unofficial secondary commentary
  as proof of publisher authority or permitted use.
- Read or expose secrets, tokens, cookies, private headers, `.env` values,
  private URLs, private host details, personal paths, or unnecessary narrative.
- Provide legal advice or claim a source is complete, authoritative, current,
  official for every purpose, or error-free beyond the exact source evidence.
- Commit, stage, push, create/update/monitor a PR, merge, clean up, close Issue
  #490, or begin #482, #453, #477, #478, or another roadmap task.

## Evidence standard

Use primary official public evidence whenever available. For every material
claim record:

- Exact public URL.
- Page/item/service title or identifier.
- Publishing body shown by the source.
- UTC access date/time or access date when time is not captured.
- The specific metadata field, terms section, license statement, attribution
  statement, or service relationship supporting the finding.
- Whether the evidence is direct, linked, inferred, conflicting, unavailable, or
  requires human confirmation.
- Any scope, date, or reliability limitation.

Paraphrase rather than copying long source passages. Do not reproduce terms or
licenses in full. If terms, license, attribution, ownership, or system-of-record
status are ambiguous, say so and identify the exact human/legal/governance review
needed. Do not convert absence of a restriction into permission.

Catalog modification timestamps, access timestamps, content hashes, schema
versions, and actual row-level change are separate concepts. Do not call a source
fresh because a catalog page was recently modified.

## Source qualification requirements

### Publishing agency and system representation

Determine and document:

- The publisher, owner, maintainer, and agency labels shown on the catalog,
  ArcGIS item, service, layer, and downloadable resource.
- The relationship among CHHS/CDSS, CCLD, the catalog host, ArcGIS account, and
  the represented operational system, using only evidence the source supplies.
- Whether any surface republishes, aggregates, transforms, or lags another.
- Dataset, item, service, layer, and resource identifiers and their relationships.
- Any direct statement of statewide scope, update responsibility, data steward,
  source of record, authoritative use, or limitation.
- Conflicts or missing links among publisher/owner labels.

Do not use the repository's current `authoritative` wording as proof. That
language is an integration issue because Issue #490 treats the candidate as
unprofiled and not approved.

### Terms, license, attribution, and access

Record:

- Terms-of-use URL and applicable service/catalog terms.
- License name or explicit absence/ambiguity.
- Required attribution and whether it applies to data, service, maps, or derived
  outputs.
- Redistribution, caching, preservation, derivative-work, automated-access,
  rate-limit, and commercial/noncommercial restrictions when stated.
- Privacy/public-data notices and prohibited uses when stated.
- Whether controlled raw preservation, fixture minimization, hashes, profiling,
  and derived aggregate reports appear compatible.
- Every unresolved term requiring human confirmation before adoption.

This is source qualification, not legal advice. Do not approve use when the
evidence is unclear.

### Authority, scope, and fitness

Assess, with evidence:

- Whether the candidate represents current statewide facility reference data,
  selected programs, a convenience export, or another scope.
- Whether stable facility/license identity exists for RecordsTracker's intended
  reference use.
- Which fields appear intended as current reference attributes and which have
  source/effective dates.
- Whether inactive/closed records are included and how omissions are described.
- Whether a missing facility can mean closure, changed scope, temporary omission,
  identifier change, validation failure, or deletion. Do not pick one without
  evidence.
- What the source cannot establish about complaint history, facility status,
  statewide completeness, or historical identity.

### Facility type and code 733

Treat `733` as an unexplained raw source value until Workstream A and official
metadata prove a stable, unique mapping. Record the official code/domain evidence,
source field, descriptive label, scope, and conflicts. If a mapping cannot be
verified, require the value to remain unresolved. Do not recommend a renderer
dictionary or infer STRTP from the visible defect alone.

## Precedence and conflict analysis

Provide at least these candidate models and evaluate their provenance, timing,
and failure behavior:

1. Statewide source as current-reference owner, with complaint-report values
   preserved as historical source-reported context.
2. Statewide source supplementing program-specific sources only for named fields
   or programs.
3. Program-specific sources retaining ownership for named fields while the
   statewide source supplies identity or gap coverage.
4. Candidate rejected or held inactive, leaving current governed behavior in
   place pending better evidence.

For each model define:

- Field-by-field owner candidates for name, facility number, type raw code, type
  label, status, address, geography, capacity, licensee/operator, and dates.
- Source and effective-date interpretation.
- Original-value and field-level provenance retention.
- Null/blank behavior: a later missing value must not erase an existing nonblank
  value without an approved rule.
- Conflicting nonblank behavior and reviewer/operator visibility boundaries.
- Current reference versus historically reported complaint identity display.
- Duplicate identifier, identifier change, and multiple-row behavior.
- Inactive, closed, disappeared, tombstone, source-scope-change, and validation-
  failure behavior.
- Last-accepted-source retention and rollback requirements.
- Why existing PostgreSQL rows are persistence state, not independent source
  authority.

Do not finalize a production precedence rule. Recommend options and gates for a
later #482 approval.

## Freshness and change-detection analysis

Using official evidence and Workstream A results, distinguish:

- Catalog metadata change.
- ArcGIS item/service/layer metadata change.
- Original-byte hash change.
- Canonical row hash change.
- Schema/domain change.
- Record-count or facility-identifier-set change.
- Added, changed, missing, duplicated, or conflicted facilities.
- Source outage, partial retrieval, validation failure, and actual accepted
  content change.

Recommend a future refresh observation cadence only when justified by measured
source behavior and published limits. Require validation before activation,
retention of the previous accepted version on failure, and operator review for
unexplained disappearance or unresolved type codes. Do not implement #477 or
#478.

## Required documents

### `docs/analysis/issue-490-governance-source-qualification.md`

Include:

- Scope, evidence date, source candidate identity, and no-approval boundary.
- Evidence table for catalog, dataset/resource, ArcGIS item/service/layer,
  publisher, system representation, terms, license, attribution, restrictions,
  and access behavior.
- Direct versus inferred/conflicting/unavailable classifications.
- Authority, scope, currency, completeness, and historical-use limitations.
- Public-data, privacy, preservation, redistribution, and no-secret findings.
- Unresolved human/legal/governance review items.
- Exact citations or official public URLs with access dates.

### `docs/analysis/issue-490-governance-recommendation.md`

Include:

- Exact Workstream A evidence version consumed, or the explicit absence of it.
- Adopt/supplement/reject/inconclusive rubric results, one gate at a time.
- A conditional or evidence-supported verdict; never force a decision to meet a
  schedule.
- Current-reference versus historical complaint-context rules.
- Field-level precedence options and provenance-preserving conflict rules.
- Blank/null, duplicate, identifier-change, inactive/closed, disappearance,
  tombstone, validation-failure, last-accepted-version, and rollback options.
- Facility type code/label and `733` status without assumption.
- Content-change versus catalog-change analysis and a justified future cadence
  range or an explicit inability to recommend one.
- Follow-up mapping to #482, #453, #477, and #478.
- Schema/import/backfill/read-model/UI/operator/schedule dependencies that would
  require later approval.
- An explicit statement that the document is not the final Issue #490 completion
  report and does not approve implementation or source activation.

## Decision rubric

Apply the rubric in
`docs/planning/issue-490-statewide-facility-source-evaluation-plan.md` exactly.

- **Adopt** only when every authority, permitted-use, reproducibility,
  equivalence, identity, data-quality, code/label, provenance, conflict, and
  offline-test hard gate passes.
- **Supplement** only with named field/program ownership and explicit conflict
  rules.
- **Reject** when a critical authority, use, access, identity, stability, or
  provenance condition fails.
- **Inconclusive** when required evidence is missing, including unavailable or
  failed Workstream A technical evidence.

The recommendation is advisory and still requires integration and human
approval.

## Follow-up mapping

Map findings without beginning the issues:

- #482 consumes verified source identity, current/historical distinctions,
  precedence options, code/label status, and conflict/disappearance rules.
- #453 consumes source/version, population, raw-code, label, unresolved-code,
  conflict, and regression baselines.
- #477 consumes operator-safe source, refresh, hash/schema/count, validation,
  conflict, unresolved-code, and last-accepted-version status requirements.
- #478 consumes measured access/change behavior, justified cadence, validation-
  before-activation, idempotence, prior-version retention, conflict,
  disappearance, and tombstone requirements.

## Validation

Run the smallest checks that prove this documentation-only work. At minimum:

1. `.\scripts\docs.ps1`.
2. `tests/data_quality/test_documentation_checks.py` if the repository's current
   focused documentation validation requires it.
3. A link/citation and access-date scan over the two owned documents.
4. A required-section scan against this prompt and the evaluation plan.
5. A cautious-language scan proving no unsupported authority, freshness,
   completeness, legal, facility-wide, or `733` claim.
6. A no-secret, no-private-URL, and no user-specific-path scan.
7. `git diff --check`.
8. A changed/untracked-file audit proving only the two Workstream B files changed.
9. A scan proving no Workstream A or reserved integration file changed.

Do not run the complete test suite. Do not use live network access in automated
tests.

## Stop conditions

Stop before further access or editing and report if:

- The branch, worktree, base SHA, clean state, ownership, or dispatch placeholder
  is wrong.
- A required endpoint or redirect is outside the exact network allowlist.
- Source access requires authentication, credentials, new terms acceptance,
  CAPTCHA bypass, or non-public data.
- Terms, license, attribution, publisher, or system representation cannot be
  established from official evidence; report the exact blocker rather than
  inferring permission or authority.
- Required work crosses the two-document ownership list or needs a reserved file.
- Workstream A evidence is missing, invalid, changed after consumption, or
  internally contradictory; keep the verdict conditional/inconclusive.
- Code `733` cannot be verified; report it unresolved rather than guessing.
- A connector, profiler, test, fixture, schema, migration, production import,
  backfill, app/UI, scheduler, deployment, QNAP, or downstream issue change would
  be required.
- The current inventory-language conflict cannot be described without editing a
  reserved integration file.

An unavailable or failing source is a valid qualification result. Do not
substitute an unapproved source or expand scope.

## Final handoff

Stop after the two documents and focused local validation. Report:

1. Verified base SHA, branch, worktree template, capabilities used, and exact
   endpoint allowlist.
2. Exact files changed.
3. Official evidence reviewed, access dates, and evidence-status summary.
4. Workstream A evidence commit/manifest/version consumed, or why the
   recommendation remains inconclusive.
5. Summary of publisher, system representation, terms/license/attribution,
   authority, precedence, conflict, freshness/change, `733`, and verdict
   findings.
6. Validation commands and pass/fail results, including intentionally unrun
   checks.
7. Documentation and security/privacy impact.
8. Unresolved human, legal, governance, and technical decisions.
9. Confirmation that Workstream A and reserved integration files were untouched.
10. Confirmation that no source, data store, app, schema, migration, UI,
    backfill, scheduler, branch lifecycle, PR, QNAP, deployment, or external
    mutable state changed.

Do not commit, stage, push, create or update a PR, merge, clean up, close Issue
#490, or begin another issue.

---
