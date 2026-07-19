# Issue #490 parallel work ownership

## Purpose

This document defines exclusive ownership, coordination, evidence exchange, and
stop conditions for two Issue #490 workstreams. Neither workstream may begin
until the planning change containing this document has merged to `main`.

The evaluation requirements are in
[Issue #490 statewide facility source evaluation plan](issue-490-statewide-facility-source-evaluation-plan.md).
The task templates are:

- [Workstream A — technical source profiling](issue-490-workstream-a-codex-prompt.md)
- [Workstream B — governance and source qualification](issue-490-workstream-b-codex-prompt.md)

## Common dispatch gate

Before either branch or worktree is created or assigned, the dispatcher must:

1. Confirm the planning change is merged to `main`.
2. Record the full 40-character planning merge SHA.
3. Verify local `main` and `origin/main` match that SHA and the base worktree is
   clean.
4. Inspect branches, worktrees, unpushed commits, active tasks, and file overlap.
5. Replace every `{{ISSUE_490_PLANNING_MERGE_SHA}}` placeholder in the selected
   prompt with that SHA.
6. Replace `{{APPROVED_ARCGIS_ENDPOINTS}}` with an exact URL allowlist. A wildcard
   host or an instruction to follow arbitrary links is not sufficient.
7. State the exact source and GitHub network allowlists, validation, stop point,
   and prohibited actions in the dispatched task.
8. Stop on dirty state, an unexpected branch, an unexplained worktree, unpushed
   commits, unresolved write overlap, or an unfilled dispatch placeholder.

The repository-safe path templates below intentionally use `<repo-parent>`.
Committed documentation must not contain a user-specific repository path.

## Branches and worktrees

| Phase | Branch | Worktree |
| --- | --- | --- |
| Workstream A | `issue-490-technical-source-profile` | `<repo-parent>\CCLD-complaints-poc-issue-490-profile` |
| Workstream B | `issue-490-governance-source-qualification` | `<repo-parent>\CCLD-complaints-poc-issue-490-governance` |
| Later integration | `issue-490-source-evaluation-integration` | `<repo-parent>\CCLD-complaints-poc-issue-490-integration` |

The worktree directory names are fixed. The dispatcher substitutes the local
repository parent outside committed content.

## Coordination model

```text
planning package merged to main
        |
        +-----------------------------+
        |                             |
        v                             v
Workstream A                     Workstream B
technical source profiling       governance/source qualification
code + fixtures + mocks          official evidence + rules + recommendation
machine-readable outputs         human-readable qualification/recommendation
        |                             |
        +--------------+--------------+
                       |
                       v
              later integration branch
              reconcile evidence and decision
              update reserved shared files
              create final Issue #490 report
```

The branches begin from the same planning merge SHA. They do not merge into each
other and do not resolve each other's files. Each workstream stops after its own
focused validation and handoff. Repository lifecycle work is separately
authorized and is not granted by these planning documents.

## Exclusive file ownership

### Workstream A — technical source profiling

Workstream A exclusively owns the following tracked paths for Issue #490:

- `src/ccld_complaints/source_profiling.py`
- `src/ccld_complaints/statewide_facility_source_evaluation.py`
- `scripts/profile_statewide_facility_source.py`
- `schemas/issue-490-statewide-facility-source-profile.schema.json`
- `tests/unit/test_source_profiling.py`
- `tests/unit/test_statewide_facility_source_evaluation.py`
- `tests/fixtures/source_profiling/issue_490/**`
- `docs/analysis/issue-490-technical-source-profile.md`

Workstream A may create controlled local artifacts only in these existing ignored
boundaries:

- `data/raw/source-profiling/issue-490/**`
- `data/processed/source-profiling/issue-490/**`
- `data/logs/issue-490-source-profiling/**`

Those local artifacts must remain untracked. If any path is not ignored,
Workstream A stops before writing there; changing `.gitignore` is an integration
decision unless separately assigned.

Workstream A owns source discovery implementation, controlled snapshots, raw and
canonical hashes, schema/profile logic, pagination and query-equivalence logic,
fixtures, mocks, profiler code, technical tests, and machine-readable profiling
output. It does not own the source-authority recommendation.

Workstream A must not edit:

- Either Workstream B analysis document.
- Any of the four Issue #490 planning-package documents.
- `CHANGELOG.md`.
- `ROADMAP.md`.
- `PUBLIC_SOURCE_DATA_INVENTORY.md`.
- `GOVERNANCE_INVENTORY.md`.
- A final Issue #490 completion report.
- Any shared index or decision-summary file.
- Application code outside the exclusive paths above, hosted app code, canonical
  schemas, Alembic migrations, database initialization, UI, QNAP, deployment, or
  scheduled-refresh files.

### Workstream B — governance and source qualification

Workstream B exclusively owns:

- `docs/analysis/issue-490-governance-source-qualification.md`
- `docs/analysis/issue-490-governance-recommendation.md`

Workstream B owns publishing-agency and system-of-record research, terms/license/
attribution analysis, source-authority assessment, current-versus-historical
identity analysis, precedence options, provenance-preserving conflict rules,
freshness and content-change analysis, and the human-readable recommendation.

Workstream B must not edit:

- Any Workstream A code, scripts, fixtures, schemas, tests, technical report, raw
  artifacts, or generated machine-readable output.
- Any of the four Issue #490 planning-package documents.
- `CHANGELOG.md`.
- `ROADMAP.md`.
- `PUBLIC_SOURCE_DATA_INVENTORY.md`.
- `GOVERNANCE_INVENTORY.md`.
- A final Issue #490 completion report.
- Any shared index or decision-summary file.
- Application code, schemas, migrations, database initialization, generated
  profiling artifacts, reviewer UI, operator UI, QNAP, deployment, backfill, or
  scheduled-refresh files.

Workstream B may read a completed Workstream A technical report and validated
generated-output manifest. It must not copy generated raw data into tracked docs
or modify A's artifacts. If A's evidence is not available, B may complete source
qualification and a conditional rubric, but it must label the verdict
`inconclusive pending technical evidence` rather than infer missing results.

## Reserved for the later integration branch only

Neither parallel workstream may modify:

- `CHANGELOG.md`
- `ROADMAP.md`
- `PUBLIC_SOURCE_DATA_INVENTORY.md`
- `GOVERNANCE_INVENTORY.md`
- The final Issue #490 completion report
- Any shared index or decision-summary file

The integration branch is also the only owner of:

- The final reconciliation between existing inventory language that calls the
  current CHHS/CDSS resource family authoritative for preload and Issue #490's
  unprofiled statewide ArcGIS candidate status.
- The combined adopt, supplement, reject, or inconclusive verdict.
- Cross-workstream evidence reconciliation and any approved follow-up issue
  mapping changes.

The integration branch may not implement a connector, production import,
backfill, schema, migration, application/UI change, scheduler, deployment, or
QNAP operation unless a separate task explicitly grants that new scope.

## Evidence exchange contract

### Workstream A handoff to B and integration

Workstream A reports:

- Commit SHA and verified base SHA.
- Exact source endpoints observed and the approved allowlist used.
- Technical-report path.
- Generated-output directory and manifest path, using repository-relative paths.
- Evaluation contract/schema version.
- Hashes and validation status for each machine-readable deliverable.
- Snapshot retrieval times and safe source-version metadata.
- Pass, fail, warning, blocked, and inconclusive checks.
- Exact unresolved technical questions.

Machine-readable output ordering, field names, null semantics, and finite status
values must be stable so Workstream B and integration can consume results without
guessing.

### Workstream B handoff to A and integration

Workstream B reports:

- Commit SHA and verified base SHA.
- Exact official evidence URLs and access dates.
- Publishing agency and represented system-of-record findings.
- Terms, license, attribution, access, and public-use findings.
- Authority and scope limitations.
- Precedence, conflict, current-versus-historical, disappearance, and freshness
  options.
- Which technical evidence was consumed by path, manifest hash, and status.
- Conditional or evidence-supported recommendation and unresolved gates.

Workstream B does not instruct A to rewrite machine output. A discovered
technical defect is reported as an integration blocker or sent back through a
separately approved A follow-up.

## Coordination checkpoints

1. **Start checkpoint:** planning merge SHA, clean worktrees, exact allowlists,
   and exclusive ownership confirmed.
2. **Discovery checkpoint:** A records exact ArcGIS endpoints. If an endpoint is
   outside the dispatched allowlist, A stops network access and requests a
   revised task; it does not follow the link automatically. B can continue
   already allowlisted official-source qualification.
3. **Contract checkpoint:** A freezes the machine-readable contract before B
   cites technical output. Later breaking changes require an explicit version
   and coordination note.
4. **Recommendation checkpoint:** B verifies the technical manifest it consumed.
   Without it, the recommendation remains conditional/inconclusive.
5. **Integration checkpoint:** the integration owner confirms both branch heads,
   validation, non-overlap, reserved-file integrity, and unresolved decisions
   before combining work.

## Merge and integration order

Recommended integration order:

1. Create the integration branch from current clean `main` only after both
   workstreams stop and report.
2. Bring in Workstream A without modifying its owned files.
3. Bring in Workstream B without modifying its owned files.
4. Verify the combined diff has no overlapping path and that B cites the exact A
   evidence version it consumed.
5. Resolve only integration-owned documents and reserved shared files explicitly
   authorized for that integration task.
6. Run the combined focused validation, documentation checks, security/path
   checks, and `git diff --check`.
7. Stop for human approval. Source activation and downstream implementation remain
   separate tasks.

## Stop conditions

Either workstream stops immediately and reports if:

- The planning package has not merged or the dispatch SHA is missing/mismatched.
- Local `main`, `origin/main`, or the assigned branch/worktree is dirty,
  divergent, owned by another task, or otherwise unexplained.
- An exact network endpoint is outside the allowlist.
- Terms require authentication, credentials, acceptance of unapproved terms, or
  access to non-public data.
- A browser, QNAP, SSH, Docker, database, deployment, or other prohibited tool is
  needed.
- Required work crosses the exclusive file boundary or a reserved integration
  file must change.
- A full statewide raw snapshot, generated output, secret, private value, or
  personal path would become tracked.
- Technical and governance evidence conflict in a way that cannot be reported
  without an unapproved policy or implementation decision.
- The task would begin #482, #453, #477, #478, or another roadmap item.

## Non-overlap verification

At each workstream handoff and again in integration:

1. List changed and untracked files.
2. Compare every path with the exclusive and reserved lists above.
3. Confirm A changed no B-owned or reserved path.
4. Confirm B changed no A-owned or reserved path.
5. Confirm generated local artifacts remain ignored.
6. Confirm no application, canonical schema, migration, database, UI, backfill,
   schedule, deployment, or QNAP file changed.
7. Run `git diff --check`.

Any overlap is a stop condition, not an invitation for one workstream to resolve
the other's changes.

## Recommended Codex effort

- Workstream A: `xhigh`. The work combines public endpoint qualification,
  preservation ordering, ArcGIS pagination semantics, schema and row
  fingerprinting, cross-source equivalence, deterministic fixtures, and strict
  offline validation.
- Workstream B: `high`. The work is documentation-only but requires careful
  primary-source qualification, terms and authority analysis, historical versus
  current identity rules, conflict governance, and evidence-bounded language.
- Later integration: `xhigh`, because it must reconcile both evidence sets and
  reserved governance language without drifting into implementation.
