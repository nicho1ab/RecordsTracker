# Build Week 2026 ArcGIS facility-reference completion plan

## Status and completion boundary

This document defines the remaining Build Week 2026 production sequence for
replacing the normal program-specific CSV facility-reference path with a
governed statewide ArcGIS/FeatureServer source when, and only when, the required
evidence supports adoption. It implements the completion-scope decision in
Issue #516; it does not itself authorize source activation, database mutation,
deployment, or issue closure.

Issue #490 remains a completed evaluation with the verdict **inconclusive;
retain existing program-specific sources and keep the statewide candidate
inactive**. Its preserved evidence is an input to this sequence, not proof that
the candidate is fit for production. The current deployed Build Week checkpoint
is `d7e9b1fff9e1826c3387a7313777d14c1480d3b4`; it is not the final Build Week
release.

The phases below are sequential. A phase may use parallel work only with
exclusive ownership and an explicit integration gate. No later phase may infer
that an earlier phase passed merely because code merged or a source responded.

## Governing invariants

- Follow `discover -> fetch -> store raw -> extract -> normalize -> validate ->
  emit` and preserve immutable original source snapshots before parsing.
- Detect content changes from original-byte hashes, normalized row content,
  schema/domain fingerprints, and facility-identifier sets. Catalog, item, or
  service timestamps are metadata signals only.
- Keep complaint-report identity and facility facts as historical source-
  reported context. A current facility-reference snapshot must not rewrite that
  history.
- Preserve original values, field-level provenance, source/effective dates,
  conflicts, blanks, invalid values, disappearances, and unresolved mappings.
- Existing PostgreSQL rows are persistence state, not independent source truth.
- Raw facility-type value `733` remains unresolved unless official source or a
  separately governed mapping proves one stable descriptive label.
- Tests use deterministic fixtures and mocks. Live public-source observations,
  deployment, and Hosted acceptance are separate governed evidence phases.
- A failed retrieval, validation, comparison, backfill, reconciliation, or
  acceptance preserves the last accepted source version and the prior
  application release. Failure never authorizes silent fallback, deletion, or
  bypass.

## Phase A — governed shadow connector and comparison

### Required outcome

Implement a production-quality ArcGIS/FeatureServer connector that resolves the
approved catalog, item, service, layer, and stable export identities; performs
bounded complete retrieval; stores immutable raw responses before parsing; and
emits deterministic normalized snapshots. Run it in shadow mode against the
retained program CSV snapshots and existing PostgreSQL facility-reference rows
without changing active production reads.

The comparison must report schema and domain fingerprints, original-byte and
normalized-content hashes, pagination/export equivalence, row and Facility ID
coverage, duplicates, additions, changes, disappearances, field population,
conflicts, status values, type codes and labels, and unresolved values including
`733`.

### Dependencies

- Issue #490 reports and preserved technical evidence.
- Confirmed public source identity, publisher/maintainer relationship, permitted
  use, attribution, and a bounded stable retrieval contract.
- Existing source connector and data contracts.
- Approved network, raw-snapshot, privacy, and retention boundaries.

### Prohibited shortcuts

- No catalog timestamp as content-change proof.
- No first-page, default-limit, row-count-only, or service-only completeness
  claim; no unapproved redirect or browser scraping.
- No import, active-source switch, PostgreSQL write, renderer dictionary, or
  deletion during shadow mode.
- No assumption that an omitted row is closed or that `733` has a label.

### Tests

- Fixture-backed discovery, redirect, pagination, ordering, terminal-page,
  timeout, throttling, malformed-response, and schema/domain-drift tests.
- Raw-before-parse preservation and deterministic hash tests.
- Full export versus complete query reconciliation by stable identity and row
  fingerprint, including same-count mismatches.
- Shadow comparison tests for blanks, invalid values, duplicates, conflicts,
  disappearance, and repeat-run determinism, with zero live network calls.

### Evidence

- Immutable snapshot manifest with source identities, retrieval times, hashes,
  byte counts, schema/domain fingerprints, and validation status.
- Deterministic ArcGIS-to-CSV and ArcGIS-to-PostgreSQL comparison packages with
  safe aggregate summaries and bounded conflict evidence.
- Reproducible test and validation results plus explicit blocked or inconclusive
  checks.

### Completion gate

Complete only when the selected source path is reproducible, pagination is
complete, service/export results reconcile or one method is explicitly
qualified, normalized-content change detection is deterministic, and shadow
evidence is sufficient for the Phase B decision. An unresolved authority,
license, source identity, material coverage, or critical data-quality question
blocks the gate.

### Rollback or preservation rule

Shadow mode cannot alter the active source. Retain every accepted CSV snapshot,
the prior PostgreSQL state, all immutable ArcGIS snapshots and manifests, and a
safe record of failed attempts. Reject incomplete or invalid ArcGIS versions
without changing the last accepted source.

## Phase B — source decision and production cutover authorization

### Required outcome

Review Phase A evidence and record an explicit **adopt**, **supplement**, or
**reject** decision. The decision must name source ownership by field and
program, precedence, effective/source-date handling, conflict and disappearance
rules, accepted quality thresholds, fallback conditions, attribution, and the
exact source version eligible for cutover.

If adoption is supported, authorize ArcGIS as the governed normal production
facility-reference source. The program CSV snapshots remain retained for
provenance, history, comparison, and controlled fallback, but cease to be the
normal active production source only after the authorized cutover gate passes.

### Dependencies

- Passing Phase A evidence and reproducible manifests.
- Human resolution of source authority, terms, license, attribution, and any
  material unresolved source relationship.
- Approved precedence, conflict, disappearance, validation-failure, and
  last-accepted-version rules.

### Prohibited shortcuts

- No adoption because the source is labeled statewide, newer, official-looking,
  or similar in row count.
- No ambiguous decision, implicit cutover, silent supplementation, or activation
  before field ownership and fallback rules are approved.
- No completeness, currency, legal, or source-of-record claim beyond evidence.

### Tests

- Decision-contract tests for finite decision and reason states.
- Threshold tests that block activation on partial retrieval, schema/domain
  drift, duplicate identity, unexplained material disappearance, unresolved
  critical mapping, or failed comparison.
- Configuration tests proving the active-source choice is explicit and
  fail-closed.

### Evidence

- Signed-off decision record linked to the exact Phase A manifests and hashes.
- Field/program ownership matrix, accepted thresholds, known limitations,
  attribution requirements, and cutover/fallback procedure.
- Proof that no active-source configuration changed before approval.

### Completion gate

Complete when reviewers approve one evidence-supported decision. Only an
**adopt** decision advances to ArcGIS production replacement; **supplement**
must define its bounded ownership, and **reject** retains the CSV family as the
normal active source and records why the replacement sequence stopped.

### Rollback or preservation rule

Retain the decision inputs, rejected or superseded snapshots, and the complete
CSV source history. The last accepted source remains active until a separately
authorized, validated cutover succeeds.

## Phase C — unified facility identity and controlled backfill under #482

### Required outcome

Under Issue #482, implement one governed facility identity projection and use it
across search, facility hub, review queue, complaint detail, packet views,
exports, and operator reporting. If Phase B authorizes ArcGIS adoption, perform
a controlled PostgreSQL facility-reference backfill that applies only approved
ArcGIS values with field-level source/version/effective-date provenance,
retains conflicting nonblank values, preserves complaint history, and is
idempotent and recoverable.

Facility-type identifiers must display verified descriptive labels. Raw `733`
must remain raw and explicitly unresolved unless governed source or mapping
evidence proves its label.

### Dependencies

- Phase B adoption or bounded supplement decision.
- Issue #482 field ownership, stable-identity, alias/succession, and display
  rules.
- Approved schema/migration and backfill plans where persistence changes are
  required.
- Restorable database backup and last-accepted source package.

### Prohibited shortcuts

- No page-local identity joins, renderer dictionaries, last-row-wins updates,
  lexical precedence, or silent overwrite of nonblank conflicts.
- No rewriting historical complaint-report values from current reference data.
- No apply-by-default, physical deletion, inferred closure, or unbounded
  backfill.

### Tests

- Stable identity, alias/succession, duplicate, null, conflict, and date-
  precedence tests across SQLite/PostgreSQL-supported boundaries.
- Dry-run/apply idempotence, checkpoint, failure, recovery, and rollback tests.
- Cross-surface contract tests proving every named consumer uses the same
  projection and unresolved `733` never gains an invented label.
- Export and print tests preserving provenance and reviewer-safe display.

### Evidence

- Versioned identity and backfill manifests with planned/applied/unchanged/
  conflicted/rejected counts and field-level provenance samples.
- Before/after aggregate reconciliation against the approved ArcGIS snapshot,
  with no unexplained loss or overwrite.
- Automated route, export, print, accessibility, responsive, and keyboard
  evidence for the shared projection.

### Completion gate

Complete when the approved source values reconcile to PostgreSQL, the backfill
is idempotent and recoverable, conflicts and unresolved values remain visible at
the appropriate tier, and every named consumer passes shared identity tests.

### Rollback or preservation rule

Retain the pre-backfill database backup, previous source package, ArcGIS and CSV
snapshots, field-level prior values, conflict records, and checkpoint. Rollback
restores the prior accepted application/database state without deleting source
history or reconstructing truth from current rows.

## Phase D — source-to-screen and operator reconciliation under #453/#477

### Required outcome

Extend Issue #453 source-to-screen coverage through the active ArcGIS snapshot,
normalized facility identity, approved PostgreSQL values, read models, every
named user surface, exports, and operator reports. Extend Issue #477 with
read-only monitoring plus only the minimum separately authorized operational
actions necessary to observe and safely control ArcGIS refresh and backfill
jobs.

Operator diagnostics must show active source and snapshot, last attempted and
successful refresh, content and schema state, row/Facility ID reconciliation,
added/changed/missing/conflicted facilities, unresolved codes, backfill and
checkpoint state, failures, and bounded retry eligibility without exposing raw
records or secrets.

### Dependencies

- Completed Phase C identity/backfill reconciliation.
- Existing Issue #453 contract adapter and Issue #477 production authorization
  boundary.
- Separately approved permissions and finite job/action contracts for any
  minimum operational action.

### Prohibited shortcuts

- No duplicated coverage calculation in the dashboard or page-local consumer.
- No operator action inferred from read access; no broad job console, raw source
  viewer, arbitrary command, silent retry, or auth bypass.
- No coverage claim based only on PostgreSQL row presence or route success.

### Tests

- Deterministic producer/adapter/consumer contract tests for ArcGIS source,
  identity, field, stage, route, export, conflict, and unresolved-code coverage.
- Authorization tests proving authentication before reads and action-specific
  operator permission before every mutation.
- Fail-closed unavailable/invalid/stale/partial package tests and bounded action
  state-machine tests where authorized.
- Automated responsive, keyboard, accessibility, print, CSV, and no-secret UI
  evidence.

### Evidence

- Versioned source-to-screen package linked to exact source, backfill, database,
  and deployed commit identities.
- Route and authorization assertion results, screenshots, text/CSV captures,
  manifest hashes, and reconciliation summaries.
- Explicit unavailable, blocked, partial, failed, and retry-eligible states.

### Completion gate

Complete when every named source-to-screen path reconciles, the operator can
diagnose failures and safely control only authorized jobs, authorization fails
closed, and automated evidence contains no credentials, assertions, cookies,
headers, private host details, or raw sensitive records.

### Rollback or preservation rule

Retain the last valid coverage package and job history. A producer, adapter,
authorization, or action failure must not change the active source or erase
prior evidence; disable the affected action while preserving read-only status.

## Phase E — scheduled governed refresh and checkpoint recovery under #478

### Required outcome

Under Issue #478, schedule governed ArcGIS refresh through discovery, immutable
snapshot retrieval, normalization, validation, shadow comparison,
decision/activation checks, controlled backfill, reconciliation, evidence
publication, and notification. Prevent overlap with a lock, persist finite
checkpoints, support bounded retry/cancel/resume and recovery, and publish safe
summaries.

Cadence must be justified by measured source behavior and published limits.
Refresh must compare normalized content and schema/identity signals, not catalog
timestamps alone.

### Dependencies

- Completed Phases A-D and an active-source decision.
- Approved cadence, lock ownership/expiry, checkpoint, retry classification,
  notification, retention, disappearance, and recovery policies.
- Human-operated deployment/rollback procedure for the target runtime.

### Prohibited shortcuts

- No overlapping run, timestamp-only no-op decision, unbounded retry, automatic
  acceptance of drift, physical deletion, or cleanup without retention policy.
- No resume from an unvalidated or mismatched checkpoint.
- No replacement of the previous accepted version after a failed run.

### Tests

- Schedule, lock contention/expiry, idempotence, checkpoint, retry category,
  cancel, resume, crash recovery, and notification tests.
- Schema/domain drift, partial retrieval, duplicate, disappearance, source
  outage, content-no-change, content-change, backfill failure, and reconciliation
  failure tests.
- End-to-end deterministic fixture runs proving exactly-once activation and safe
  evidence output.

### Evidence

- Run manifest and timeline with source/content hashes, lock/checkpoint states,
  validation and reconciliation outcomes, actions, and safe failure summaries.
- Proof that unchanged normalized content causes no backfill and that changed
  content cannot activate before all gates pass.
- Recovery evidence from representative interrupted stages.

### Completion gate

Complete when scheduled runs cannot overlap, all stages are observable and
recoverable, unchanged and changed content are distinguished deterministically,
activation is validation-gated, reconciliation is mandatory, and failures
preserve the last accepted source and database state.

### Rollback or preservation rule

Retain immutable source versions, manifests, checkpoints, run history, and the
prior accepted database/application release according to approved policy.
Rollback selects a previously accepted version; it never refetches or rebuilds
historical truth from mutable current state.

## Phase F — production deployment, Hosted acceptance, and final release

### Required outcome

Merge all required implementation phases through normal review, deploy the
exact accepted merge SHA through the human-operated release process, verify
application and database health without recreating PostgreSQL, and run automated
Hosted acceptance against the deployed production-auth path. Reconcile the
deployed ArcGIS snapshot, PostgreSQL state, source-to-screen package, operator
diagnostics, scheduled refresh state, named reviewer routes, exports, and
evidence manifests.

After all required checks, deployment verification, automated Hosted acceptance,
documentation, and issue completion gates pass, record the final Build Week SHA
and move tag `openai-build-week-2026` to that exact accepted SHA.

### Dependencies

- Completed and merged Phases A-E with required CI checks passing.
- Human QNAP operator deployment authorization and approved release archive.
- Approved production authentication and ephemeral Hosted evidence provider;
  absence remains a blocker and never authorizes bypass.
- Final documentation and issue-state review.

### Prohibited shortcuts

- No final SHA or tag at a feature-branch head, local-only checkpoint, merely
  healthy route, incomplete Hosted capture, or unmerged phase.
- No client-supplied authentication assertion at an unapproved public edge, no
  cookies/browser profiles/stored assertions/secrets in evidence, and no manual
  browser inspection substituted for automated acceptance.
- No PostgreSQL recreation or restore for an application-only release unless a
  separate incident/rollback procedure explicitly requires it.

### Tests

- Required CI, migration/Alembic, runtime configuration, route, auth, package,
  database reconciliation, refresh/job, export, accessibility, keyboard,
  responsive, and print checks.
- Deterministic LocalProductionAuth evidence before deployment and automated
  Hosted acceptance at the exact deployed merge SHA.
- Release archive, Compose configuration, health/restart-count, and rollback
  validation appropriate to the approved deployment.

### Evidence

- Final merge/deployed SHA, release archive hash, application/PostgreSQL health
  and restart counts, Alembic status, route and authorization results, runtime
  package/database reconciliation, public endpoint verification, and Hosted
  evidence path/hash/captures/assertions/statuses.
- Retained prior release, Compose, environment, source, database, and evidence
  backups, with no secrets copied into evidence.
- Final documentation and issue linkage for #482, #453, #477, #478, and #516.

### Completion gate

Complete only when all required phases are merged, the exact merge SHA is
deployed, automated Hosted acceptance passes without auth or evidence bypass,
runtime/source/database reconciliation passes, required issues satisfy their
approved completion criteria, and final documentation is accepted. Until then,
the final Build Week SHA and release remain pending.

### Rollback or preservation rule

Keep the previous application release with its Compose file, the host-local
environment, PostgreSQL data and backup, last accepted source package, and
evidence. Roll back application and active-source selection together under the
approved runbook; never discard immutable snapshots, field provenance,
conflicts, checkpoints, or the prior accepted release.

## Issue linkage and state

- **#490:** completed evaluation evidence; remains complete and is not reopened
  or recharacterized as production adoption.
- **#482:** required Build Week implementation for the unified facility identity
  projection and controlled ArcGIS backfill.
- **#453:** remains open for blocked Hosted evidence and additional ArcGIS
  source-to-screen verification.
- **#477:** remains required for read-only monitoring and the minimum separately
  governed operational actions necessary to observe and safely control ArcGIS
  refresh and backfill jobs.
- **#478:** required Build Week implementation for scheduled governed refresh,
  locking, checkpoints, recovery, and reconciliation.
- **#516:** governs this completion-scope alignment; it does not by itself mark
  any implementation phase complete.

No new issue is required by this plan. Issue state changes occur only after the
applicable implementation, deployment, evidence, and review gates pass.

## Final Build Week release rule

The pre-Build Week baseline remains
`bb5b1246fbf677a328c70abad48af3023fa1ebb0`. The first eligible Build Week
commit remains `508102077ec57dcf673142620e412ad2bf7078b1`. The current deployed
checkpoint is `d7e9b1fff9e1826c3387a7313777d14c1480d3b4`, but the final Build Week
release is pending.

The final release must include this complete ArcGIS replacement sequence and
may be named only after every required phase is merged, deployed, and accepted.
Tag `openai-build-week-2026` must eventually point to that exact final accepted
SHA, not to the current checkpoint.
