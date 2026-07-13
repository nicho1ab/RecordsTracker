# CCLD Connector

This connector is responsible for discovering, fetching, storing, extracting, and normalizing public CCLD facility report data.

The first implementation should focus on FacilityReports URLs in this format:

```text
https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=<facility_number>&inx=<index>
```

The connector must follow `SOURCE_CONNECTOR_CONTRACT.md`.

## Facility detail discovery

Discovery starts from the public facility detail page for facility `157806098` and identifies rendered `FacilityReports` links that match the canonical report URL format. Each discovered link is normalized into a source document candidate with:

- `source_name`
- `facility_number`
- `report_index`
- `source_url`
- `discovered_report_date`
- `discovered_at`, when the discovery run provides one

Discovery removes duplicate report URLs and duplicate report indexes. It does not download or parse each report body; report fetching and extraction remain separate connector steps.

If a live facility detail response does not contain rendered report anchors, the connector falls back to the public report-list API used by the facility detail page and creates the same candidate URL shape from the returned report array indexes.

## Single-facility ingestion orchestration

`ingest_facility_reports_for_facility()` runs one facility through the connector contract:

1. Discover report candidates.
2. Load a report document through an injected fixture loader, or fetch live content and store raw bytes before extraction.
3. Extract deterministic report fields.
4. Normalize records to the canonical data contract.
5. Validate normalized records against JSON schemas.
6. Emit records to SQLite when the connector is configured with a database path.

The function returns in-memory normalized records and per-candidate ingestion failures. Missing fixture content and extraction or validation errors are recorded in the result instead of being hidden.

The optional `limit` argument restricts the number of discovered report candidates selected for fetch or fixture loading. This lets users test with one or a few reports before requesting all discovered reports. The optional `max_requests` argument is a safety guard that prevents accidental large live fetches when a selected candidate set is larger than intended.

## Explicit live fetch command

Live CCLD requests are user-invoked through `scripts/run-ccld-live-fetch.ps1`. The command discovers reports for facility `157806098` by default, downloads the selected report bodies to `data/raw/ccld`, and ingests the saved raw files into SQLite for Datasette review. The default fetches one report; users can provide `-Limit 3` or `-Limit 5` for a small selected batch, or combine `-All` with an intentionally raised `-MaxRequests` value.

The live command prints an external-site warning, uses a clear user agent, applies a reasonable timeout, limits report requests unless the user chooses all discovered reports, enforces the max-request guard, and does not use an aggressive retry loop. Automated tests should inject fixture HTML and fake report fetchers instead of making live web requests.

Before discovery or report fetching, the live command reports facility identifier
intake details: accepted facility identifiers, duplicate identifiers ignored, and
blank, comment, or header values ignored from small text or CSV input files.
Facility identifiers must contain digits only; invalid values are rejected before
the connector makes public web requests.

After discovery and fetching, the live command reports facilities with records
discovered, facilities with no records discovered, discovery failures, candidates
selected, reports skipped by limit, reports fetched, records written, and report
failures. Per-facility summary lines include a run-state label such as records
written, no records discovered, skipped by limit, partial report failures, or
report failures.

## Initial deterministic extraction

The first implemented fixture covers facility `157806098` with report index `3`.

The extractor reads the public FacilityReports HTML response, preserves the raw source file, and deterministically extracts labeled fields from the report text:

- Facility number and facility name
- Report type, report date, date signed, and visit date, including split label/value date layouts
- Complaint received date, including inline narrative phrase variants, and complaint control number
- The earliest deterministic investigation activity date from a bounded
  investigation-findings sentence, without substituting report date
- One bounded `investigation_activity` event for the governed activity sentence,
  including event date, type, text, and source section
- Facility capacity and the literal regional-office label from the complaint
  report facility/header sections
- Present-but-blank facility address and city elements as explicit extraction
  audit states; these fields remain unallocated canonically pending separate work
- Allegation text, including allegation and investigation finding heading variants and lowercase continuation lines in wrapped layouts
- Normalized finding, including explicit `Finding:` labels, `Finding -` inline labels, split `Finding` label/value layouts, and source punctuation variants
- Deterministic delay metrics for received-to-visit, received-to-report, and report-to-signed dates when both dates are available
- Review delay flags for records that may need closer review

The normalized output uses the canonical entities in `DATA_CONTRACT.md`; the CCLD facility number is stored as `external_facility_number` on the facility record.

The connector does not infer `first_investigation_activity_date` from report date.
It normalizes a narrative date only when governed investigation wording contains
a deterministic activity cue and parseable date. If no first activity date is
available, the normalized complaint record marks `missing_first_activity_date`.
Report date is used as a delay review proxy only when no first activity date or
visit date is available.

Target extraction audit rows link to the retained source document and preserve a
bounded source section plus source text. Generated evidence hashes that source
text instead of emitting it.

## Focused extraction-gap evidence

From `<Repo Path>\`, run the local governed-fixture adapter:

```powershell
.\.venv\Scripts\python.exe -m ccld_complaints.extraction_gap_evidence --mode local --output-dir <path>
```

In the configured runtime, run the aggregate-only PostgreSQL adapter:

```powershell
python -m ccld_complaints.extraction_gap_evidence --mode runtime --output-dir <path>
```

The command writes `manifest.json`, `field-results.csv`,
`artifact-results.csv`, `gap-status.csv`, `traceability-results.csv`, and
`summary.md`. It does not emit complaint narratives, raw artifact bodies,
connection strings, private URLs, secrets, synthetic facility records, or
user-specific paths. Runtime population is reported separately from governed
extractor capability. Existing imported PostgreSQL rows require regeneration
and reimport before newly extracted values appear; no safe automated in-place
refresh command is currently implemented.
