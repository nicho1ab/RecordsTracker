# ADR-0017: Use One Read-Only Governed Facility Identity Projection

## Status

Accepted

## Context

RecordsTracker originally had two eligible facility-information paths with
different semantics. Program-reference rows preserved resource and snapshot
metadata. Canonical facility rows
linked to complaint reports preserve historically reported complaint context
and source-document traceability. Existing pages and exports combine subsets of
those values independently, which can produce different facility names, types,
addresses, counties, capacities, statuses, or missing-value behavior for the
same public Facility ID.

Phase A evaluated the governed ArcGIS source and concluded **SUPPLEMENT**, not
replacement. Issue #518 subsequently implemented its accepted snapshot
lifecycle. Issues #553/#554 then approved and implemented the official CCLD
TransparencyAPI as the primary current facility-reference source family. ArcGIS
keeps distinct snapshot-plus-object row identity and supplementary semantics;
CKAN/program observations are historical/controlled fallback evidence.

## Decision

Use one shared, deterministic, read-only facility identity projection for the
eventual reviewer, packet, export, and operator consumers. The first Issue #521
slice implements the projection plus only an authorized service-level read over
existing program-reference and complaint-linked canonical facility data. The
Issue #522 follow-on applies this accepted decision to the core facility lookup,
suggestion, request, hub, reviewer list/detail, packet preview/draft, and repeated
feedback-context reads through one shared presenter; it does not change the
projection decision or persistence ownership.

Issue #482 completes the source-family composition at the same read-only
boundary. An eligible active accepted TransparencyAPI snapshot is primary
current reference; an eligible active accepted ArcGIS snapshot is
supplementary; CKAN/program observations are historical fallback; and
complaint-linked observations remain complaint/report-time evidence. Reads do
not promote, accept, retrieve, or mutate snapshots.

The projection accepts a digit-only public Facility ID and an authorized corpus
scope. It keeps four identity categories separate:

1. Public Facility ID used for facility navigation and matching.
2. Internal canonical database record identity, which is intentionally not
   displayable.
3. Source-resource row identity, which is not assumed unique by Facility ID.
4. Snapshot or import-batch identity that locates the observation in time and
   provenance.

No internal or source identity may be presented as the public Facility ID.
Query-carried facility names remain navigation context only and are not inputs
to the projector.

## Field result contract

The projection supports facility name, public Facility ID, facility type,
status, Closed Date, full address, city, state, ZIP, county, capacity,
administrator, licensee, telephone, regional office, and CONTACT. CONTACT and
Facility Administrator remain separate. Coordinates are excluded.

Each field result carries a safely selected display value when applicable, a
normalized comparison value, semantic state, source row and snapshot identity,
observation time, conflict flag, every eligible alternative observation, and
current-reference, supplementary-reference, historical-reference, or historical
complaint context. The canonical internal
identity uses the same result shape but is always `internal_only` and has no
display value.

Semantic states are `populated`, `blank`, `absent`, `unavailable`,
`unresolved_raw_code`, `conflicting`, `internal_only`, `invalid`, and
`extraction_failed`. Pages may
translate those states into approved user-facing text through the shared
presenter, but page strings are not stored in or accepted by the projection.

## Field-level precedence and reconciliation

Precedence is defined separately for every supported field in
`DATA_CONTRACT.md`. For the current-reference read model, the first eligible
populated candidate is active accepted TransparencyAPI, then eligible ArcGIS
supplement, then CKAN/program historical reference, then complaint-linked
historical evidence. Prior accepted TransparencyAPI observations participate
only to preserve populated address or telephone when the active observation is
blank, absent, placeholder, or unavailable. This does not make any source a
global canonical owner and does not update stored canonical values.

The following invariants apply to every field:

- Blank never erases an eligible nonblank value.
- Identical normalized observations reconcile while retaining all provenance.
- Conflicting nonblank originals and their contexts are retained even when a
  field rule selects a current display candidate.
- Current-reference values never rewrite complaint-time observations.
- Source disappearance never implies closure or deletion.
- Current status and Closed Date remain distinct; CONTACT and Facility
  Administrator remain distinct.
- Multiple same-ID rows remain separate observations.
- Same-source, same-time conflicting values have no selected winner; database
  or input order never decides.
- A numeric facility-type value is a raw code, not a descriptive label. Raw
  `733` remains `unresolved_raw_code` unless separately governed evidence proves
  a label.
- Page-local status mappings are not promoted into shared truth.

## Authorization and production safety

The service requires the existing source-derived read permission and exact
scope before loading candidates. It reads existing tables with `SELECT` only.
It does not write source-derived, facility-reference, reviewer-created, audit,
job, checkpoint, import, or operational rows.

Fixture, demo, synthetic, sample, mock, tiny, and test-only provenance is
excluded by default. If those are the only otherwise matching observations,
the affected source family is reported unavailable rather than displayed as
production facility truth. Tests can explicitly opt in to test candidates.

## Consequences

Benefits:

- Later consumers can share one identity, precedence, state, and conflict
  contract instead of copying page-local merge rules.
- Current reference and historical complaint evidence remain usable without
  overwriting each other.
- Duplicate rows, missing fields, raw codes, and internal identities stay
  explicit and testable.
- The implementation is rollback-compatible because it adds no schema,
  migration, persisted projection, backfill, or source activation.

Tradeoffs:

- Core routes, templates, packets, print draft, and governed exports consume the
  projection, while specialized aggregate views retain their separately governed
  read models.
- A tied conflict intentionally yields no selected display value.
- Production data quality remains bounded by eligible accepted source snapshots
  and retained historical observations.

## Migration sequence

1. Merge and validate this read-only projection contract.
2. In Issue #522, migrate the authorized core reviewer and facility read models
   plus packet preview/draft without duplicating precedence; leave specialized
   aggregate views and exports for their separately bounded phases.
3. Add controlled PostgreSQL backfill only after separate schema, dry-run,
   apply, checkpoint, recovery, provenance, and reviewer-state-preservation
   authorization.
4. In Issue #482, consume eligible accepted TransparencyAPI and ArcGIS snapshots
   through the shared read-only projection; ArcGIS remains a supplement.
5. Extend Issue #453/#477 reconciliation and Issue #478 governed refresh only
   after the shared consumer and persistence phases are accepted.

At every step, rollback preserves the previous application release, existing
program and complaint observations, reviewer-created state, and any prior
accepted snapshot. A failed later phase does not alter this read-only contract
or authorize a page-local fallback.

## Non-goals

This decision and its Issue #521/#522/#482 implementation do not add schemas,
migrations, backfill, source retrieval, snapshot promotion, source scheduling,
operator actions, hosted or QNAP deployment, Cloudflare changes, export
migration, database writes, or legal, statewide, freshness, or completeness
conclusions. Issue #522 changed the named read-only core route/template and
print-presentation consumers; Issue #482 changes source composition and bounded
facility search without redesigning those surfaces.
