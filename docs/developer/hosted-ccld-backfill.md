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
- The newest approved facility-reference snapshot/access row owns nonblank
  hosted canonical facility type, county, and status.
- A valid structured `VISIT DATE` and explicit investigation narrative are
  eligible first-activity evidence. The earliest valid date wins; report date
  alone is not eligible.
- Incoming missing or blank values never erase populated canonical values.
- Differing nonblank governed values follow the ownership rule and record the
  prior value, selected value, source field, resource ID, dataset slug, and
  snapshot/access metadata in source traceability.
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
bounded work and `-CheckpointFile <path>` to record completed facility numbers;
`-Restart` ignores an existing checkpoint. Writes require explicit `-Apply`.

The Python entry point exposes the equivalent `--facility-number`,
`--facility-number-file`, `--all-existing`, `--operation`, `--batch-size`,
`--checkpoint-file`, `--restart`, `--dry-run`, and `--apply` arguments.

Output is limited to examined, eligible, updated, unchanged, skipped,
conflicted, warning, and failed counts. It does not print raw paths, source
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
  before writes, processes each facility in an isolated transaction, preserves
  stable source-derived identities and the original import batch, and continues
  after an isolated facility failure.
- Repeating apply with unchanged inputs is idempotent. Checkpoint/resume skips
  completed facility numbers without treating them as failures.

For the QNAP runtime, `-QnapContainer` passes the same arguments to the existing
app service defined by `docker-compose.qnap.yml`; it does not alter the host,
container configuration, environment file, or mounts.

## Validation coverage

Fixture and unit coverage proves exact field/date extraction, approved-source
precedence and conflicts, missing-value preservation, dry-run/apply/repeat,
batch and checkpoint/resume behavior, isolated failures, unchanged raw
traceability, stable identities/import scope, preserved reviewer-created state
and audit history, reviewer-detail visibility, and ordinary retrieval parity.
Tests use local source-shaped fixtures and doubles only.
