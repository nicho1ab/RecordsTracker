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

## Populate the sample database

From the repository root, run the bundled sample script:

```powershell
.\scripts\run-ccld-sample.ps1
```

The script initializes `data/processed/ccld.sqlite` if needed and writes the available fixture-backed CCLD sample report into SQLite. The bundled facility detail fixture discovers 40 report candidates, but only bundled fixture-backed report content is written. At present, the bundled report fixture is facility `157806098`, report index `3`. It prints the database path and the Datasette command to open it.

You can choose a different local database path:

```powershell
.\scripts\run-ccld-sample.ps1 -DbPath data\processed\sample.sqlite
```

## Start Datasette

After the sample database is populated, run the command printed by the script:

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
