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
`facility-reference`, and `preserved-artifacts`. Use `-BatchSize 1..1000` for
transaction grouping. Apply additionally requires both an explicit
`-MaxFacilities 1..1000` per-run bound and `-CheckpointFile <path>`;
`-Restart` explicitly starts a new checkpoint selection. Writes require
explicit `-Apply`, and apply accepts only `-Operation facility-reference`.
The `all` and `preserved-artifacts` operations remain dry-run diagnostics and
cannot write complaint-derived records.

The Python entry point exposes the equivalent `--facility-number`,
`--facility-number-file`, `--all-existing`, `--operation`, `--batch-size`,
`--max-facilities`, `--checkpoint-file`, `--restart`, `--dry-run`, and
`--apply` arguments.

Output is limited to candidate, excluded, examined, eligible, intended-update,
updated, unchanged, skipped, conflicted, warning, and failed counts. It does not print raw paths, source
URLs, report narrative, database values, or credentials. A configuration error
returns exit code 2; an isolated facility failure or safe runtime failure
returns exit code 1.

## Prerequisites and safeguards

- The hosted database migrations must already be current.
- Approved real facility-reference rows must be preloaded before an operation
  that requests facility-reference enrichment.
- Preserved-artifact processing requires the stored raw path to be available to
  the runtime and its bytes to match the stored SHA-256.
- Dry-run uses rollback and is the default. Apply validates reference identity
  before writes, processes at most the explicit per-run bound, preserves
  stable source-derived identities and the original import batch, and continues
  after an isolated facility failure.
- Version 2 checkpoints freeze the selected public Facility IDs and the exact
  operation/selector, write through an atomic durable replacement, retain safe
  per-Facility-ID failure-attempt counts, and reject mismatched resume requests.
  A completed facility transaction commits before its checkpoint completion is
  recorded, so interruption can cause an idempotent repeat but cannot cause the
  checkpoint to claim an uncommitted update.
- Repeating apply with unchanged inputs is idempotent. Checkpoint/resume skips
  completed Facility IDs, retries failed IDs without silently dropping them,
  and excludes newly appearing all-existing rows until a deliberate restart.
- Only canonical `facility_type`, `county`, and `status` allocations can be
  enriched. The command does not alter reviewer-created notes, status,
  decisions, or continuity state and does not activate ArcGIS, retrieve a live
  source, schedule work, or expose an unrestricted mutation path.

For the QNAP runtime, `-QnapContainer` passes the same arguments to the existing
app service defined by `docker-compose.qnap.yml`; it does not alter the host,
container configuration, environment file, or mounts.

## Validation coverage

Fixture and unit coverage proves exact field/date extraction, approved-source
precedence and conflicts, missing-value preservation, dry-run/apply/repeat,
explicit apply bounds, durable checkpoint/resume behavior, interrupted-run
recovery, isolated failures, unchanged raw
traceability, stable identities/import scope, preserved reviewer-created state
and audit history, reviewer-detail visibility, and ordinary retrieval parity.
Tests use local source-shaped fixtures and doubles only.
