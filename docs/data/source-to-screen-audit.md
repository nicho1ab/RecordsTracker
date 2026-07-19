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

## Contract `1.0.0` coverage package

The Issues #453/#477 producer uses the same module entry point and the governed
field IDs in `source-to-screen-inventory.md`. A fixture-only local package can be
generated without a source call or database connection:

```powershell
Set-Location <repo-root>
.\.venv\Scripts\python.exe -m ccld_complaints.source_to_screen_audit `
  --coverage-fixture tests\fixtures\source_to_screen_coverage\scenarios.json `
  --coverage-scenario complete-balanced `
  --generated-at 2026-07-19T18:00:00Z `
  --output-dir data\processed\source-to-screen-audit\issue-453-fixture
```

The fixed time is for deterministic fixture comparison only. Ordinary generation
captures one current UTC `Z` timestamp. The programmatic
`generate_coverage_package()` boundary accepts the same allowlisted aggregate
mapping from a governed read-only adapter. It does not retrieve a source, start a
job, import data, or mutate a database.

Contract package artifacts are:

- required `manifest.json`;
- required aggregate-only `coverage-report.json`;
- `operator-facility-index.jsonl` when that read boundary is available;
- `operator-job-index.jsonl` when that read boundary is available; and
- aggregate-only `aggregate-coverage.csv`.

The manifest does not list or hash itself. It records the byte count, lowercase
SHA-256, media type, and availability of each payload artifact. JSON uses sorted
keys and compact canonical serialization. JSONL uses one canonical object per
LF-terminated line. CSV uses its documented fixed header and LF line endings.

The report identity is `coverage-report-v1-<sha256>` over canonical JSON holding
the contract major version, evaluation ID, ordered source snapshot IDs,
criteria-set ID, scope ID, and producer schema ID. `generated_at` is excluded.
The package schema is
`schemas/issues-453-477-coverage-report-v1.schema.json`, and the producer schema
ID is `issues-453-477-coverage-report-v1`.

## Runtime audit

Run this inside the deployed application container:

```sh
docker compose -f docker-compose.qnap.yml exec app python -m ccld_complaints.source_to_screen_audit --mode runtime --output-dir /app/data/processed/source-to-screen-audit/runtime-post-deploy
```

Runtime mode requires the configured PostgreSQL database. Its queries return aggregate
population counts only. The generated files must stay in the ignored processed-data
directory and must not be committed.

## Generated outputs

The following files are the pre-contract structural audit outputs. They remain
available for the existing local/runtime audit mode:

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

Contract `1.0.0` maps those structural inventory dispositions into these closed
terminal categories without collapsing failure to generic missing:

- `present_and_populated`
- `present_but_not_extracted`
- `extracted_but_not_allocated`
- `allocated_but_not_imported`
- `stored_but_not_read`
- `read_but_not_rendered`
- `rendered_incorrectly`
- `present_blank`
- `source_label_absent`
- `source_artifact_unavailable`
- `unsupported_layout`
- `conflicting_sources`
- `intentionally_internal`
- `not_applicable`

Every inventory field is reported at source presence, extraction,
normalization, canonical allocation, PostgreSQL population, read-model exposure,
complaint-page rendering, and facility-hub rendering. Each eligible field/stage
distribution balances across successful, blank, absent, unavailable,
unsupported, conflict, failure, and skipped. A non-applicable surface has an
eligible count of zero rather than a fabricated missing result. The aggregate
adapter may report counts greater than one for a catalog field/stage and a
separate terminal classification eligible count; reconciliation requires each
stage and terminal distribution to balance exactly.

Operational refresh, retrieval, import, preserved-artifact, hash, checkpoint,
job, processing, and change states are separately aggregated. They never infer a
coverage classification. Reconciliation emits all 16 stable invariant IDs and
fails closed without changing counts. Release assessment applies the explicit
`criteria_set_id` baselines, thresholds, observed regression counts, and any
input exception ID; the producer never approves an exception.

## Safety boundary

Reports contain stable field and gap identifiers, classifications, aggregate counts,
percentages, reviewer routes, and repository-relative evidence references. They exclude
complaint narratives, source-document bodies, record values, connection strings, tokens,
cookies, private URLs, and raw filesystem paths. Baseline generation is local-only.

The contract report and aggregate CSV never contain Facility IDs. The operator
facility index contains only public Facility ID and contract-approved safe status
metadata. Input and output allowlists reject unknown fields plus narratives, raw
HTML, URLs, paths, secrets, authentication claims, container or host detail,
stack traces, SQL, and uncontrolled errors.

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
- Contract packages retain immutable generation instances by report ID. Until a
  separate retention policy is approved, policy ID and retain-until remain null,
  disposition is `pending_policy`, and no automated deletion is authorized.
- The current runtime command above remains the read-only structural PostgreSQL
  audit shape. Wiring its aggregate result plus existing operational read
  boundaries into a production-style contract generation is pending integration
  evidence; fixtures are never substituted for runtime data.
- Issue #490 remains controlling: existing program-specific sources are retained
  for the evaluated scope, every statewide candidate stays inactive, no
  statewide completeness baseline or refresh cadence is approved, and raw `733`
  remains unresolved without a descriptive facility-type label.
