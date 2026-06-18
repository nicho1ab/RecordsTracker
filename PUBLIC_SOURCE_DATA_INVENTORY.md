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
| Structured CSV/open-data sources | CCLD public download CSVs, CalHHS/CHHS Community Care Licensing Facilities dataset, uploaded local CSV examples | Profile locally before implementation. Preserve source URL, download timestamp, file name, raw hash, row count, column count, parser warnings, and known limitations. |
| HTML portal/detail pages | CCLD individual complaint report pages | Use deterministic discovery and extraction when reliable. Preserve source URL, raw HTML or source document, raw hash, retrieval timestamp, connector metadata, report index when available, and extraction audit context. |
| PDFs/document reports | Future public report PDFs or scanned public documents | Treat as future work. PDF extraction requires accessibility, deterministic parsing where possible, source preservation, fixture-backed tests, and careful handling of parsing confidence and warnings. |
| Metadata/catalog pages | Open-data dataset metadata pages, data dictionaries, portal catalog records | Preserve catalog URL, dataset title, publisher, update cadence when known, license or terms reviewed, field descriptions, download URL, and access date. |
| Future multi-state public sources | Other state licensing, child welfare, education, juvenile justice, or public oversight sources | Require a separate source inventory entry, jurisdiction, agency, terms review, limitations, connector decision, fixture plan, and caution language before implementation. |

## CCLD source inventory

| Source candidate | Source type | Source URL status | Update frequency status | Planning use | Known limitations and parsing risks | Traceability requirements |
|---|---|---|---|---|---|---|
| CCLD individual complaint report pages | HTML portal/detail pages | Existing connector records page-level source URLs during discovery. | Unknown; depends on public portal updates. | Primary complaint report source path for current extraction and review workflows. | HTML layouts vary; reports may have missing fields, wrapped allegations, label variants, punctuation variants, or changed public availability. Reports are public-source records, not complete facility conclusions. | Preserve source URL, raw path when available, raw SHA-256 hash, retrieval timestamp, connector name and version, report index where available, extraction audit rows, and parser warnings. |
| CCLD public download CSVs | Structured CSV/open-data sources | Exact download URLs must be recorded during local profiling or future connector planning. | Unknown until source metadata or portal notes are reviewed. | Candidate source for facility, licensing, program, or complaint summary context. | CSV columns may change; encodings, delimiters, headers, dates, missing values, and program-specific fields may vary. Summary rows may not equal complaint-level source facts. | Preserve download URL, retrieved_at timestamp, original file name, raw SHA-256 hash, row count, column count, parser profile, parser warnings, and source-specific known limitations. |
| CalHHS/CHHS Community Care Licensing Facilities dataset | Structured CSV/open-data source plus metadata/catalog page | Exact dataset and metadata URLs must be recorded during profiling. | Unknown until dataset metadata is reviewed. | Candidate facility master/reference data for names, facility numbers, program type, status, capacity, county, or regional office context if mapped through approved contract fields. | Open-data field names and update cadence may differ from CCLD report data. Facility rows may be stale, changed, corrected, or scoped differently than complaint reports. | Preserve dataset URL, metadata URL, publisher, access/download timestamp, raw hash, file name, row count, column count, field list, parser warnings, and source limitations. |
| Facility master data | Structured CSV/open-data source | To be identified from CCLD or CalHHS/CHHS source metadata. | Unknown. | Candidate facility identity and facility context source. | Must not overwrite complaint-report-derived source facts without approved import/sync and conflict rules. | Preserve stable source-derived identity, source URL, raw hash, retrieval timestamp, file name, row count, column count, and mapping rationale. |
| Program-specific facility/licensing/complaint summary CSVs | Structured CSV/open-data sources | To be identified from CCLD public downloads and local example files. | Unknown; file names may include snapshot dates. | Candidate source for program-scoped facility and licensing context. | Program files may use different schemas, date formats, status codes, and summary definitions. Snapshot dates in file names are not proof of official update cadence. | Preserve source URL if available, download timestamp, original file name, raw hash, row count, column count, parser profile, parser warnings, and program scope notes. |
| Metadata files | Metadata/catalog pages or CSV metadata exports | Exact source URL must be recorded when known. | Unknown. | Candidate field descriptions, publisher, license, refresh, and catalog context. | Metadata may be incomplete, stale, or inconsistent with downloaded files. | Preserve metadata URL, access timestamp, raw hash, file name, row count, column count, and field descriptions. |

## Uploaded CSV examples

The following uploaded local source examples are known planning inputs by file
name only. They are not tracked in the repository at the time this inventory was
added, and full/raw copies must remain untracked unless a later task explicitly
approves repository storage:

- `CDSS_CCL_Facilities_2065342970436235361.csv`
- `community-care-licensing-facilities-metadata.csv`
- `HomeCare06072026.csv`
- `CHILDCAREHOMEmorethan806072026.csv`
- `ChildCareCenters06072026.csv`
- `24HourResidentialCareforChildren06072026.csv`
- `FosterFamilyAgencies06072026.csv`

Do not commit raw full-size CSVs unless they are already intentionally tracked
and approved for repository storage. Use them locally for source profiling until
an implementation task approves tiny sampled fixtures or a controlled raw-data
storage approach.

The hosted CCLD facility lookup can use `CDSS_CCL_Facilities_2065342970436235361.csv`
as an ignored local facility-directory reference input through
`CCLD_FACILITY_REFERENCE_CSV` or `data/raw/ccld/facility-reference.csv`. That
support is limited to preloaded local/test lookup and request-page type-ahead
fields such as `FAC_NBR`, `NAME`, `PROGRAM_TYPE`, `STATUS`, `CAPACITY`, location,
county, and facility type. It does not commit the raw CSV, import rows, add a
connector, change schemas or migrations, populate source-derived records, verify
official facility status, prove complaint coverage, or make source-completeness
claims.

Recommended local profiling before implementation:

- Run `scripts/profile_public_source_csvs.py` or
  `scripts/profile-public-source-csvs.ps1` against the ignored local
  `data/raw/source-profiling/` workspace before any connector, import, schema,
  migration, hosted behavior, or canonical-field work is proposed. The profiler
  writes ignored local summaries under `data/processed/source-profiling/` and
  `data/logs/`; those generated outputs are discovery artifacts and must not be
  committed.
- Record source URL or catalog URL when known.
- Record access or download timestamp.
- Compute and record the raw SHA-256 hash locally.
- Record original file name, file size, row count, column count, header row, and
  encoding when known.
- Document columns, apparent data types, date formats, missing-value markers,
  duplicate key candidates, and source identifiers.
- Identify malformed rows, irregular quoting, delimiter issues, embedded
  newlines, blank rows, repeated headers, unexpected encodings, or parser
  warnings.
- Compare facility identifiers and names against existing CCLD-derived records
  without treating either source as automatically authoritative.
- Create tiny sampled fixtures only when implementation needs them and only with
  source metadata, Git-normalized hash expectations, and fixture documentation.

Future CSV handling must preserve at least source URL when known, download
timestamp, original file name, raw hash, row count, column count, parser profile,
parser warnings, and source-specific known limitations. These planning fields do
not add canonical source-derived fields to `DATA_CONTRACT.md` by themselves.

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
cover the CCLD program-specific facility download shape and the CalHHS/CHHS
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