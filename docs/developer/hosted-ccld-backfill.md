# Hosted CCLD Refresh And Backfill

## Purpose and boundary

The hosted CCLD refresh repairs deterministic source-derived fields through one
shared preparation path used by ordinary controlled retrieval and the
existing-data backfill. It is CCLD-only. Backfill reads already-preserved raw
complaint artifacts and approved facility-reference rows; it never downloads a
report, uses browser automation, or changes reviewer-created state.

No schema migration is required. The canonical fields, source traceability,
reviewer-created state, audit history, and import-scope columns already exist.

## Field ownership and precedence

- Explicit complaint-report `FACILITY TYPE` is extracted, including a numeric
  source code. It is the facility-type fallback when no approved nonblank
  reference value exists.
- Approved facility-reference observations are adapted to the shared governed
  facility projection. Its field rules select the newest eligible nonblank
  facility type, county, and status; this command has no independent first-row-
  wins merge.
- A valid structured `VISIT DATE` and explicit investigation narrative are
  eligible first-activity evidence. The earliest valid date wins; report date
  alone is not eligible.
- Incoming missing or blank values never erase populated canonical values.
- Differing nonblank governed values follow the ownership rule and record the
  prior value, selected value, source field, resource ID, dataset slug, and
  snapshot/access metadata in source traceability.
- Eligible same-precedence observations at the same time that disagree remain
  an explicit unresolved conflict. The canonical field stays unchanged; input
  order never chooses a winner.
- Other facility-reference fields remain reference-only unless separately
  governed.

Production/backfill enrichment accepts only configured official CCLD facility-
reference resources preloaded in `hosted_facility_reference_records`. Fixture,
mock, sample, synthetic, and test-only resource identities are rejected.

## Command interface

The PowerShell wrapper defaults to dry-run:

```powershell
.\scripts\backfill-hosted-ccld-data.ps1 -FacilityNumber 425802141 -Operation all -DryRun
```

Selectors are mutually exclusive: `-FacilityNumber`,
`-FacilityNumberFile <path>`, or `-AllExisting`. Operations are `all`,
`facility-reference`, `preserved-artifacts`, and
`canonical-complaint-observations`. Use `-BatchSize 1..1000` for transaction
grouping. Apply additionally requires both an explicit `-MaxFacilities 1..1000`
per-run bound and `-CheckpointFile <path>`; `-Restart` explicitly starts a new
checkpoint selection. Writes require explicit `-Apply`, and apply accepts only
`-Operation facility-reference`, `-Operation preserved-artifacts`, or
`-Operation canonical-complaint-observations`. The `all` operation remains a
dry-run diagnostic and cannot write.

`preserved-artifacts` and `canonical-complaint-observations` replay the same
preserved-document preparation path and therefore use the same preserved-
artifact provenance identity. Switching between those equivalent operations
does not create a provenance-only source-derived update.

The Python entry point exposes the equivalent `--facility-number`,
`--facility-number-file`, `--all-existing`, `--operation`, `--batch-size`,
`--max-facilities`, `--checkpoint-file`, `--restart`, `--dry-run`, and
`--apply` arguments.

For a bounded residual-idempotence investigation, `-DiagnoseDifferences`
requires `-Operation preserved-artifacts` and an explicit Facility ID or
Facility-ID file. It rejects `-AllExisting`, apply, checkpoint, restart, and
maximum-facility options. This non-default mode performs only preserved-artifact
reads and preparation, compares the exact candidate values used by the import
write decision, and emits one deterministic JSON document. Each difference
contains the public Facility ID, entity type, stable source-record key, and
differing field paths. String and structured values are represented only by
type, length or count, and SHA-256; complaint and allegation narratives are not
printed. Reviewer-created state and audit tables are outside the diagnostic read
path.

The equivalent direct Python forms are:

```powershell
python scripts/backfill_hosted_ccld_data.py --facility-number <facility-id> --operation preserved-artifacts --diagnose-differences
python scripts/backfill_hosted_ccld_data.py --facility-number-file <facility-id-file> --operation preserved-artifacts --diagnose-differences
```

Diagnostic mode is a third mutually exclusive mode: the wrapper passes
`--diagnose-differences` without `--dry-run` or `--apply`. Ordinary wrapper
invocation still passes `--dry-run`, and explicit `-Apply` still passes
`--apply`.

Backfill mode output is limited to candidate, excluded, examined, eligible,
intended-update, updated, unchanged, skipped, conflicted, warning, and failed
counts. Diagnostic mode instead emits one deterministic JSON document containing
redacted differences. Neither mode prints raw paths, source URLs, report
narrative, database values, or credentials. A configuration error returns exit
code 2; an isolated facility failure or safe runtime failure returns exit code
1.

## Prerequisites and safeguards

- The hosted database migrations must already be current.
- Approved real facility-reference rows must be preloaded before an operation
  that requests facility-reference enrichment.
- Preserved-artifact processing requires the stored raw path to be available to
  the runtime and its bytes to match the stored SHA-256.
- Dry-run uses rollback and is the default. When facility-reference enrichment
  is requested, apply validates reference identity before writes. Every apply
  processes at most the explicit per-run bound, preserves stable source-derived
  identities and the original import batch, and continues after an isolated
  facility failure.
- Version 2 checkpoints freeze the selected public Facility IDs and the exact
  operation/selector, write through an atomic durable replacement, retain safe
  per-Facility-ID failure-attempt counts, and reject mismatched resume requests.
  A completed facility transaction commits before its checkpoint completion is
  recorded, so interruption can cause an idempotent repeat but cannot cause the
  checkpoint to claim an uncommitted update.
- Repeating apply with unchanged inputs is idempotent. Checkpoint/resume skips
  completed Facility IDs, retries failed IDs without silently dropping them,
  and excludes newly appearing all-existing rows until a deliberate restart.
- Preserved allegation identities first reuse an existing sibling whose source-
  derived allegation text, category, finding, and confidence are unchanged.
  Exact generated identity and deterministic source occurrence then reconcile
  unmatched allegations, events, and repeated extraction-audit rows. A newly
  extracted allegation receives a collision-free identity and therefore cannot
  shift the stable identities or values of unchanged siblings.
- Before a write decision, preserved-artifact provenance is stabilized only when
  the complete final source-record key set and every importer-visible governed
  value other than artifact identity exactly match persisted state. Superseded
  duplicate projections therefore cannot rotate provenance alone; a new,
  removed, or genuinely changed final projection retains newly generated
  provenance and remains an update.
- Only canonical `facility_type`, `county`, and `status` allocations can be
  enriched. The command does not alter reviewer-created notes, status,
  decisions, or continuity state and does not activate ArcGIS, retrieve a live
  source, schedule work, or expose an unrestricted mutation path.

For the QNAP runtime, `-QnapContainer` passes the same arguments to the existing
app service defined by `docker-compose.qnap.yml`; it does not alter the host,
container configuration, environment file, or mounts.

## Validation coverage

Fixture and unit coverage proves exact field/date extraction, approved-source
precedence and conflicts, missing-value preservation, preserved-artifact and
canonical-observation dry-run/apply/repeat behavior, explicit apply bounds,
durable checkpoint/resume behavior, interrupted-run recovery, isolated failures,
unchanged raw traceability, stable identities/import scope, preserved reviewer-
created state and audit history, stable child identity when extraction adds a
sibling, semantic allegation identity when a sibling is inserted, final-
projection artifact identity with duplicated document projections, equivalent
preserved-operation provenance, reviewer-detail visibility, SELECT-only redacted
difference diagnosis, and ordinary retrieval parity. Tests use local source-
shaped fixtures and doubles only.
