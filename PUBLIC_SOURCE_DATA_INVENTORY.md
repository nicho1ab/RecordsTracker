# Public Source Data Inventory

## Purpose

This document inventories public-source data expansion candidates and planning
boundaries. It is documentation only. It does not approve CSV import, PDF
extraction, HTML scraping, new connectors, database tables, schemas,
migrations, authentication, role-based UI, GitHub issue automation, app workflow
behavior, live public-source loading, deployment, QNAP, Azure, AWS, public URL
behavior, source-derived canonical field changes, reviewer-created state
persistence, multi-state support, or legal conclusions.

No schema changes are approved by this inventory.

Future implementation must follow `DATA_CONTRACT.md`,
`SOURCE_CONNECTOR_CONTRACT.md`, `SECURITY_AND_PRIVACY.md`, and the accepted
hosted tester MVP ADR boundaries.

## Source type classification

| Source type | Examples | Planning notes |
|---|---|---|
| Structured CSV/open-data sources | CHHS/CDSS Community Care Licensing Facilities resources, CCLD public download CSVs, uploaded local CSV examples | Profile locally before implementation. Preserve dataset/catalog URL, resource ID when available, resource name, access/download timestamp, source file name or resolved download URL when available, file/snapshot date when present, row count, column count, parser warnings, source column mapping/version when implemented later, and known limitations. Raw hash is optional diagnostic metadata for authoritative structured facility CSV resources. |
| HTML portal/detail pages | CCLD individual complaint report pages | Use deterministic discovery and extraction when reliable. Preserve source URL, raw HTML or source document, raw hash, retrieval timestamp, connector metadata, report index when available, and extraction audit context. |
| PDFs/document reports | Future public report PDFs or scanned public documents | Treat as future work. PDF extraction requires accessibility, deterministic parsing where possible, source preservation, fixture-backed tests, and careful handling of parsing confidence and warnings. |
| Metadata/catalog pages | Open-data dataset metadata pages, data dictionaries, portal catalog records | Preserve catalog URL, dataset title, publisher, update cadence when known, license or terms reviewed, field descriptions, download URL, and access date. |
| Future multi-state public sources | Other state licensing, child welfare, education, juvenile justice, or public oversight sources | Require a separate source inventory entry, jurisdiction, agency, terms review, limitations, connector decision, fixture plan, and caution language before implementation. |

## CCLD source inventory

| Source candidate | Source type | Source URL status | Update frequency status | Planning use | Known limitations and parsing risks | Traceability requirements |
|---|---|---|---|---|---|---|
| CCLD individual complaint report pages | HTML portal/detail pages | Existing connector records page-level source URLs during discovery. | Unknown; depends on public portal updates. | Primary complaint report source path for current extraction and review workflows. | HTML layouts vary; reports may have missing fields, wrapped allegations, label variants, punctuation variants, or changed public availability. Reports are public-source records, not complete facility conclusions. | Preserve source URL, raw path when available, raw SHA-256 hash, retrieval timestamp, connector name and version, report index where available, extraction audit rows, and parser warnings. |
| CHHS/CDSS Community Care Licensing Facilities program datastores | Structured CSV/open-data source plus metadata/catalog page | Official legacy dataset URL: `https://data.chhs.ca.gov/dataset/ccl-facilities`; dataset slug: `ccl-facilities`. Issue #490 successfully profiled the seven named program datastores. Stable resource IDs and dataset metadata should drive future download/profile logic because direct temporary CSV filenames and resolved URLs may change. | Content freshness remains unverified. Catalog, resource, and file dates are metadata and do not prove row changes. | Validated current program-specific facility-source family for the Issue #490 evaluation. Existing governed preload behavior continues only for its separately approved target subset. This does not establish statewide completeness, source-of-record status, or universal facility coverage. | The bounded Issue #490 snapshot contains 68,527 rows across seven programs. Open-data field names and dates differ by resource. Facility rows must not overwrite complaint-report-derived historical source facts without approved import/sync, precedence, and conflict rules. | Preserve official dataset/catalog URL, resource ID, resource name, CDSS publisher and CCLD program labels, access/download timestamp, source file name or resolved download URL, file/snapshot date when present, row and column counts, parser warnings, source column mapping/version, and evaluation limitations. Raw hash remains optional diagnostic metadata for the governed product contract. |
| Statewide ArcGIS-backed Community Care Licensing Facilities source evaluated under Issue #516 | Structured ArcGIS/open-data supplementary candidate plus catalog, service, query, and export metadata | Phase A resolved the exact catalog/item/service/layer/export relationship and retained two complete observations. Issue #518 now authorizes only the stable catalog/item/service/layer and fixed layer-query paths; evaluation-only export, replica, redirect, Azure, generated, signed, and opaque paths remain excluded. Query and export differ for 47 shared Facility IDs and remain separate observations. | Unresolved. Two short-interval Phase A observations and the 2026-07-20 query observation do not prove content freshness or justify a refresh cadence. | Inactive supplementary current-reference source. Phase A merged at `41d512127febdfd086432e7f082d0651da232e9f` with **SUPPLEMENT**. The bounded query-only connector preserves a controlled candidate, but program-specific snapshots remain primary; ArcGIS is not a replacement or production-active source. | The controlled 2026-07-20 query returned 29,871 rows and 29,714 unique facility numbers; 157 rows exceeded one row per duplicate facility-number group. Source-row identity is snapshot plus `ObjectId`; facility number is non-unique. Program sources contain 68,526 unique nonblank Facility IDs: 27,831 shared, 1,883 ArcGIS-only, and 40,695 program-only. Raw `733` remains unmapped. California Open Data designates Creative Commons Attribution but publishes no exact version or dataset-specific attribution sentence; Andrew accepted provisional attribution as product-owner risk, not a legal conclusion. System-of-record status, maintainer, steward, update owner, and cadence remain unresolved. | Preserve source-specific immutable responses under the ignored governed evidence root, sanitized retrieval metadata, provisional attribution, original-response and normalized hashes, schema/domain fingerprints, separate query/export observations, every `ObjectId`, facility-number match/grouping values, conflicts, disappearances, candidate/accepted/prior-accepted state, and rollback evidence. See the [Phase A comparison](docs/analysis/build-week-2026-arcgis-shadow-comparison.md), [SUPPLEMENT recommendation](docs/analysis/build-week-2026-arcgis-source-recommendation.md), [live connector evidence](docs/analysis/issue-518-live-query-connector-evidence.md), and [Build Week completion plan](docs/planning/build-week-2026-arcgis-facility-reference-completion-plan.md). |
| CCLD public download CSVs outside the target facility resource set | Structured CSV/open-data sources | Exact download URLs or catalog records must be recorded during local profiling or future connector planning. | Unknown until source metadata or portal notes are reviewed. | Candidate source for licensing, program, or complaint summary context outside the current facility preload target set. | CSV columns may change; encodings, delimiters, headers, dates, missing values, and program-specific fields may vary. Summary rows may not equal complaint-level source facts. | Preserve download/catalog URL, resource ID when available, retrieved_at timestamp, original file name or resolved download URL, row count, column count, parser profile, parser warnings, and source-specific known limitations. Raw hash is optional diagnostic metadata for structured facility CSV resources. |
| Facility master data | Structured CSV/open-data source | Identified through CHHS/CDSS Community Care Licensing Facilities dataset metadata or future confirmed CCLD/CHHS/CDSS source metadata. | Unknown. | Inactive candidate for facility identity and context unless a later evaluation and separate approval qualify an exact source and use. | Issue #490 did not establish a statewide candidate's source-of-record status, stable access path, coverage, freshness, terms, or precedence. It must not overwrite complaint-report-derived source facts without approved import/sync and conflict rules. | Preserve stable source-derived identity, official dataset/catalog URL, resource ID when available, resource name, access/download timestamp, source file name or resolved download URL, row count, column count, parser warnings, and mapping rationale. Raw hash is optional diagnostic metadata. |
| Program-specific facility/licensing/complaint summary CSVs | Structured CSV/open-data sources | The evaluated and current preload-target resources are distinguished below. Other program CSVs need source metadata confirmation before implementation. | Unknown; file names may include snapshot dates. | Current governed facility-reference inputs only for an explicitly approved named resource and preload scope; otherwise candidate context. | Program files may use different schemas, date formats, status codes, and summary definitions. Snapshot dates in file names are not proof of official update cadence or statewide completeness. | Preserve official dataset/catalog URL, resource ID when available, resource name, access/download timestamp, source file name or resolved download URL, file/snapshot date when present, row count, column count, parser profile, parser warnings, and program scope notes. Raw hash is optional diagnostic metadata. |
| Metadata files | Metadata/catalog pages or CSV metadata exports | Exact source URL must be recorded when known. | Unknown. | Candidate field descriptions, publisher, license, refresh, and catalog context. | Metadata may be incomplete, stale, or inconsistent with downloaded files. | Preserve metadata URL, access timestamp, raw hash, file name, row count, column count, and field descriptions. |

## Authoritative facility CSV resources

In this existing product-contract heading, `authoritative` is limited to a
separately approved named structured resource and its governed preload scope. It
does not mean statewide completeness, current content freshness, universal
program coverage, legal authority, or operational system-of-record status.
RecordsTracker currently uses the named CHHS/CDSS Community Care Licensing
Facilities program resources as the governed facility reference family for the
existing preload path. Issue #490 successfully profiled the seven current
program datastores as a bounded 68,527-row evaluation snapshot.

Issue #490 remains completed historical evaluation evidence. The later governed
Phase A evaluation under #516 resolved the exact ArcGIS source and returned
**SUPPLEMENT**, not adoption or replacement. This inventory records source
framing only; it does not approve import code, schemas, migrations, database
tables, hosted behavior, deployment, UI changes, production activation, raw CSV
commits, or generated profiling outputs.

Program-specific snapshots remain the primary facility-reference source family.
ArcGIS is a separately versioned supplementary current-reference source. Neither
source overwrites or erases the other. Blank ArcGIS values never erase nonblank
program values; identical values may reconcile while retaining both source
observations; conflicting nonblank values retain both originals and conflict
state. Disappearance does not mean closure or deletion, failed candidates never
partially apply, and rollback selects complete prior accepted snapshots.

Content change must be detected through preserved original bytes, normalized
row content, schema/domain fingerprints, and Facility ID sets. Catalog or
resource timestamps alone are insufficient. Facility number cannot be a unique
ArcGIS database key. Any later reconciliation/backfill must retain field-level
provenance and nonblank conflicts, and raw `733` must remain unmapped unless
verified source or governed mapping evidence proves a label.

Parent dataset:

- Dataset name: Community Care Licensing Facilities.
- Dataset slug: `ccl-facilities`.
- Official dataset URL: `https://data.chhs.ca.gov/dataset/ccl-facilities`.
- Publisher: California Department of Social Services (CDSS).
- Program label: Community Care Licensing Division (CCLD).
- Catalog host: California Health and Human Services Open Data Portal.

Issue #490 validated this seven-resource program-source family for its bounded
technical evaluation. The row counts do not establish statewide completeness or
current content freshness:

| Evaluated program resource | Official CHHS resource ID | Evaluated rows |
|---|---|---:|
| Child Care Centers | `7aed8063-cea7-4367-8651-c81643164ae0` | 19,426 |
| Residential Care Facilities for the Elderly | `744d1583-f9eb-45b6-b0f8-b9a9dab936a6` | 12,522 |
| 24-Hour Residential Care for Children | `c9df723a-437f-4dcd-be37-ec73ae518bb9` | 1,960 |
| Foster Family Agencies | `5f5f7124-1a38-4b61-93b9-4e4be3b3b07d` | 709 |
| Home Care Organization | `b4d78b7f-12df-4b0c-a81a-ff40b949bc75` | 3,654 |
| Family Child Care Homes | `4b5cc48d-03b1-4f42-a7d1-b9816903eb2b` | 19,758 |
| Adult Residential Facilities | `9f5d1d00-6b24-4f44-a158-9cbe4b43f117` | 10,498 |

Current preload target resource set, unchanged by Issue #490:

| Target resource name | Official CHHS resource ID | Local example filename, when already known |
|---|---|---|
| Child Care Centers | `7aed8063-cea7-4367-8651-c81643164ae0` | `ChildCareCenters06072026.csv` |
| Family Child Care Homes | `4b5cc48d-03b1-4f42-a7d1-b9816903eb2b` | `CHILDCAREHOMEmorethan806072026.csv` |
| Home Care Organization | `b4d78b7f-12df-4b0c-a81a-ff40b949bc75` | `HomeCare06072026.csv` |
| Foster Family Agencies | `5f5f7124-1a38-4b61-93b9-4e4be3b3b07d` | `FosterFamilyAgencies06072026.csv` |
| 24-Hour Residential Care for Children | `c9df723a-437f-4dcd-be37-ec73ae518bb9` | `24HourResidentialCareforChildren06072026.csv` |
| Statewide facility master/local facility-directory example | Needs confirmation from official CHHS dataset metadata before use. | `CDSS_CCL_Facilities_2065342970436235361.csv` |

The committed local profiling registry for this target set lives in
`src/ccld_complaints/source_profiling.py` as `FACILITY_SOURCE_REGISTRY`. That
registry is reused by the local facility-reference preload command to match
ignored local CSV files to known CHHS/CDSS resources. It does not implement live
download, connector execution, QNAP/deployment behavior, or statewide crawling.

The target facility resources share a statewide facility export shape. Exact
source column names must be preserved when known during profiling and mapping;
known local helper columns already referenced by this inventory include
`FAC_NBR`, `NAME`, `FAC_TYPE_DESC`, `PROGRAM_TYPE`, `STATUS`, `CLIENT_SERVED`,
`CAPACITY`, and `FAC_DO_DESC`. Intended field
coverage includes facility type, facility number, facility name, licensee,
facility administrator, telephone, address, city, state, ZIP, county, regional
office, capacity, status, license first date, closed date, and file date or
snapshot date.

Direct temporary CSV filenames and resolved download URLs may change. Future
download/profile logic should use stable resource IDs and official dataset
metadata when available, while recording the resolved file name or download URL
observed at access time.

Raw full-size CSV files remain untracked and ignored. Do not commit raw full-
size CSVs unless a later task explicitly approves repository storage. Generated
profiling outputs remain ignored by Git.

## Local CSV examples

The following local source examples are known only as ignored local files unless
the authoritative resource table above identifies their official CHHS resource
ID. They are not tracked in the repository, and full/raw copies must remain
untracked unless a later task explicitly approves repository storage:

- `community-care-licensing-facilities-metadata.csv`

Do not commit raw full-size CSVs unless they are already intentionally tracked
and approved for repository storage. Use them locally for source profiling until
an implementation task approves tiny sampled fixtures or a controlled raw-data
storage approach.

The hosted CCLD facility lookup can use ignored local facility-directory
reference inputs in two local/test ways. Fixture/demo mode can still read
`CCLD_FACILITY_REFERENCE_CSV` or `data/raw/ccld/facility-reference.csv`.
PostgreSQL mode can read rows preloaded into
`hosted_facility_reference_records` by
`scripts/load-facility-reference-preload.ps1`. Both paths are limited to lookup
and request-page type-ahead fields such as `FAC_NBR`, `NAME`, `PROGRAM_TYPE`,
`STATUS`, `CAPACITY`, location, county, and facility type. They do not commit
raw CSVs, run live downloads, add connectors, populate source-derived complaint
records, verify official facility status, prove complaint coverage, or make
source-completeness claims.

The PostgreSQL preload also retains the issue #447 governed source-reference
allocations. `All Visit Dates`, `Inspection Visit Dates`, and `Other Visit
Dates` are nullable, sorted, deduplicated ISO-date arrays; `CLIENT_SERVED` is
nullable source-reference text; `Closed Date` remains a nullable typed
reference date. The composite complaint-information column and any trailing CSV
cells remain unflattened in original-row provenance. These fields do not create
canonical complaint events, allegation counts, facility types, or facility
status, and the preload does not bridge reference rows into canonical facility
entities.

The hosted CCLD facility hub can also read supported ignored local public summary
CSV inputs through `CCLD_FACILITY_REVIEW_SIGNALS_CSVS` or the existing ignored
`data/raw/source-profiling/` filenames for the shared 31-column CCLD program
summary shape used by `HomeCare06072026.csv`,
`CHILDCAREHOMEmorethan806072026.csv`, `ChildCareCenters06072026.csv`,
`24HourResidentialCareforChildren06072026.csv`, and
`FosterFamilyAgencies06072026.csv`. Supported fields are limited to safe scalar
facility-level review signals such as facility number, name, type, status,
capacity, county, regional office, license first date, closed date, last visit
date, inspection/complaint/other/total visit counts, citation indicators, Type A
and Type B citation counts where represented, POC date counts, and source dataset
label. Malformed, shifted, or unsupported rows are skipped or counted internally
without exposing raw rows. This support does not commit raw CSVs, import data,
add connectors, change schemas or migrations, populate source-derived records,
verify sources, prove complaint coverage, or make source-completeness claims.

## Representative multi-facility coverage validation

The reproducible validation path for representative multi-facility CCLD coverage
now uses existing approved local/test pieces rather than a new connector or
schema:

1. Preload ignored local CHHS/CDSS Community Care Licensing Facilities CSV rows
   into `hosted_facility_reference_records` with
   `scripts/load-facility-reference-preload.ps1`.
2. Load or retrieve CCLD complaint records through the existing hosted
   source-derived import path, controlled Request Records retrieval, or
   operator batch retrieval path.
3. Run `scripts/report-representative-coverage.ps1` to generate a read-only JSON
   report over the hosted PostgreSQL tables.

The report records the exact loaded source files, source resource names, source
dataset URLs, source-access timestamps, snapshot dates when available, facility
types, facility row counts, CCLD complaint row counts, complaint source URLs,
retrieval timestamps, source-document linkage counts, required traceability
field counts, source-derived duplicate-identity counts, retrieval
failure/rejection counts from job metadata, and representative status as
not-ready, partial, or candidate.

This report does not download public sources, crawl statewide, infer public
source completeness, transform missing values into conclusions, mutate
reviewer-created state, or prove production/QNAP coverage from PostgreSQL rows
alone. It classifies clearly identified fixture/demo/test rows and
unknown-provenance rows separately and excludes them from representative counts.
Facility-reference skipped-row counts remain in the preload command output;
they are not persisted in the current facility-reference table. Manual browser
evidence, selected-source reconciliation, and acceptance remain required before
the representative coverage requirement can be marked complete.

Recommended local profiling before implementation:

- Run `scripts/profile_public_source_csvs.py` or
  `scripts/profile-public-source-csvs.ps1` against the ignored local
  `data/raw/source-profiling/` workspace before any connector, import, schema,
  migration, hosted behavior, or canonical-field work is proposed. The profiler
  writes ignored local summaries and the machine-readable
  `facility-source-gap-assessment.json` under
  `data/processed/source-profiling/`, plus logs under `data/logs/`; those
  generated outputs are discovery artifacts and must not be committed.
- Record official dataset URL or catalog URL.
- Record resource ID when available.
- Record resource name.
- Record access or download timestamp.
- Record source file name or resolved download URL when available.
- Record file date or snapshot date when present.
- Record row count, column count, header row, and encoding when known.
- Record raw SHA-256 locally only as optional diagnostic metadata for
  authoritative structured facility CSV resources.
- Document columns, apparent data types, date formats, missing-value markers,
  duplicate key candidates, and source identifiers.
- Identify malformed rows, irregular quoting, delimiter issues, embedded
  newlines, blank rows, repeated headers, unexpected encodings, or parser
  warnings.
- Compare facility identifiers and names against existing CCLD-derived
  complaint/report records without overwriting either source unless a later
  approved import/sync task defines conflict rules.
- Create tiny sampled fixtures only when implementation needs them and only with
  source metadata, Git-normalized hash expectations, and fixture documentation.

Future structured CSV facility handling must preserve at least official dataset
URL or catalog URL, resource ID when available, resource name, access/download
timestamp, source file name or resolved download URL when available, file date or
snapshot date when present, row count, column count, parser warnings, and source
column mapping/version when implemented later. Raw hash is optional diagnostic
metadata for structured facility CSV resources. These planning fields do not add
canonical source-derived fields to `DATA_CONTRACT.md` by themselves.

Local profiling does not import data, create canonical fields, approve schemas
or migrations, add connectors, create database tables, populate the hosted app,
or validate source completeness. Raw CSVs, downloaded PDFs, downloaded HTML
pages, and generated profiling outputs remain ignored by Git. Tiny committed
fixtures for profiler tests must be synthetic and must not copy rows from local
raw source files.

Local CDE HTML captures may be CAPTCHA or access-block pages. Treat those as
source-access issues for later discovery notes, not as valid data pages or
approved HTML scraping inputs.

## Tiny fixture selection

The committed fixtures under `tests/fixtures/public_source_facilities/` are
tiny, synthetic representatives selected from local profiling results. They
cover the CCLD program-specific facility download shape and the CHHS/CDSS
facility-master shape for fixture-backed source/facility view planning. The
local hosted scaffold `/facilities` route now uses these committed tiny fixtures
only for a read-only sample facility master view and detail pages. The fixtures
include manifest placeholders for source family, jurisdiction, source
reference, raw hash, and retrieval timestamp so tests can exercise
source-traceability-style display without committing raw source files or
generated profiling outputs. Facility detail pages also use the fixture rows to
show local-only source coverage indicators and related fixture/sample
source-record context where the sample mapping exists.

These fixtures do not approve CSV import, connector implementation, schema or
migration work, database-backed hosted app behavior, live source loading,
canonical field changes, source completeness claims, or legal conclusions. The
metadata CSV that produced a parser warning in profiling is intentionally
deferred from this tiny fixture set until a later task defines metadata warning
expectations.

## Multi-source expansion model

Future source adapters should be planned through a source registry entry before
implementation. A registry entry should capture:

- Source name.
- Source type: CSV/open-data, HTML portal/detail page, PDF/document report,
  metadata/catalog page, or multi-state public source.
- Jurisdiction.
- Agency or publisher.
- Topic or domain.
- Retrieval method.
- Update cadence when known.
- Parser profile.
- Traceability fields.
- Caution and limitation language.
- Allowed use.
- Review status.

The source registry is a conceptual planning model in this document. It does not
create a schema, table, configuration file, connector, import command, hosted
workflow, or canonical field. Future implementation must decide whether the
registry belongs in documentation, code configuration, database tables, or an
operator-managed manifest through a separate task.

## Attorney focus-area planning

Future role or focus profiles may help reviewers choose queues, filters,
dashboards, issue-spotting views, and contextual help. Candidate focus areas
include:

- Facility oversight.
- Foster youth education justice.
- K-12 discipline, absenteeism, and placement stability.
- Juvenile justice touchpoints.
- Transition-age youth outcomes.
- Cross-state comparison.

Focus profiles are reviewer workflow aids. They must not produce legal
conclusions, facility-wide conclusions, public-source completeness conclusions,
delay conclusions, harm conclusions, abuse or neglect conclusions, liability
conclusions, or rights-deprivation conclusions. They also must not imply that a
reviewer has a role, permission, or professional authority unless future
authentication, authorization, and product governance explicitly define it.

## Feedback and GitHub intake planning

Future user feedback, bug report, data issue, and feature request paths may
integrate with GitHub issues or another development intake system only after
appropriate gates are implemented. This document does not implement GitHub issue
automation or any hosted feedback workflow.

Required gates before feedback becomes development work:

- Triage review.
- Classification as bug, enhancement, data issue, documentation issue, or source
  issue.
- Privacy and secrets check.
- Duplicate check.
- Priority and severity assignment.
- Human approval before issue creation or implementation.
- Traceability from user feedback to the GitHub issue or development intake item
  if one is created.

Feedback must remain reviewer-created or user-submitted state. It must not be
treated as source-derived fact, must not overwrite source records, and must not
include secrets, private URLs, personal account details, or unnecessary personal
information.

## Deferred implementation

This inventory does not implement:

- CSV import.
- PDF extraction.
- HTML scraping.
- New connectors.
- Database tables.
- Schemas or migrations.
- Authentication or role-based UI.
- GitHub issue automation.
- App workflow behavior.
- Live public-source loading.
- Deployment, QNAP, Azure, AWS, or public URL behavior.
- Source-derived canonical field changes.
- Reviewer-created state persistence.
- Legal conclusions.
