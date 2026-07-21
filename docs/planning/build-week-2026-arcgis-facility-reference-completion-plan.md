# Build Week 2026 ArcGIS facility-reference completion plan

> Historical plan notice: Issue #553 supersedes this document's forward-looking
> source direction. The official CCLD TransparencyAPI is now the approved
> primary current facility-reference source; ArcGIS remains separately versioned
> supplementary evidence and CKAN/program snapshots remain historical/controlled
> fallback evidence. The phases below are retained as Issue #516/#518 history
> and do not authorize new ArcGIS-first implementation.

## Status and completion boundary

This document defines the Build Week 2026 production sequence for implementing
the governed ArcGIS facility-reference **SUPPLEMENT** decision. Program-specific
snapshots remain the primary source family. ArcGIS is a separate supplementary
current-reference source; it does not replace the program sources. This plan
does not itself authorize source activation, database mutation, deployment, or
issue closure.

Issue #490 remains completed historical evaluation evidence. The definitive
Phase A evaluation under Issue #516 merged at
`41d512127febdfd086432e7f082d0651da232e9f` and returned **SUPPLEMENT**. The
current deployed Build Week checkpoint is
`d7e9b1fff9e1826c3387a7313777d14c1480d3b4`; it is not the final Build Week
release.

The original #516 issue body proposed replacing the program CSV sources. The
later Issue #516 comments and merged Phase A evidence supersede that premise:
program snapshots remain primary and ArcGIS may become only a separately
governed current-reference supplement. Nothing in this plan authorizes ArcGIS
activation, cutover, backfill, refresh scheduling, deployment, or issue closure.

The phases below are sequential. Safe parallel implementation starts only after
the Phase C identity and reconciliation contract is merged, and then only with
exclusive file/behavior ownership plus an explicit integration gate. No later
phase may infer that an earlier phase passed merely because code merged or a
source responded.

## Governing invariants

- Follow `discover -> fetch -> store raw -> extract -> normalize -> validate ->
  emit` and preserve immutable original source snapshots before parsing.
- Detect content changes from original-byte hashes, normalized row content,
  schema/domain fingerprints, and facility-identifier sets. Catalog, item, or
  service timestamps are metadata signals only.
- Keep complaint-report identity and facility facts as historical source-
  reported context. A current facility-reference snapshot must not rewrite that
  history.
- Keep program and ArcGIS snapshots, observations, identities, and lifecycle
  state separate. Neither source overwrites or erases the other.
- Blank ArcGIS values never erase nonblank program values. Identical values may
  reconcile while retaining both observations. Conflicting nonblank values
  retain both originals and conflict state; no global ArcGIS-wins or
  program-wins rule is approved.
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
- Facility disappearance does not mean closure or deletion. Failed candidates
  never partially apply, and rollback selects complete prior accepted snapshots.
- ArcGIS source-row identity is immutable snapshot identity plus `ObjectId`.
  Facility number is a non-unique matching/grouping value and cannot be a unique
  ArcGIS database or upsert key.
- Scheduling remains blocked until a governed cadence is approved.

## Decision and authority record

### Completed evidence and implementation

- #490 remains the historical, inconclusive evaluation that retained the
  program-specific sources and left the then-evaluated statewide candidate
  inactive. It is not rewritten by the later Phase A result.
- #516 Phase A completed the deterministic ArcGIS shadow comparison and approved
  **SUPPLEMENT**, not replacement, adoption, activation, or cutover.
- #521 established the shared read-only facility projection for eligible
  existing program-reference and complaint-linked data. #522 migrated the named
  reviewer surfaces, and #523 aligned the governed exports and bounded existing
  backfill. None of those completed issues consumes or activates ArcGIS.
- #477 is closed and repository-complete for its supported read-only operator
  dashboard. It did not authorize mutation, scheduling, source retrieval,
  deployment, or Hosted execution.

### Approved repository decisions

- Program snapshots remain the primary facility-reference source family;
  ArcGIS remains a separate, inactive supplementary current-reference source.
- ArcGIS source-row identity is snapshot identity plus `ObjectId`; Facility ID
  is a non-unique match/grouping value. Query and export remain distinct
  observations.
- Blank ArcGIS values do not erase nonblank program values. Identical values may
  reconcile while retaining both observations. Conflicting nonblank values keep
  both originals and explicit conflict state. No global source-wins rule exists.
- Current reference and historical complaint-time facts remain distinct. Raw
  `733` remains unresolved.

### Decisions reserved to Andrew and later governed phases

Andrew must explicitly approve the exact license/terms version and required
attribution, the candidate's source-of-record role, maintainer/steward/update
owner, refresh cadence, production field allowlist and field-specific
precedence, accepted-snapshot promotion, ArcGIS activation/cutover, and any
production backfill. Missing approval is a blocker, never permission to infer or
bypass a decision. QNAP deployment remains a human-operator action, and Hosted
acceptance remains a separate automated evidence gate against the exact deployed
merge SHA.

The exact next repository issue is **#518**, limited to the separate dual-source
snapshot and lifecycle boundary described in Phase B. After #518, #482 owns the
ArcGIS-specific identity/reconciliation and controlled-backfill extension; #453
owns additional ArcGIS source-to-screen coverage through the completed #477
read-only boundary; #478 owns any later approved scheduled refresh.

## Phase A — completed ArcGIS evaluation and SUPPLEMENT decision

### Required outcome

Completed the governed ArcGIS shadow evaluation and recorded **SUPPLEMENT** as
the authoritative decision. The evaluated ArcGIS source contains 29,871 rows,
29,714 unique nonblank facility numbers, and 129 duplicated facility numbers
across 286 rows. Query and export differ on 47 shared Facility IDs. The retained
program sources contain 68,526 unique nonblank Facility IDs: 27,831 shared,
1,883 ArcGIS-only, and 40,695 program-only.

Phase A established snapshot identity plus `ObjectId` as ArcGIS source-row
identity and facility number as a non-unique matching/grouping value. Raw `733`
remains unmapped. Refresh cadence, exact license version and attribution,
system-of-record status, maintainer, steward, and update owner remain unresolved.
Phase A did not activate ArcGIS or change runtime/database behavior.

### Dependencies

- Completed Issue #490 reports and preserved technical evidence.
- The bounded Issue #516 authorization for the exact public source identities
  and retrieval path.
- Existing source/data contracts and approved raw-snapshot/privacy boundaries.

### Prohibited shortcuts

- No catalog timestamp as content-change proof.
- No row-count-only equivalence claim or assumption that query/export are one
  atomic snapshot.
- No import, activation, PostgreSQL write, backfill, renderer dictionary,
  scheduling, or deletion.
- No assumption that disappearance means closure or that `733` has a label.

### Tests

- Fixture-backed source policy, redirect/query redaction, pagination,
  terminal-page, malformed-response, and schema/domain-drift tests.
- Raw-before-parse preservation, deterministic hash, duplicate, conflict,
  comparison, and repeat-run determinism tests.
- Full export/query and retained-program reconciliation by source identity and
  row fingerprint, including same-count value mismatches.

### Evidence

- The merged [Phase A comparison](../analysis/build-week-2026-arcgis-shadow-comparison.md)
  and [SUPPLEMENT recommendation](../analysis/build-week-2026-arcgis-source-recommendation.md).
- Immutable 100-artifact manifest, original/normalized hashes, schema/domain
  fingerprints, two observations, program reconciliation, and safe summaries.
- Explicit unresolved authority, license/attribution, ownership, cadence, and
  `733` findings.

### Completion gate

Complete. Phase A merged at `41d512127febdfd086432e7f082d0651da232e9f`
with **SUPPLEMENT**. The unresolved findings constrain later implementation;
they do not authorize replacement or activation.

### Rollback or preservation rule

Phase A altered no active source. Retain its immutable evidence and all program
history. Invalid future candidates must not change either source family's last
accepted snapshot.

## Phase B — separate governed source snapshots under #518

### Required outcome

Under Issue #518, implement separate immutable program and ArcGIS snapshots;
source-specific row identities; original-byte and normalized-content hashes;
schema, domain, count, identity, duplicate, disappearance, and conflict
validation; and candidate, validated, accepted, active, rejected, and
prior-accepted lifecycle state per source family.

Keep ArcGIS query and export observations separately identified. Promotion and
rollback operate on complete validated snapshots and preserve both histories.
Phase B does not perform reviewer integration, canonical facility backfill,
operator mutation, or scheduling.

### Dependencies

- Completed Phase A evidence and **SUPPLEMENT** decision.
- Issue #518's corrected dual-source boundary.
- Approved persistence design for source-specific snapshots and lifecycle
  pointers, plus explicit terms/authority blockers.

### Prohibited shortcuts

- No replacement model, overwrite-in-place sole source of truth, shared
  source-row key, or unique ArcGIS facility-number key.
- No collapsing duplicate ArcGIS rows, selecting a first/winning row, or
  treating query/export as one observation.
- No reviewer integration, canonical backfill, source activation, or scheduling.
- No completeness, currency, legal, or source-of-record claim beyond evidence.

### Tests

- Source-specific snapshot identity, immutable storage, hash, validation, and
  lifecycle-transition tests.
- Tests for partial retrieval, schema/domain drift, duplicates, query/export
  mismatch, disappearance, rejected candidates, and prior-accepted preservation.
- Atomic promotion/rollback and repeat-run tests proving both source histories
  remain intact.

### Evidence

- Source-specific manifests and immutable artifacts with original/normalized
  hashes, schema/domain fingerprints, validation decisions, and lifecycle state.
- Separate query/export observation evidence and accepted/prior-accepted pointer
  reconciliation.
- Proof that Phase B did not change canonical/reviewer data or source precedence.

### Completion gate

Complete when both source families can stage, validate, reject, promote, and
roll back complete snapshots independently and atomically, with deterministic
reconciliation of lifecycle pointers and no canonical/reviewer mutation.

Current repository status: PR #545 merged the offline lifecycle foundation.
The Issue #518 live-query completion branch adds the separately authorized
fixed-policy connector, immutable ignored response evidence, exact ObjectId
reconciliation, provisional attribution, and live-candidate adapters that reuse
the same transitions. A controlled live candidate completed stage, validation,
acceptance-state, promotion, and rollback in a disposable PostgreSQL schema;
prior accepted and unrelated reviewer-created state were preserved. Phase B may
be marked complete only after independent review, required checks, and merge.
This gate does not activate ArcGIS or authorize Phase C.

### Rollback or preservation rule

Retain every accepted, rejected, and superseded snapshot and manifest. A failed
candidate never partially applies; rollback selects the complete prior accepted
snapshot for that source family while preserving the other source unchanged.

## Phase C — unified facility identity and controlled backfill under #482

### Required outcome

Current status: #521-#523 completed the shared projection, named consumers and
exports, and bounded existing backfill for eligible program-reference data.
Issue #482 extends that same read-only projection to active accepted
TransparencyAPI primary and ArcGIS supplementary snapshots while retaining
CKAN/program and complaint-linked observations as historical evidence. It does
not recreate those consumers or authorize a production backfill.

Under Issue #482, implement one governed facility identity and reconciliation
projection over the separate TransparencyAPI, ArcGIS, CKAN/program, and
complaint-linked observations. Define stable identity, source-specific row
identity, governed matching, field-level ownership, source/effective-date
handling, blank-preserving fallback, conflict retention, duplicate handling,
and disappearance review.

The existing #523 bounded backfill remains separate and is not executed or
expanded by #482. Any future production backfill requires explicit selection,
checkpoints, repeat-run safety, failure isolation, protection of reviewer-created
state, and separate mutation authority. There is no global ArcGIS-wins rule,
and a current-reference value cannot rewrite historical complaint context.

Facility-type identifiers must display verified descriptive labels. Raw `733`
must remain raw and explicitly unresolved unless governed source or mapping
evidence proves its label.

### Dependencies

- Completed Phase B source-specific snapshots and lifecycle model.
- Issue #482 field ownership, stable-identity, alias/succession, and display
  rules.
- Approved schema/migration and backfill plans where persistence changes are
  required.
- Restorable database backup and last-accepted source package.

### Prohibited shortcuts

- No page-local identity joins, renderer dictionaries, last-row-wins updates,
  lexical precedence, or silent overwrite of nonblank conflicts.
- No unique ArcGIS facility-number key and no collapse of distinct `ObjectId`
  rows.
- No rewriting historical complaint-report values from current reference data.
- No apply-by-default, physical deletion, inferred closure, or unbounded
  backfill.

### Tests

- Stable identity, alias/succession, duplicate, null, conflict, and date-
  precedence tests across SQLite/PostgreSQL-supported boundaries.
- Dry-run/apply idempotence, checkpoint, failure, recovery, and rollback tests.
- Tests proving identical values retain both observations, blanks do not erase,
  conflicts retain both originals, and disappearance does not infer closure.
- Tests proving reviewer-created state is unchanged and unresolved `733` never
  gains an invented label.

### Evidence

- Versioned identity and backfill manifests with planned/applied/unchanged/
  conflicted/rejected counts and field-level provenance samples.
- Before/after aggregate reconciliation against both accepted source snapshots,
  with no unexplained loss, overwrite, or source-history collapse.
- Checkpoint, repeat-run, failure-isolation, reviewer-state-preservation, and
  rollback evidence.

### Completion gate

Complete when the identity/reconciliation contract is merged, every eligible
source observation remains traceable, named read consumers reconcile
deterministically, and reviewer-created state is unchanged. Production
promotion, backfill execution, scheduling, deployment, and Hosted acceptance
remain separate completion gates.

### Rollback or preservation rule

Retain the pre-backfill database backup, previous source package, ArcGIS and CSV
snapshots, field-level prior values, conflict records, and checkpoint. Rollback
restores the prior accepted application/database state without deleting source
history or reconstructing truth from current rows.

## Phase D — shared facility projection across reviewer and export surfaces

### Required outcome

Current status: #522/#523 completed the named reviewer/export migration for the
existing projection. Phase D remains open only for deterministic parity and
source-traceability evidence after the approved ArcGIS supplement is integrated;
it must not introduce a second projection or page-local precedence.

Use the merged Phase C facility projection across search, facility hub, review
queue, complaint detail, packet views, and exports. Every surface must consume
the same identity, field-ownership, blank, conflict, disappearance, and current-
versus-historical rules rather than reimplementing page-local precedence.

Reviewer surfaces remain concise and distinguish current-reference supplement
context from historically source-reported complaint facts. Raw `733` remains
unmapped everywhere.

### Dependencies

- Merged Phase C identity and reconciliation contract plus successful controlled
  backfill evidence.
- Existing approved reviewer/export design and accessibility requirements.
- Source-traceable read models that expose the shared projection.

### Prohibited shortcuts

- No page-local joins, fallback dictionaries, first-row selection, duplicated
  precedence logic, or source-specific display forks.
- No silent replacement of historical complaint context with current ArcGIS
  values.
- No raw provenance internals moved into the primary reviewer tier.

### Tests

- Cross-surface contract tests proving every named consumer uses the shared
  projection and renders the same governed identity/value state.
- Conflict, blank, disappearance, duplicate, current/historical, and unresolved
  `733` regression tests.
- Route, export, print, accessibility, responsive, zoom, and keyboard tests.

### Evidence

- Deterministic route and export assertions linked to the exact Phase C contract,
  source snapshots, backfill manifest, database state, and application SHA.
- Automated screenshots/text/export captures for populated, blank, conflict,
  duplicate, unavailable, and unresolved-code states.
- Reconciliation showing every named consumer uses the shared projection.

### Completion gate

Complete when search, facility hub, review queue, complaint detail, packet views,
and exports pass shared-projection and source-traceability assertions with no
page-local ownership or precedence divergence.

### Rollback or preservation rule

Preserve the last accepted projection/read model, source snapshots, backfill
manifest, and prior application release. A consumer failure must not rewrite
source history or authorize a page-local fallback.

## Phase E — source-to-screen and operator reconciliation under #453/#477

### Required outcome

Extend Issue #453 source-to-screen coverage through both source-specific
snapshots, the shared facility projection, approved PostgreSQL values, read
models, every named user surface, exports, and operator reports. Reuse the
closed #477 read-only dashboard and stable package boundary without reopening or
expanding #477. Any new ArcGIS-specific diagnostic contract, and any minimum
operational action needed later to safely control refresh/backfill jobs, requires
separate issue authorization.

Operator diagnostics must show source family and snapshot identity, separate
query/export observations, content and schema state, row/Facility ID
reconciliation, duplicate groups, conflicts, disappearance, drift, rejected
candidates, last accepted/prior accepted state, backfill/checkpoint state, and
failures without exposing raw records or secrets.

### Dependencies

- Completed Phase D shared-projection integration and Phase C reconciliation.
- Existing Issue #453 contract adapter and the completed Issue #477 production
  authorization boundary.
- Separately approved permissions and finite job/action contracts for any
  minimum operational action.

### Prohibited shortcuts

- No duplicated coverage calculation in the dashboard or page-local consumer.
- No operator action inferred from read access. Begin with read-only monitoring;
  no broad job console, raw source viewer, arbitrary command, silent retry, or
  auth bypass.
- No coverage claim based only on PostgreSQL row presence or route success.

### Tests

- Deterministic producer/adapter/consumer contract tests for both source
  families, identity, field, stage, route, export, conflict, disappearance,
  duplicate, drift, rejected-candidate, and unresolved-code coverage.
- Authorization tests proving authentication before reads and action-specific
  operator permission before every mutation.
- Fail-closed unavailable/invalid/stale/partial package tests and bounded action
  state-machine tests where authorized.
- Automated responsive, keyboard, accessibility, print, CSV, and no-secret UI
  evidence.

### Evidence

- Versioned source-to-screen package linked to exact program/ArcGIS snapshots,
  backfill, database, projection, and deployed commit identities.
- Route and authorization assertion results, screenshots, text/CSV captures,
  manifest hashes, and reconciliation summaries.
- Explicit unavailable, blocked, partial, failed, and retry-eligible states.

### Completion gate

Complete when every named source-to-screen path reconciles, the operator can
diagnose failures through read-only monitoring, authorization fails closed, and
automated evidence contains no credentials, assertions, cookies, headers,
private host details, or raw sensitive records. Separately authorized actions,
if any, must pass their own finite state and permission gates.

### Rollback or preservation rule

Retain the last valid coverage package and job history. A producer, adapter,
authorization, or action failure must not change the active source or erase
prior evidence; disable the affected action while preserving read-only status.

## Phase F — separate governed refresh and checkpoint recovery under #478

### Required outcome

Under Issue #478, implement separate governed program-source and ArcGIS refresh
workflows through discovery, immutable snapshot retrieval, normalization,
validation, accepted-pointer update, reconciliation, evidence publication, and
notification. Record attempts and finite state, prevent unsafe overlap with
locks, persist checkpoints, and support bounded recovery and eligible retries.
Any controlled backfill remains a separately gated downstream stage.

Cadence must be justified by measured source behavior and published limits.
Refresh must compare normalized content and schema/identity signals, not catalog
timestamps alone.

### Dependencies

- Completed Phases A-E and accepted source-specific lifecycle, identity,
  reconciliation, shared-projection, and monitoring contracts.
- Approved cadence, lock ownership/expiry, checkpoint, retry classification,
  notification, retention, disappearance, and recovery policies.
- Human-operated deployment/rollback procedure for the target runtime.

### Prohibited shortcuts

- No overlapping run, timestamp-only no-op decision, unbounded retry, automatic
  acceptance of drift, physical deletion, or cleanup without retention policy.
- No resume from an unvalidated or mismatched checkpoint.
- No replacement of either source family's previous accepted snapshot after a
  failed run and no cross-source pointer update from a single-source failure.
- No schedule is enabled until cadence is approved.

### Tests

- Per-source schedule, lock contention/expiry, attempt state, idempotence,
  checkpoint, retry category, cancel, resume, crash recovery, and notification
  tests.
- Schema/domain drift, partial retrieval, duplicate, disappearance, source
  outage, content-no-change, content-change, backfill failure, and reconciliation
  failure tests.
- End-to-end deterministic fixture runs proving exactly-once activation and safe
  evidence output.

### Evidence

- Per-source run manifests and timelines with source/content hashes,
  lock/attempt/checkpoint states, validation and reconciliation outcomes,
  actions, and safe failure summaries.
- Proof that unchanged normalized content causes no backfill and that changed
  content cannot activate before all gates pass.
- Recovery evidence from representative interrupted stages.

### Completion gate

Complete when scheduled runs cannot overlap, all stages are observable and
recoverable, unchanged and changed content are distinguished deterministically,
accepted-pointer changes are validation-gated, reconciliation is mandatory,
notifications are safe, and failures preserve both source families' prior
accepted snapshots and database state.

### Rollback or preservation rule

Retain immutable source versions, manifests, attempts, checkpoints, run history,
and the prior accepted database/application release according to approved
policy. Rollback selects complete previously accepted source snapshots; it
never refetches or rebuilds historical truth from mutable current state.

## Phase G — production deployment, Hosted acceptance, and final release

### Required outcome

Merge all required implementation phases through normal review, deploy the
exact accepted merge SHA through the human-operated release process, verify
application and database health without recreating PostgreSQL, and run automated
Hosted acceptance against the deployed production-auth path. Reconcile the
deployed program and ArcGIS snapshots, shared facility projection, PostgreSQL
state, source-to-screen package, operator diagnostics, separate refresh state,
named reviewer routes, exports, and evidence manifests.

After all required checks, deployment verification, automated Hosted acceptance,
documentation, and issue completion gates pass, record the final Build Week SHA
and move tag `openai-build-week-2026` to that exact accepted SHA.

### Dependencies

- Completed and merged Phases A-F with required CI checks passing.
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
- Final documentation and issue linkage for #518, #482, #453, #477, #478, and
  #516.

### Completion gate

Complete only when all required phases are merged, the exact merge SHA is
deployed, automated Hosted acceptance passes without auth or evidence bypass,
runtime/source/database reconciliation passes, required issues satisfy their
approved completion criteria, and final documentation is accepted. Until then,
the final Build Week SHA and release remain pending.

### Rollback or preservation rule

Keep the previous application release with its Compose file, the host-local
environment, PostgreSQL data and backup, last accepted source package, and
evidence. Roll back the application and complete source-family accepted-pointer
set together under the approved runbook; never discard immutable snapshots,
field provenance, conflicts, checkpoints, or the prior accepted release.

## Issue linkage and state

- **#490:** completed historical evaluation evidence; remains complete and is
  not reopened or recharacterized as production adoption.
- **#518:** completed the Phase B ArcGIS snapshot lifecycle, source-specific
  identity, validation, accepted/prior-accepted pointers, and atomic rollback.
  It did not own reviewer integration or canonical backfill.
- **#482:** #521-#523 completed the shared projection, named reviewer/export
  consumers, and bounded existing backfill. #482 now extends the shared
  read-only projection to accepted TransparencyAPI primary and ArcGIS
  supplementary snapshots with CKAN/program and complaint history retained.
  It does not execute a production backfill.
- **#453:** remains open for blocked Hosted evidence and additional ArcGIS
  source-to-screen verification.
- **#477:** closed and repository-complete for the supported read-only operator
  dashboard. Future ArcGIS coverage may use its stable package boundary, but any
  new diagnostics or operational action require separate issue authority.
- **#478:** owns separate source refresh workflows, locking, attempts,
  checkpoints, recovery, retries, reconciliation, notifications, and approved
  cadence.
- **#516:** governs this completion-scope alignment and records Phase A as
  complete with **SUPPLEMENT**. After this governance correction merges, #516
  can close without marking any later implementation, deployment, or acceptance
  phase complete.

No new issue is required for the next step: proceed with open Issue #518. Issue
state changes occur only after the applicable implementation, deployment,
evidence, and review gates pass.

## Final Build Week release rule

The pre-Build Week baseline remains
`bb5b1246fbf677a328c70abad48af3023fa1ebb0`. The first eligible Build Week
commit remains `508102077ec57dcf673142620e412ad2bf7078b1`. The current deployed
checkpoint is `d7e9b1fff9e1826c3387a7313777d14c1480d3b4`, but the final Build Week
release is pending.

The final release must include this complete dual-source ArcGIS supplement
sequence and may be named only after every required phase is merged, deployed,
and accepted. Tag `openai-build-week-2026` must eventually point to that exact
final accepted SHA, not to the current checkpoint.
