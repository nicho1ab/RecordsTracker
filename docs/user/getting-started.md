# Getting Started

This project creates a searchable dataset from public complaint and facility reports.

## What you can do

- Search complaint records.
- Filter by facility, date, allegation category, and finding.
- Open the original public source URL.
- Review calculated delay fields.
- Export structured data.

## Local database

Normalized ingestion results can be stored in the local SQLite database for browsing with Datasette. Stored records include source traceability fields such as source URL, raw file hash, raw path, connector name, connector version, retrieval time, and report index when available.

## Fixture-backed sample mode

From the repository root, run the bundled sample script:

```powershell
.\scripts\run-ccld-sample.ps1
```

The script initializes `data/processed/ccld.sqlite` if needed and writes the available fixture-backed CCLD sample report into SQLite. The bundled facility detail fixture discovers 40 report candidates, but only bundled fixture-backed report content is written. At present, the bundled report fixture is facility `157806098`, report index `3`. It prints the database path and the Datasette command to open it.

This mode uses bundled test fixtures only. It does not make live web requests, and it is the right first check when you want a repeatable local sample.

You can choose a different local database path:

```powershell
.\scripts\run-ccld-sample.ps1 -DbPath data\processed\sample.sqlite
```

## Live CCLD fetch mode

Live mode is explicitly user-invoked and accesses the public CCLD external site. The default is conservative: if you do not provide facility input, the script uses facility `157806098`; if you do not provide a limit, the script fetches one discovered report per facility. The workflow does not crawl statewide, expand searches, or fetch every report unless you explicitly use `-All` and set `-MaxRequests` high enough.

Start with one report so you can confirm the workflow before fetching more:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -Limit 1
```

You can also provide the facility number explicitly:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098 -Limit 1 -MaxRequests 1
```

To fetch one discovered report for two or three explicit facilities, pass multiple facility numbers. `-Limit` applies per facility, and `-MaxRequests` is the overall report-request guard:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098, 123456789 -Limit 1 -MaxRequests 2
```

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098, 123456789, 987654321 -Limit 1 -MaxRequests 3
```

For a small text or CSV file, put one facility number per line or use comma-separated values:

```text
facility_number
157806098
123456789
987654321
```

Then pass the file path:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityInputPath .\facility-numbers.csv -Limit 1 -MaxRequests 3
```

After one report per facility succeeds, try a small larger per-facility limit such as three or five reports. `-MaxRequests` must be at least as large as the total selected report count across all facilities:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -Limit 3 -MaxRequests 5
```

You can choose a different local database path or raw file directory:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -Limit 5 -MaxRequests 5 -DbPath data\processed\live-ccld.sqlite -RawDir data\raw\ccld
```

To fetch every discovered report for facility `157806098`, use `-All` and intentionally raise `-MaxRequests` high enough for the discovered report count:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -All -MaxRequests 50
```

The live script prints a warning before making requests, uses a clear user agent, applies a request timeout, limits report requests unless `-All` is used, enforces `-MaxRequests`, and does not use an aggressive retry loop.

Downloaded report files are saved under `data/raw/ccld` by default. The `data/raw` path is ignored by Git so live public source files stay local unless you intentionally move or copy them. Ingestion reads the saved raw files, records their SHA-256 hashes, and writes source traceability fields to the `source_documents` table.

Rerunning the same command updates existing SQLite rows by stable identifiers rather than duplicating the same source documents.

## Start Datasette

After the sample or live database is populated, run the command printed by the script:

```powershell
datasette "data/processed/ccld.sqlite" --metadata "data/processed/ccld.datasette-metadata.json"
```

Open the local URL printed by Datasette in a browser.

If you wrote live results to a different database path, open that path instead:

```powershell
datasette "data/processed/live-ccld.sqlite" --metadata "data/processed/live-ccld.datasette-metadata.json"
```

The printed command includes a Datasette metadata file. That metadata adds the project title, database description, review-oriented table and view descriptions, column notes, suggested sort fields, delay flag caution language, source traceability explanations, and saved query examples. See [Local Review Workflow](local-review-workflow.md) for the guided review steps.

The saved query examples include `complaints_by_facility`, `records_with_delay_review_flags`, `newest_reports`, `allegation_summary_by_facility`, and `source_traceability_check`.

## Tables to open first

Start with these Datasette views in this order:

1. `complaint_review_summary` is the main review view. It combines facility number, facility name, complaint dates, finding, allegation count and summary, delay calculations, review flags, source URL, and raw path.
2. `facility_complaint_summary` gives one row per facility with complaint count, allegation count, earliest and latest complaint received dates, and a count of records with delay review flags.
3. `delay_review_flags` shows only complaint records with one or more delay or review flags. Use it as a triage list for closer review, not as proof that an investigation was delayed.
4. `source_traceability_review` lists source URL, raw SHA-256 hash, raw path, connector name, connector version, retrieval time, and report index so reviewers can confirm where each record came from.

Then use these normalized tables when you need lower-level detail:

1. `facilities` lists the facility identifiers and names. Use this table to confirm that the database contains the facility you intended to review.
2. `source_documents` lists each public source document, source URL, raw file hash, connector name, connector version, retrieval time, and report index when available. Use this table to verify source traceability before relying on extracted complaint fields.
3. `complaints` lists complaint dates, findings, delay fields, review flags, and complaint control numbers. Use this table for the main complaint review.
4. `allegations` lists allegation text and categories linked to each complaint by complaint ID.
5. `events` lists dated events extracted from reports when available.
6. `extraction_audit` lists field-level extraction methods, source text, confidence, and warnings when available.

The table and column names are intentionally close to the data contract so exported CSV files remain understandable outside Datasette.

## Accessibility notes

Datasette pages are browser-based tables. Use keyboard navigation, browser zoom, and built-in search or filter controls as needed. Exported CSV files include clear table headers; keep those headers when sharing exports so screen reader users and spreadsheet users can understand each field.

Do not rely on color alone when reviewing exported findings or status fields. Keep source URL and raw hash columns in review exports so records can be checked against the public source.

## Important limitation

The dataset is derived from public source reports. The public portal remains the source of record.

Live fetched records reflect what the public site returned at the time of retrieval. Public reports may later change, be corrected, become unavailable, or use layouts the current extractor does not fully understand. Delay review flags are screening aids only and do not prove that an investigation was delayed.
