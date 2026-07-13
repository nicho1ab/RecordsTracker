# Public Source Facility Fixture Selection

## Purpose

This directory contains tiny, synthetic fixture candidates selected from local
CSV profiling results. They support governed parser, preload, catalog, and
explicit local fixture-demo tests; default and PostgreSQL modes must not use
them as runtime fallback data.

The fixtures are intentionally small and representative. They are not raw source
files, not generated profiling outputs, not large extracts, and not complete
public record datasets.

## Fixture files

| File | Why it exists | Profiled source shape represented | Source family supported |
|---|---|---|---|
| `ccld_program_facilities_tiny.csv` | Represents the CCLD program-specific public download shape with human-readable facility columns. | 31-column files such as `ChildCareCenters06072026.csv`, `HomeCare06072026.csv`, `FosterFamilyAgencies06072026.csv`, and related program downloads. | CCLD public download CSVs. |
| `chhs_facility_master_tiny.csv` | Represents the CHHS/CDSS facility-master style shape with `FAC_NBR`, `PROGRAM_TYPE`, status, capacity, geography, and coordinate columns. | 21- or 22-column files such as `CDSS_CCL_Facilities_2065342970436235361.csv` and `downloads/chhs-community-care-licensing-facilities.csv`. | CHHS/CDSS facility master CSVs. |
| `source_fixture_manifest.csv` | Records fixture-level source-family, jurisdiction, profiled-shape, source-reference, raw-hash placeholder, and retrieval-time placeholder metadata for future source-view tests. | Local profiling summary metadata and source traceability planning fields. | Fixture manifest only. |

## Selection rationale

PR #114 profiled 9 ignored CSV files under `data/raw/source-profiling/`, with
106,981 total data rows, 1 parser warning, and 125 malformed or irregular rows.
Eight files were marked suitable for tiny fixture creation. The selected
fixtures cover the two facility-oriented source shapes most useful for future
read-only source/facility view work:

- CCLD program-specific public download CSVs with facility number, facility
  name, facility type, county, status, capacity, visit/date fields, and
  complaint-summary-like columns.
- CHHS/CDSS facility-master CSVs with `FAC_NBR`, `PROGRAM_TYPE`, `STATUS`,
  `CLIENT_SERVED`, `CAPACITY`, `COUNTY`, `FAC_DO_DESC`, `FAC_TYPE_DESC`, and
  location fields. Numeric `TYPE` remains provenance-only.

Issue #447 uses the CCLD fixture to verify sorted/deduplicated visit-date arrays
and raw complaint-information provenance, and the CHHS fixture to verify the
nullable source-reference-only client-served allocation. These allocations do
not turn the fixture rows into production records or canonical complaint events.

The profiled metadata CSV is not represented as a committed tiny fixture in this
directory because the profiler marked it unsuitable for immediate tiny fixture
creation due to a parser warning. Future metadata fixture work should first
define the metadata source shape and warning expectations.

## Boundaries

These fixtures must not be used as:

- Complete public record datasets.
- Official facility lists.
- Evidence that a public source is complete, current, or authoritative.
- Approval for production import, connector implementation, live retrieval, or
  production fixture fallback.
- A basis for legal, facility-wide, delay, harm, abuse, neglect, liability, or
  rights-deprivation conclusions.

The `source_fixture_manifest.csv` traceability fields are placeholders for tests
and future view planning. They are not raw source hashes or retrieval records
from the ignored local files.

Raw CSVs, downloaded PDFs, downloaded HTML pages, and generated profiling
outputs remain ignored by Git and must not be copied into this directory.
