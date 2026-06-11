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

The script initializes `data/processed/ccld.sqlite` if needed and writes the available fixture-backed CCLD sample report into SQLite. It prints the database path and the Datasette command to open it.

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

Start with these tables:

- `complaints` for complaint dates, findings, delay fields, and complaint control numbers.
- `allegations` for the allegation text linked to each complaint.
- `source_documents` for source URL, raw file hash, connector name, retrieval time, and report index.
- `facilities` for facility identifiers and names.

Use `source_documents` to verify source traceability before relying on extracted complaint fields.

## Accessibility notes

Datasette pages are browser-based tables. Use keyboard navigation, browser zoom, and built-in search or filter controls as needed. Exported CSV files include clear table headers; keep those headers when sharing exports so screen reader users and spreadsheet users can understand each field.

Do not rely on color alone when reviewing exported findings or status fields. Keep source URL and raw hash columns in review exports so records can be checked against the public source.

## Important limitation

The dataset is derived from public source reports. The public portal remains the source of record.
