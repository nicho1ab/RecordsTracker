# Exporting Data

Exports should include clear headers and source traceability fields.

## Profile CCLD public download CSVs and generate a facility cohort

CCLD public download CSV files (downloaded from ccld.dss.ca.gov into `data/raw/ccld/`) can be profiled locally to produce a normalized facility-reference CSV for use in targeted stakeholder extracts or live-fetch cohort selection.

```powershell
.\scripts\profile-ccld-public-download-csvs.ps1
```

This produces three ignored outputs under `data/processed/ccld-public-downloads/`:

- `ccld-download-profile.json` — per-file profile: row count, header count, row-width warnings (rows with trailing Complaint Info values beyond the header), facility type counts, status counts, county counts.
- `ccld-download-profile.csv` — flat per-file summary.
- `facility-reference.csv` — normalized reference CSV with columns: FacilityNumber, FacilityName, FacilityType, ProgramType, Status, City, County, Capacity, LicenseFirstDate, ClosedDate, LastVisitDate, SourceFile.

To produce a targeted cohort for a specific facility type and status, use `-FacilityType` and `-FacilityStatus`:

```powershell
.\scripts\profile-ccld-public-download-csvs.ps1 -FacilityType "Temporary Shelter Care Facility" -FacilityStatus "Licensed"
```

The resulting `facility-reference.csv` can be passed directly to the stakeholder export using `-FacilityReferenceCsv`, optionally combined with `-OnlyFacilityReferenceRows` to limit output to that cohort:

```powershell
.\scripts\export-stakeholder-facility-overview.ps1 `
    -FacilityReferenceCsv data\processed\ccld-public-downloads\facility-reference.csv `
    -OnlyFacilityReferenceRows
```

This script does not import facility rows into the database, modify raw files, add schemas, or make network requests. Public CCLD portal (ccld.dss.ca.gov) remains the source of record. Facility reference rows are reference aids only; absence or zero complaint counts is not source completeness.

## Export a stakeholder facility overview

After populating the local SQLite database, use the stakeholder facility overview script to write a ZIP package with a per-facility summary CSV, a substantiated/equivalent complaints CSV, a README, and a manifest:

```powershell
.\scripts\export-stakeholder-facility-overview.ps1
```

Output goes under `data/processed/stakeholder-extracts/<timestamp>/`. Use `-DbPath` to export from a different database:

```powershell
.\scripts\export-stakeholder-facility-overview.ps1 -DbPath data\processed\live-ccld.sqlite
```

To include facilities from a reference list even when no complaint records are loaded for them, supply `-FacilityReferenceCsv` with a path to a CSV that has a facility number column (any common header alias is recognised):

```powershell
.\scripts\export-stakeholder-facility-overview.ps1 -FacilityReferenceCsv data\processed\active-facilities.csv
```

Facilities in the reference CSV that have no loaded complaint records appear in `facility-overview.csv` with `LoadedComplaintCount=0` and `ComplaintDataLoadedStatus=No complaints loaded`. A zero count does not imply no public complaints exist; it reflects only loaded records. Reference data also enriches missing metadata fields (for example, city) for facilities that do have loaded complaints. Duplicate facility numbers in the reference file are deduplicated deterministically (first occurrence wins).

To produce a targeted package limited to only the facilities in the reference CSV, add `-OnlyFacilityReferenceRows`. Unrelated facilities already loaded in SQLite are excluded:

```powershell
.\scripts\export-stakeholder-facility-overview.ps1 -FacilityReferenceCsv data\raw\ccld\facility-reference.csv -OnlyFacilityReferenceRows
```

Using `-OnlyFacilityReferenceRows` without `-FacilityReferenceCsv` fails with a clear error.

The ZIP package includes:

- `facility-overview.csv` for per-facility complaint counts, substantiated/equivalent counts, date ranges, source-traceability counts, and a Limitations column.
- `substantiated-complaints.csv` for individual records where the source-derived finding/resolution/status indicates substantiated or an equivalent value, with source URL, raw hash, and a stable reviewer detail path.
- `README.md` with scope and limitations notes.
- `manifest.json` with generation metadata and row counts.

If the database is absent or empty, valid CSVs with headers, README, manifest, and ZIP are produced without failing.

This extract is a review aid over loaded source-derived records. The public CCLD portal remains the source of record. Counts reflect only loaded records; zero does not prove no complaints exist. Finding/resolution values are source-derived and not independently verified by RecordsTracker. Raw narrative allegation text is intentionally excluded.

## Export a local review bundle

After populating the local SQLite database, use the review bundle script to write source-traceable CSV files and a short README with review cautions:

```powershell
.\scripts\export-review-bundle.ps1
```

The default output folder is `data/processed/review-bundle`. Use `-DbPath` and `-OutputDir` when exporting from a custom database path:

```powershell
.\scripts\export-review-bundle.ps1 -DbPath data\processed\live-ccld.sqlite -OutputDir data\processed\live-review-bundle
```

The bundle includes:

- `complaint_review_with_source_traceability.csv` for complaint review fields with source URL, raw SHA-256 hash, raw path, connector metadata, retrieval timestamp, and report index.
- `delay_review_flags_with_source_traceability.csv` for triage records with one or more review flags and the same source traceability fields.
- `source_traceability.csv` for checking source URL, raw hash, connector metadata, retrieval time, report index, document type, and content type.
- `multi_facility_source_traceability.csv` for checking source traceability status, source metadata, and linked derived-record counts by source document across facilities.
- `complaint_timeline_with_source_traceability.csv` for complaint milestone dates and extracted event dates with source traceability.
- `field_source_traceability.csv` for extracted values, source text, source section, warnings, confidence, extraction method, extractor version, and source document traceability.
- `facility_pattern_review.csv` for facility-level complaint counts, source document counts, allegation categories, finding mix, missingness, report-date proxy usage, review flag counts, and date ranges.
- `facility_comparison_review.csv` for facility/category/finding rows with source-document counts, traceability-completeness counts, same-category/finding facility counts, and cautious scope notes.
- `README.md` with review notes and delay-flag caution language.

Unknown database values are exported as `unknown`. Delay review flags, timeline rows, facility pattern counts, multi-facility traceability rows, and facility comparison rows in the bundle are screening aids for closer review, not conclusions that an investigation was delayed, findings about a facility, proof that an event did or did not occur, proof that the public source is complete, or findings about facility-wide conduct.

## Export from Datasette

1. Open the table you want to review.
2. Apply any needed filters in Datasette.
3. Use Datasette's CSV export link for the filtered table or query.
4. Keep the header row in the exported CSV.
5. Keep source traceability columns in review exports so each record can be checked against the public source.

For complaint review, start with the `complaint_review_summary` view because it includes complaint fields, allegation count and summary, delay review fields, source URL, and raw path in one export. Use `facility_complaint_summary` for facility-level counts, `delay_review_flags` for records that need closer delay review, and `source_traceability_review` when checking source URLs, raw hashes, connector metadata, retrieval time, and report indexes.

If you are unsure which export path to use, open the `review_home` saved query first. Its export row points to `complaint_review_export_with_traceability` and reminds reviewers to keep clear headers plus source URL, raw hash, connector metadata, retrieval time, and report index when available. Use the review bundle when you need a source-traceable review packet that includes complaint review, delay triage, source traceability, multi-facility source traceability, timeline, field traceability, facility pattern, and facility comparison CSV files together.

Before exporting from a Datasette view or saved query, read its description. The metadata explains when the output is appropriate, what not to conclude from it, and which traceability columns to keep.

If a view does not include all needed low-level fields, export the normalized tables and preserve the ID columns so reviewers can join or compare records.

Recommended export columns:

- Facility number
- Facility name
- Complaint control number
- Complaint received date
- First investigation activity date
- Report date
- Finding
- Allegations
- Source URL
- Raw SHA-256 hash
- Connector name
- Retrieval timestamp

Do not remove source URL or raw hash fields from research exports.

## Accessible CSV review

For accessible tabular output:

- Keep clear column headers from the database or data dictionary.
- Do not replace headers with abbreviations that are not explained.
- Do not communicate findings, warnings, or status by color alone.
- Include a note that delay review flags are screening aids, not conclusions.
- Include a note that the public portal remains the source of record.
- When exporting `delay_review_flags`, label the export as a triage or review list rather than a list of delayed investigations.
- Avoid adding personal paths, account names, emails, private URLs, or machine-specific details to exported files.
- Share CSV or spreadsheet formats with readable headers instead of PDF unless PDF accessibility can be validated.
