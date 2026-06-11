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

The script initializes `data/processed/ccld.sqlite` if needed and writes the available fixture-backed CCLD sample report into SQLite. It prints the database path and the Datasette command to open it.

This mode uses bundled test fixtures only. It does not make live web requests, and it is the right first check when you want a repeatable local sample.

You can choose a different local database path:

```powershell
.\scripts\run-ccld-sample.ps1 -DbPath data\processed\sample.sqlite
```

## Live CCLD fetch mode

Live mode is explicitly user-invoked and accesses the public CCLD external site. The default is conservative: if you do not provide a limit, the script fetches one discovered report.

Start with one report so you can confirm the workflow before fetching more:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -Limit 1
```

After that succeeds, try a small larger limit such as three or five reports. `-MaxRequests` is a safety guard that must be at least as large as the selected report limit:

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
datasette "data/processed/ccld.sqlite"
```

Open the local URL printed by Datasette in a browser.

## Tables to open first

Start with these tables in this order:

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
