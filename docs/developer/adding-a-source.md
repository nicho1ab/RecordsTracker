# Adding a Source

## Required steps

1. Create `src/ccld_complaints/connectors/<source>/`.
2. Implement the source connector contract.
3. Add source documentation.
4. Add at least three raw fixtures.
5. Add expected JSON fixture outputs.
6. Add connector contract tests.
7. Update known limitations.
8. Update user docs if new fields or behavior are exposed.

## Required review

A source connector cannot be accepted until it passes:

- Unit tests
- Fixture tests
- Data contract validation
- Accessibility review for any user-facing output
- Documentation checks

## Local public-source CSV profiling

Before proposing a connector, import path, schema, migration, hosted workflow,
or canonical field for local public-source CSV examples, run the local profiler
against the ignored source workspace:

```powershell
.\scripts\profile-public-source-csvs.ps1
```

The profiler reads CSV files recursively from `data\raw\source-profiling`, skips
non-CSV files, does not modify raw files, does not contact the internet or cloud
services, and writes ignored summaries to `data\processed\source-profiling` plus
`data\logs\source-profiling.log`. Use the output only as local discovery input.
It does not import data into SQLite or the hosted scaffold, create canonical
fields, approve schema or migration work, add connectors, or validate source
completeness.

Do not commit raw downloaded CSVs, PDFs, HTML pages, or full generated profiling
outputs. Committed profiler fixtures must be tiny, synthetic, and stored under
the test fixture area.

## CCLD FacilityReports baseline

The CCLD connector discovers public FacilityReports URLs from the facility detail page for facility `157806098`. Discovery normalizes each rendered report link into a source document candidate with source name, facility number, report index, source URL, visible report date, and optional discovery timestamp. Duplicate URLs and duplicate report indexes are removed before candidates are returned.

Discovery does not download or parse each report body. Fetching, raw storage, extraction, normalization, validation, and emission remain separate connector contract steps.

The initial deterministic extraction fixture targets report index `3`. It extracts labeled HTML fields deterministically and normalizes them into the existing facility, source document, complaint, allegation, and extraction audit records without adding source-specific canonical columns.

The initial single-facility ingestion helper returns validated records in memory and records per-candidate failures. Offline tests should inject fixture loaders for report bodies; live fetching is only used when no loader is provided, and raw content is stored before extraction.
