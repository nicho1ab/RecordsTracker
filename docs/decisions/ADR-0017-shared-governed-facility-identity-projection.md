# ADR-0017: Use One Read-Only Governed Facility Identity Projection

## Status

Accepted

## Context

RecordsTracker currently has two eligible facility-information paths with
different semantics. Program-reference rows describe a current facility
reference and preserve resource and snapshot metadata. Canonical facility rows
linked to complaint reports preserve historically reported complaint context
and source-document traceability. Existing pages and exports combine subsets of
those values independently, which can produce different facility names, types,
addresses, counties, capacities, statuses, or missing-value behavior for the
same public Facility ID.

Phase A evaluated the governed ArcGIS source and concluded **SUPPLEMENT**, not
replacement or production activation. ArcGIS has distinct snapshot-plus-object
row identity, duplicate Facility IDs, query/export differences, fields without
governed domains, and unresolved authority and terms gates. It cannot enter the
runtime projection in this slice.

## Decision

Use one shared, deterministic, read-only facility identity projection for the
eventual reviewer, packet, export, and operator consumers. The first Issue #521
slice implements the projection plus only an authorized service-level read over
existing program-reference and complaint-linked canonical facility data.

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
status, full address, city, state, ZIP, county, capacity, administrator,
licensee, telephone, and regional office. Coordinates are excluded.

Each field result carries a safely selected display value when applicable, a
normalized comparison value, semantic state, source row and snapshot identity,
observation time, conflict flag, every eligible alternative observation, and
current-reference or historical complaint context. The canonical internal
identity uses the same result shape but is always `internal_only` and has no
display value.

Semantic states are `populated`, `blank`, `absent`, `unavailable`,
`unresolved_raw_code`, `conflicting`, `internal_only`, and `invalid`. Pages may
later translate those states into approved user-facing text, but page strings
are not stored in or accepted by the projection.

## Field-level precedence and reconciliation

Precedence is defined separately for every supported field in
`DATA_CONTRACT.md`. For the current-reference read model, the newest eligible
nonblank program-reference observation is the first presentation candidate and
the complaint-linked observation is the historical fallback. This does not
make the program source a global canonical owner and does not update stored
canonical values.

The following invariants apply to every field:

- Blank never erases an eligible nonblank value.
- Identical normalized observations reconcile while retaining all provenance.
- Conflicting nonblank originals and their contexts are retained even when a
  field rule selects a current display candidate.
- Current-reference values never rewrite complaint-time observations.
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

- Existing routes, templates, packets, prints, and exports do not yet consume
  the projection and can still differ until their sequenced migration.
- A tied conflict intentionally yields no selected display value.
- Production data quality remains bounded by eligible existing program and
  complaint-linked observations.

## Migration sequence

1. Merge and validate this read-only projection contract.
2. In a separate Issue #482 child, migrate authorized reviewer and facility
   read models and then packet/export consumers without duplicating precedence.
3. Add controlled PostgreSQL backfill only after separate schema, dry-run,
   apply, checkpoint, recovery, provenance, and reviewer-state-preservation
   authorization.
4. Add ArcGIS accepted snapshots only after Issue #518 lifecycle, authority,
   terms, identity, and acceptance gates pass; ArcGIS remains a supplement.
5. Extend Issue #453/#477 reconciliation and Issue #478 governed refresh only
   after the shared consumer and persistence phases are accepted.

At every step, rollback preserves the previous application release, existing
program and complaint observations, reviewer-created state, and any prior
accepted snapshot. A failed later phase does not alter this read-only contract
or authorize a page-local fallback.

## Non-goals

This decision and implementation do not add schemas, migrations, backfill,
ArcGIS retrieval or activation, source scheduling, operator actions, hosted or
QNAP deployment, Cloudflare changes, route/template migration, print/export
changes, database writes, or legal, statewide, freshness, or completeness
conclusions.
