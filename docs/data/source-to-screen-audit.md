# Source-to-screen audit

The source-to-screen audit inventories complaint, facility, and shared fields from
repository contracts through storage and current reviewer surfaces. It is diagnostic and
aggregate-only; it does not remediate identified product gaps.

## Local audit

From a PowerShell prompt:

```powershell
Set-Location '<Repo Path>\'
.\.venv\Scripts\python.exe -m ccld_complaints.source_to_screen_audit --mode local --output-dir data/processed/source-to-screen-audit/local-pre-pr --write-tracked-baseline
```

Local mode inspects repository schemas, explicit mappings, retained representative
artifacts, governed fixtures, and the configured SQLite file when it exists. It never
silently substitutes tiny fixtures for unavailable configured data and does not require
network access.

## Runtime audit

Run this inside the deployed application container:

```sh
docker compose -f docker-compose.qnap.yml exec app python -m ccld_complaints.source_to_screen_audit --mode runtime --output-dir /app/data/processed/source-to-screen-audit/runtime-post-deploy
```

Runtime mode requires the configured PostgreSQL database. Its queries return aggregate
population counts only. The generated files must stay in the ignored processed-data
directory and must not be committed.

## Generated outputs

- `manifest.json`
- `data-element-inventory.csv`
- `data-element-inventory.json`
- `population-summary.csv`
- `null-semantics.csv`
- `facility-hub-coverage.csv`
- `complaint-detail-coverage.csv`
- `aggregate-feature-readiness.csv`
- `gap-register.csv`
- `recommended-issues.json`
- `summary.md`
- `sqlite-postgres-parity.csv`

`sqlite-postgres-parity.csv` is emitted only when both stores are available in the same
audit invocation. All other files are emitted on every successful run.

## Missing-value rules

- Numeric zero is counted only when the stored scalar is a verified numeric zero.
- Null and missing JSON keys are measured separately.
- Empty and whitespace-only strings are blank.
- Literal unknown, unavailable, not applicable, and undated states remain distinct.
- Uninspected and missing source coverage is unavailable, never zero.
- Always-null and nearly-always-null fields are flagged for follow-up.

## Classifications

- `SOURCE_NOT_PROVIDED`
- `RAW_PRESENT_EXTRACTION_MISSING`
- `EXTRACTED_CANONICAL_MAPPING_MISSING`
- `CANONICAL_IMPORT_NOT_POPULATED`
- `SQLITE_POSTGRES_DIVERGENCE`
- `STORED_QUERY_OMISSION`
- `UI_DISPLAY_OMISSION`
- `UNEXPLAINED_BLANK`
- `AGGREGATE_DATA_INSUFFICIENT`
- `FIXTURE_RUNTIME_DIVERGENCE`
- `INTENTIONALLY_INTERNAL`
- `NOT_APPLICABLE`

## Safety boundary

Reports contain stable field and gap identifiers, classifications, aggregate counts,
percentages, reviewer routes, and repository-relative evidence references. They exclude
complaint narratives, source-document bodies, record values, connection strings, tokens,
cookies, private URLs, and raw filesystem paths. Baseline generation is local-only.

## Interpretation limits

- Retained artifacts and governed fixtures establish discovery coverage; they are not
  silently treated as production population data.
- An unavailable SQLite database produces explicit unavailable coverage.
- The audit records known route/query consumers from a reviewed explicit registry; it does
  not scrape rendered reviewer pages or retain HTML.
- Aggregate readiness is conservative: missing prerequisite coverage is not a defensible
  zero.
- Standard local and runtime modes do not compare fixture rows directly. The
  `FIXTURE_RUNTIME_DIVERGENCE` classification is available for an equivalent governed
  cross-store comparison, but the audit does not infer that divergence from unrelated
  fixture and runtime scopes.
- PostgreSQL JSON population queries require confirmation through the post-deployment
  runtime command; local adapter tests use SQLite JSON support.
