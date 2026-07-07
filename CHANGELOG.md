# Changelog

## Unreleased
- Aligned Facility Lookup and Request Records with the shared hosted shell and
  component patterns: both pages now use compact reviewer-facing Facility ID
  workflows, demote optional planning/reference details below the main task,
  avoid setup/configuration wording in the default path, and keep Request
  Records selected Facility ID, copy, date range, and action controls clear
  without changing retrieval/import behavior.
- Added the shared Figma-aligned hosted shell and applied it first to Review
  Queue: the top shell now uses a compact RecordsTracker workspace bar with
  Figma-derived font variables, teal/slate/amber tokens, explicit brand/search/
  nav/mode grid columns, facility lookup, no-wrap primary navigation, and a
  single mode badge; Review Queue now leads with a lighter facility brief and
  Worklist-first task surface, moves search below the Worklist, keeps
  table/cue/export sections collapsed below the Worklist, and removes generic
  "Check source" plus stale first-activity cues as persistent review labels
  while preserving specific source/date cues and source availability as separate
  information.
- Reworked hosted Reviewer Detail toward the approved Complaint overview
  workspace: the page now centers one compact overview card with complaint
  identity, one structured facility facts bar, source narrative, MM/DD/YYYY
  key-date timeline with a document-style received marker, centered event marker
  variants, and centered 120+ day gap cue, warning versus informational review
  badges, corrected first-activity warning logic, separate CCLD source
  availability/action, compact status/note controls, accessible copy buttons
  including source narrative, inline definitions, and finding badge variants
  while keeping source traceability/debug/help-heavy content out of the
  reviewer-facing tier.
- Applied the Prompt 2 hosted UI contract across Request Records selected-context
  and no-match recovery, Facility Hub, signal-only Facility summary, and
  Facility Review Priority. Primary navigation now uses Home as the single
  facility/start destination while `/ccld/facilities` remains available, task
  actions use compact grouped buttons, user-facing Prompt 2 date ranges render
  as MM/DD/YYYY, and operator/runtime details stay behind support disclosures.
- Standardized hosted UI action groups for Home/Facility, Feedback, and Help:
  Home now uses the Find a Facility start experience, key actions use compact
  primary/secondary button grouping without list-item buttons, Feedback supports
  broader feedback types with hidden page-path metadata, and Help remains a
  short task-oriented user page with runtime notes kept secondary.
- Tightened the screenshot-review pass for attorney-facing CCLD pages: reviewer
  detail now hides the duplicate flag explainer and empty reviewer-history
  table, Request Records/no-match support details are collapsed under
  reviewer-oriented labels, facility lookup/hub details and optional planning
  views are secondary to request actions, and Help now leads with reviewer
  workflow topics while preserving runtime/source internals under support notes.
- Corrected hosted reviewer detail tiering so the attorney-facing page no
  longer renders source traceability internals, source-derived value-check
  tables, full source field dumps, related source bundle rows,
  technical/operator details, first-run/detail navigation dumps, field-note
  guidance, or issue-report bridge copy. The page now emphasizes complaint and
  facility identity, source narrative, compact timeline, finding/allegation
  summary, review-flag badges, copy affordances, concise reviewer-created
  note/status actions, and focused queue/next-record actions while preserving
  source-derived records, traceability, reviewer-created persistence, audit,
  retrieval, export, and runtime behavior.
- Simplified the hosted attorney start, facility lookup, and Request Records flow
  so Home centers the review path, facility lookup result selection carries the
  facility/license number and name into Request Records with immediate date
  controls, and Request Records distinguishes already-loaded queue review from
  controlled retrieval requests while preserving safe facility/date/feedback
  context and existing retrieval/import behavior.
- Simplified hosted attorney-facing navigation by removing Job Status from the
  primary navigation, keeping job diagnostics available through support-oriented
  diagnostics pages and contextual Request Records links, and standardizing the
  feedback entry label as "Feedback" while preserving the GitHub-backed
  `/feedback` flow, safe context allowlist, request/queue/reviewer/detail
  routes, and retrieval/import behavior.
- Added a numbered RecordsTracker UI/product improvement inventory for user
  approval before reviewer-facing UI implementation. The inventory organizes
  proposed Home, facility lookup, facility hub, Request Records, queue, reviewer
  detail, packet, feedback, Help, diagnostics, and cross-page workflow changes
  by page/workflow, preserves operator/support diagnostics outside the primary
  attorney path, marks items needing Figma AI/design exploration, and defines
  small implementation PR groupings and stop conditions without changing app
  behavior.
- Added an operator batch CCLD complaint retrieval CLI at
  `ccld_complaints.hosted_app.batch_complaint_retrieval`. The command selects
  facilities from `hosted_facility_reference_records`, defaults to dry-run,
  splits date ranges into 366-day-or-less windows, writes JSONL manifests with
  resume support, skips already-loaded windows unless `--force` is supplied, and
  reuses the existing controlled Request Records retrieval/import seam for
  apply mode.
- Expanded hosted `/feedback` into the shared GitHub-backed feedback intake for
  bug reports, feature requests, confusing workflow/page reports, packet/export
  issues, source/data concerns, and new data source requests. Configured
  submissions now build concise RecordsTracker issue titles, safe issue bodies
  with allowlisted context, safe issue links, and label-fallback retries; missing
  GitHub configuration or GitHub failures show a copyable safe summary without
  exposing tokens or server internals.
- Added steering, design, and accessibility governance for the approved
  attorney-facing reviewer surface model, including reviewer/operator/developer
  surface separation, reviewer action patterns, facility/request workflow rules,
  terminology and source-detail boundaries, page-direction rules, feedback/help
  direction, traffic-light status accessibility, and the required numbered
  page-change inventory gate before reviewer-facing UI implementation.
- Fixed live Request Records imported-count semantics so retrieval job metadata,
  Request Records messaging, and Job Status show the number of unique
  source-derived rows persisted after import/upsert normalization, not the
  pre-persistence flattened candidate-row count.
- Improved hosted facility lookup and Request Records typeahead suggestions so
  each suggestion shows a compact text status badge near the facility name and
  wraps long facility number, location, county, type, and program text without
  horizontal scrolling. Facility result/detail labels now use concise field
  names without "directory field" suffixes. Added a read-only facility reference
  address diagnostic command that compares normalized address fields with
  address-like columns preserved in `original_row_json` for loaded PostgreSQL
  facility reference rows.
- Updated the hosted CCLD facility lookup in PostgreSQL page mode to search the
  active preloaded facility reference table server-side before applying the
  browser result limit. The lookup and request comboboxes now use a narrow
  query-specific suggestions route for PostgreSQL-backed reference rows, so
  loaded facility numbers and names from Child Care Centers, Family Child Care
  Homes, Home Care Organization, Foster Family Agencies, 24-Hour Residential
  Care for Children, and statewide facility master sources remain searchable
  without preloading only the first static browser slice.
- Added a narrow PostgreSQL-backed CCLD facility reference preload path for
  authoritative CHHS/CDSS Community Care Licensing Facilities CSV resources.
  The new Alembic table stores typed lookup fields plus explicit source
  metadata, a local dry-run/apply preload command parses ignored local CSVs
  through the existing `FACILITY_SOURCE_REGISTRY`, and PostgreSQL page mode now
  prefers preloaded facility reference rows while preserving existing
  source-derived and fixture fallbacks. No raw CSVs, live downloads, new hosted
  routes, UI redesign, QNAP/deployment/auth changes, reviewer workflow changes,
  or complaint retrieval changes were added.
- Added facility source profiling and database-fit assessment output for the
  CHHS/CDSS Community Care Licensing Facilities preload planning path. The
  local profiler now records the official target resource registry, per-file
  resource matching, blank/type/duplicate facility-number signals, source-to-app
  field mappings, and a machine-readable gap report without adding imports,
  schemas, migrations, UI, hosted routes, raw CSV commits, generated profile
  commits, QNAP/deployment/auth changes, or live downloads.
- Aligned the data/source contract so CHHS/CDSS CCLD Community Care Licensing
  Facilities CSV resources are authoritative facility reference sources for the
  facility preload path, with raw hash optional diagnostic metadata for
  structured facility CSV resources. No import, schema, migration, UI, hosted
  behavior, connector implementation, raw CSV commit, or generated profiling
  output was added.
- Added a concise "How to read this record" guide to hosted reviewer detail so
  testers can distinguish source-derived public record context, review cues, and
  follow-up actions without treating page guidance as legal conclusions.
- Added concise useful-feedback examples to hosted `/feedback` so testers can
  describe what they were trying to do, where they were in the workflow, what
  looked wrong or confusing, what they expected, and what visible safe context
  was shown without adding storage, sending behavior, or another workflow.
- Improved hosted `/feedback` submission confirmation so testers can review
  the submitted feedback fields, visible safe context, and next actions after
  submit without adding feedback storage, sending behavior, or another workflow.
- Added a concise tester task guide to the hosted entry orientation with concrete
  first-run review tasks, expected observations, and the existing safe feedback
  handoff.
- Tightened hosted `/feedback` context handling with an explicit safe query
  allowlist, visible submitted page-path context, and hosted entry/orientation
  links that carry safe workflow context without source keys or hidden
  submission context.
- Added a concise first-time tester orientation on the hosted entry page that
  explains the start path, loaded context, facility lookup, prioritized records,
  packet/brief, readiness checklist, and `/feedback` handoff. The existing
  feedback route now includes more actionable tester-feedback guidance without
  adding a second feedback workflow or changing feedback persistence.
- Added acceptance guardrails for the guided attorney review workflow across
  the hosted entry point, facility pattern review hub, prioritized record
  queue, packet preview/draft brief, and attorney readiness checklist using the
  existing fixture/demo routes and loaded context only.
- Added a guided attorney review workflow entry point on the hosted home page.
  The path links existing facility lookup/hub, reviewer queue/detail, packet
  preview/draft, and readiness checklist areas, with concise limited-data
  caution language and no new workflow state, persistence, export lifecycle, or
  source-derived record changes.
- Added an attorney review readiness checklist near the packet preview/draft
  attorney brief. The checklist uses only loaded packet context to label
  prioritized records, source-traceability cues, reviewer-created note/status
  presence, limited-data warnings, and follow-up questions as review-readiness
  guidance without adding packet state, exports, legal conclusions, or source-
  completeness claims.
- Added a copy-ready attorney review brief to packet preview and draft pages.
  The brief uses the active facility/date context, loaded record counts,
  prioritized records, packet readiness cues, source-traceability cue counts,
  reviewer-created status/note presence, review reasons, and follow-up review
  questions while avoiding raw source keys, source document identifiers, import
  or audit details, durable packet state, exports, source-derived mutation,
  legal conclusions, and source-completeness claims.
- Added packet readiness from prioritized facility records. Facility hubs now
  summarize selected facility identity, loaded complaint context, Review next
  prioritized-record availability, source-traceability availability, and
  reviewer-created status/note cues before linking to the existing packet
  preview/draft routes. Packet preview and draft pages now include a
  print/copy-friendly "Prioritized records for review" summary based on existing
  review-next ordering and cautious source-derived/reviewer-created reasons,
  without adding packet lifecycle state, retrieval, schemas, persistence, exports,
  source-derived mutation, or reviewer-created write behavior.
- Added a compact default-visible Review next section to facility review hubs.
  The section recommends loaded complaint records using existing source-derived
  and reviewer-created cues, shows cautious reasons, and links to existing
  reviewer detail pages without changing retrieval, schemas, persistence,
  source-derived records, or reviewer note/status semantics.
- Added a default-visible Facility Pattern Review Summary to facility review hubs.
  The summary uses already loaded source-derived complaint records plus available
  uploaded public summary fields to show complaint counts, finding mix,
  delay/missing-date review signals, source-traceability availability,
  reviewer-created note/status cues, recent activity, and existing request/queue
  next-action links. Raw source keys, source document IDs, import/audit details,
  retrieval behavior, extraction behavior, schemas, migrations, source-derived
  mutation, reviewer-created write semantics, legal conclusions, source
  verification, and source-completeness claims are unchanged.
- Applied the reviewer-detail product-quality visual standard across remaining
  hosted RecordsTracker pages. Home now presents the four-step facility review
  path (find facility, request records, review evidence, prepare/export/send
  feedback); Request Records, Job Status, facility lookup/hub/intelligence,
  reviewer queue, packet context-empty states, feedback, and help use calmer
  reviewer-facing labels and page-level orientation. Evidence capture and
  acceptance checks now recognize the compact shared shell, active navigation,
  page headings, and Request Records/Job Status route names instead of requiring
  old workflow/keyboard rail text on every page. No schema, extraction,
  retrieval, persistence, source connector, or lifecycle behavior changed.
- Redesigned the hosted reviewer complaint detail page as an attorney-focused
  complaint-review workspace. The page now leads with complaint identity,
  facility/license context, a separated reviewer-created state panel, cautious
  why-flagged cues, keyboard-focusable quick review cards, visible structured
  source-backed sections, compact glossary support, source traceability summary,
  source narrative excerpt, and collapsed full source-derived and
  technical/operator details. Existing note/status action paths are unchanged;
  no schema, extraction, retrieval, or persistence behavior changed.
- Stakeholder facility overview export now produces a single Excel workbook
	(`.xlsx`) instead of a ZIP of loose files. The workbook contains five
	worksheets in order: `README`, `facility-overview`, `substantiated-complaints`,
	`complaint-records`, `Manifest`. Data worksheets have bold headers, frozen
	top row, auto-filter, and auto-sized columns (max 60 chars). The `README`
	tab includes purpose, key details (row counts, timestamp, git commit),
	how-to-use guidance, tabs overview, counts and coverage note, source of
	record, and important limitations — all with plain cautious language and no
	severity rankings or legal conclusions. The `Manifest` tab uses key/value
	rows (not a raw JSON blob) and includes `complaint_record_row_count`.
	`StakeholderExtractResult.zip_path` is replaced by `xlsx_path`; the ZIP is
	no longer created. Adds `openpyxl>=3.1` dependency. No schema, migration,
	live-retrieval, hosted-UI, or source-connector changes.
- Added `complaint-records.csv` to the stakeholder facility overview extract
	package. The file contains one row per loaded complaint record (all statuses,
	not just substantiated/equivalent) for all facilities in the extract. New
	columns: `FindingGroup` (SubstantiatedOrEquivalent, NotSubstantiatedOrEquivalent,
	or UnknownOrMissing — derived from source-derived finding text only),
	`ComplaintType` (source-derived document type or "not available"),
	`AllegationCategory` (source-derived category labels from the allegations
	table, concatenated, or "not available"), `KeywordReviewCues` (deterministic
	keyword-based review-cue label derived from finding and allegation_category
	fields — review aid only, not a severity score, risk score, verified finding,
	or legal classification). Raw narrative allegation text is never included.
	`complaint-records.csv` is included in the ZIP package and in
	`manifest.json` with a `complaint_record_row_count` field. The
	`-OnlyFacilityReferenceRows` filter applies to this file as well. README.md
	now explains complaint-records.csv and its limitations. No schema, migration,
	live-retrieval, or hosted-UI changes.
- Fixed `_candidates_from_report_list_json` discovery null/malformed payload
	handling: JSON `null`, `{"REPORTARRAY": null}`, and null elements inside
	`REPORTARRAY` are now treated as "no records discovered" instead of crashing
	with `AttributeError`. Non-dict JSON responses surface as controlled
	discovery failures with a descriptive message. Adds regression tests covering
	all four cases plus normal discovery behavior.
- Fixed `-FacilityStatus` and `-InputPath` parameter name mismatch in
	`scripts/profile-ccld-public-download-csvs.ps1` (previously `$Status` and
	`$InputDir` silently ignored user-supplied values). The Python CLI option was
	also renamed from `--status` to `--facility-status`. Filter summary now always
	prints both `FacilityType filter` and `FacilityStatus filter` lines before
	the row count.
- Added local profiling and cohort-generation utility for CCLD public download
	CSVs: `scripts/profile-ccld-public-download-csvs.ps1` (PowerShell wrapper),
	`scripts/profile_ccld_public_download_csvs.py` (CLI), and
	`src/ccld_complaints/ccld_public_download.py` (module). Reads CSV files from
	`data/raw/ccld`, tolerates rows with extra trailing Complaint Info values
	beyond the 31-column header without crashing, and writes ignored outputs
	under `data/processed/ccld-public-downloads/`:
	`ccld-download-profile.json` (per-file row count, header count, row-width
	warnings, facility type/status/county counts, limitations),
	`ccld-download-profile.csv` (flat per-file summary), and
	`facility-reference.csv` (normalized with columns FacilityNumber,
	FacilityName, FacilityType, ProgramType, Status, City, County, Capacity,
	LicenseFirstDate, ClosedDate, LastVisitDate, SourceFile). Use
	`-FacilityType` and `-Status` to produce a targeted cohort CSV. The
	reference CSV is designed for direct use with `-FacilityReferenceCsv` in
	the stakeholder export. No database writes, schema changes, or network
	requests.
- Added optional `-OnlyFacilityReferenceRows` switch to
	`scripts/export-stakeholder-facility-overview.ps1` (and the corresponding
	`--only-facility-reference-rows` CLI flag). When set alongside
	`-FacilityReferenceCsv`, only facilities whose facility number appears in
	the reference CSV are written to `facility-overview.csv` and
	`substantiated-complaints.csv`; unrelated facilities already loaded in SQLite
	are excluded. Using the switch without a reference CSV fails with a clear
	error. The `only_facility_reference_rows` field is included in
	`manifest.json`.
- Added optional `-FacilityReferenceCsv` parameter to
	`scripts/export-stakeholder-facility-overview.ps1` (and the corresponding
	`--facility-reference-csv` CLI argument). When a facility reference CSV is
	supplied, facilities from that list are included in `facility-overview.csv`
	even when no complaint records are loaded for them; those rows show
	`LoadedComplaintCount=0` and `ComplaintDataLoadedStatus=No complaints
	loaded`. Reference data enriches missing metadata fields (e.g. city) for
	facilities that do appear in the loaded complaints. The facility number
	column is matched case-insensitively using a list of common header aliases.
	Duplicate facility numbers in the reference file are deduplicated
	deterministically (first occurrence wins). Manifest fields
	`facility_reference_csv`, `facility_reference_row_count`, and
	`facility_reference_matched_count` are included when a reference CSV is
	used.
- Added a repeatable local stakeholder facility overview extract script at
	`scripts/export-stakeholder-facility-overview.ps1`. The script reads the
	local SQLite database and writes a timestamped ZIP package under
	`data/processed/stakeholder-extracts/<timestamp>/` containing
	`facility-overview.csv` (per-facility complaint counts including
	substantiated/equivalent counts, date ranges, and source-traceability
	counts), `substantiated-complaints.csv` (individual substantiated/equivalent
	records with source URL, raw hash, and a stable reviewer detail path),
	`README.md` (plain-language scope and limitations note), and `manifest.json`
	(generation metadata and row counts). Substantiated/equivalent matching uses
	the same conservative keyword logic as the hosted triage page. If the
	database is absent or empty, valid empty CSVs with headers, README, manifest,
	and ZIP are produced without failing. Raw narrative allegation text is
	intentionally excluded. No risk scores, severity scores, legal conclusions,
	facility-wide conclusions, verified severity claims, or source-completeness
	claims are made.

- Added a browser-accessible cross-facility substantiated complaint triage page
	at `/reviewer/records/substantiated`. The page lists currently loaded
	complaint records across facilities when the source-derived
	finding/resolution/status indicates substantiated or an equivalent
	source-derived value, and each row includes facility context, complaint/report
	date context when available, the source-derived value, and safe links to
	reviewer detail and source traceability. The page includes plain-language
	caution copy: it is a triage aid, source-derived values are not independently
	verified by RecordsTracker, the list is based only on currently loaded
	records, and an empty state means no currently loaded matches (not that no
	substantiated reports exist in the public source). Existing complaint matrix
	export and complaint CSV export behavior is unchanged.

- Added a local/test complaint review matrix CSV export at
	`/reviewer/records/matrix.csv`. The CSV is Excel-ready for a facility/date
	context and includes source-derived complaint identifiers, key dates, finding,
	allegation categories, source label, source URL, source-traceability cue,
	missing-field cues, loaded-record indicator, and clearly separated
	reviewer-created note/status columns. Export actions are linked from facility
	hub contexts, request/queue results, and reviewer detail when a facility context
	is available. The matrix states that it is a local/test review aid, not a
	certified report, not source verification, not a complaint-coverage
	determination, not a source-completeness proof, and not a legal finding.
	Retrieval behavior, live crawling, connector/extraction behavior,
	source-derived mutation, reviewer-created write behavior, feedback persistence
	or submission, packet lifecycle, final legal export behavior, schemas,
	migrations, correction behavior, assignment, claiming, auth, deployment, legal
	conclusions, complaint-coverage claims, source verification claims, and
	source-completeness claims are unchanged.

- Added a substantiated-only complaint CSV export at
	`/reviewer/records/substantiated.csv`. The CSV is Excel-ready (UTF-8 with BOM,
	CRLF line endings) and is restricted to source-derived complaint records
	where the extracted finding/status is identified as substantiated. The export uses only
	existing source-derived fields plus reviewer-created read seams: it includes
	Facility Name; Facility/License Number; Complaint Received Date; Report Date;
	Visit Date; Date Signed; Finding/Status; Complaint Control Number; Source
	Report URL; Source Traceability Status; Reviewer-created status; and
	Reviewer-created note present. Reviewer-created note text is not exported.
	This is a local/test review aid only and is not a certified report, legal
	finding, or a source-completeness proof.

- Added a hosted Facility Review Intelligence Dashboard at
	`/ccld/facilities/intelligence`. The dashboard uses existing public
	facility-directory rows and supported uploaded public facility-summary signals
	to group facilities by transparent review-priority indicators such as complaint
	activity, citation activity, POC activity, recent visit activity, long periods
	since last visit, high capacity, and closed status. It provides filters, sorting,
	visible explanations for why each facility appears, and direct navigation to
	facility hubs, complaint requests, and reviewer queues. This is presentation-
	only: retrieval behavior, crawling behavior, connector/extraction behavior,
	reviewer-created write behavior, packet lifecycle, exports, schemas, migrations,
	auth, deployment, legal conclusions, risk scores, wrongdoing determinations,
	complaint-coverage claims, source-verification claims, and source-completeness
	claims are unchanged.

- Improved CCLD request and queue friction cues for the local/test review loop.
	Request context cards now label the request context source, facility context
	cue, and recovery actions for facility hubs, signal-only facility hubs, the
	facility review priority list, and new complaint request flow. Request no-match
	states now say when no loaded local/test records matched the current
	facility/date context and keep recovery links visible. Queue decision actions
	now include facility review priority navigation while preserving reviewer detail,
	packet preview/draft, same queue, filter, and feedback paths. Complaint
	retrieval behavior, live crawling, connector/extraction behavior,
	source-derived mutation, reviewer-created write behavior, feedback persistence
	or submission, packet lifecycle, export behavior, schemas, migrations,
	correction behavior, assignment, claiming, legal conclusions, complaint-
	coverage claims, source verification claims, and source-completeness claims are
	unchanged.

- Improved reviewer detail usability cues for the local/test review loop. Reviewer
	detail now labels facility context as a directory-backed facility hub,
	signal-only facility hub, or manual request context when the active local/test
	inputs support that distinction; it also surfaces clearer next actions for the
	facility hub, facility review priority list, same facility/date queue, packet
	preview/draft, complaint request, and feedback. The page keeps source-derived
	values, source-traceability cues, and reviewer-created note/status boundaries
	separate. Complaint retrieval behavior, live crawling, connector/extraction
	behavior, source-derived mutation, reviewer-created write behavior, feedback
	persistence/submission, packet lifecycle, export behavior, schemas, migrations,
	correction behavior, assignment, claiming, legal conclusions, complaint-
	coverage claims, source verification claims, and source-completeness claims are
	unchanged.

- Fixed facility review signal parsing for supported uploaded public summary rows
	that include trailing repeated complaint-detail columns after the supported
	summary header. The loader now uses only the supported leading summary fields,
	ignores trailing detail values, and still skips rows that are too short or have
	unsupported facility identifiers. Signal-only facility hubs can now render for
	those facilities without exposing trailing complaint-detail values. Retrieval,
	extraction, schemas, migrations, source-derived records, reviewer-created state,
	feedback, packets, exports, correction, assignment, claiming, source
	verification, complaint coverage, source completeness, and legal conclusions are
	unchanged.

- Added signal-only facility hub support for facilities that appear in supported
	uploaded public summary signals but not in the active preloaded facility
	directory. When a directory row is not available locally, the facility hub can
	show bounded uploaded public summary fields, review cues, existing complaint
	request/review links, and clear not-directory/not-source-verification/not-
	complaint-coverage/not-source-completeness/not-legal-finding boundaries.
	Retrieval behavior, facility review signals parsing, reviewer-created state,
	note/status behavior, feedback persistence, packet/export lifecycle, schemas,
	migrations, correction, assignment, claiming, legal conclusions, complaint-
	coverage claims, source verification claims, and source-completeness claims are
	unchanged.

- Aligned hosted CCLD sample facility-directory examples with active preloaded
	facility data. Facility lookup, facility hub, evidence capture, acceptance, and
	README examples now use known loaded preloaded facility-directory example
	`434417302` for facility hub links, while `157806098` remains clearly scoped to
	the manual complaint request / seeded complaint review context. Retrieval
	behavior, facility review signals, reviewer-created state, note/status
	behavior, feedback persistence, packet/export lifecycle, schemas, migrations,
	correction, assignment, claiming, legal conclusions, complaint-coverage claims,
	and source-completeness claims are unchanged.

- Added a hosted CCLD facility review priority list based on existing facility
	review signals from supported uploaded public licensing/visit/citation summary
	fields. The route groups and filters facilities by transparent review cues such
	as complaint visit activity, citation indicators, POC indicators, recent visit
	activity, closed status, high capacity, long gap since last visit, and multiple
	signal types, with each row linking to the facility review hub. This is
	grouping over uploaded public summary fields only. Retrieval behavior, live
	crawling, connectors, extraction behavior, schemas, migrations, source-derived
	complaint records, reviewer-created writes, feedback persistence, packet/export
	lifecycle, correction, assignment, claiming, legal conclusions, complaint-
	coverage claims, source verification, and source-completeness claims are
	unchanged.

- Added hosted CCLD facility review signals on the facility hub from supported
	uploaded public licensing/visit/citation summary CSV fields. The first supported
	shape is the shared 31-column CCLD program summary CSV shape used by local
	files such as `24HourResidentialCareforChildren06072026.csv`,
	`ChildCareCenters06072026.csv`, `CHILDCAREHOMEmorethan806072026.csv`,
	`HomeCare06072026.csv`, and `FosterFamilyAgencies06072026.csv`. The loader
	treats facility numbers as strings, deduplicates exact duplicate rows,
	aggregates distinct rows by facility, skips malformed/shifted or unsupported
	rows safely, and shows bounded scalar visit, complaint-visit, citation, POC,
	status, capacity, license-date, and last-visit-date review cues. Retrieval
	behavior, live crawling, connectors, extraction behavior, schemas, migrations,
	source-derived complaint records, reviewer-created writes, feedback
	persistence, packet/export lifecycle, correction, assignment, claiming, legal
	conclusions, complaint-coverage claims, source verification, and source-
	completeness claims are unchanged.

- Added a hosted CCLD facility review hub route for selected facility-directory
	results. Facility lookup results now include an `Open facility review hub`
	action alongside the existing complaint-request action. The hub shows safe
	facility-directory fields, separates directory data from complaint records,
	surfaces available local/test complaint-review context when existing loaded
	data supports it, and links to existing request, reviewer queue, packet
	preview, packet draft, and facility lookup routes. Retrieval behavior,
	schemas, migrations, connectors, extraction behavior, source-derived records,
	reviewer-created writes, note/status behavior, feedback persistence,
	packet/export lifecycle, correction, assignment, claiming, legal conclusions,
	complaint coverage, and source-completeness claims are unchanged.

- Added preloaded hosted CCLD facility-directory lookup support for the
	CDSS/CHHS facility CSV shape with `FAC_NBR`, `NAME`, `PROGRAM_TYPE`,
	`STATUS`, `CAPACITY`, location, county, and facility-type fields. The lookup
	and request-page type-ahead can use an ignored full local CSV from
	`CCLD_FACILITY_REFERENCE_CSV` or `data/raw/ccld/facility-reference.csv`, keep
	facility numbers as strings, deduplicate exact duplicate rows, preserve
	distinct duplicate facility-number rows, and display only safe scalar
	directory fields. Full raw CSVs remain uncommitted and ignored. Retrieval
	behavior, schemas, migrations, connectors, imports, source-derived records,
	reviewer-created writes, legal conclusions, complaint coverage, and source-
	completeness claims are unchanged.

- Improved hosted reviewer detail source-traceability clarity. Reviewer detail
  now explains what visible traceability cues mean, what locally missing
  traceability cues do and do not mean, what to check before reviewer-created
  notes/statuses or packet preparation, and when to use feedback for confusing
  traceability. Retrieval behavior, schemas, migrations, source-derived records,
  reviewer-created writes, note/status behavior, feedback submission/persistence,
  packet lifecycle, legal conclusions, source verification, and source-
  completeness claims are unchanged.

- Improved hosted CCLD feedback context starter clarity. Feedback links with
  safe handoff context now show an editable suggested issue starter in the
  existing description field, using only sanitized workflow, facility/date,
  retrieval context/status, safe job identifier, and visible prompt text when
  available. Feedback persistence, GitHub issue submission behavior, retrieval
  execution, schemas, migrations, source-derived records, reviewer-created
  writes, exports, packet lifecycle, legal conclusions, and source-completeness
  claims are unchanged.

- Improved hosted CCLD retrieval feedback handoff context. Request results,
  retrieval setup-required states, retrieval job summaries, retrieval job
  history, and retrieval job detail now link to feedback with bounded safe
  CCLD-only context for the surface, facility/date request, retrieval status,
  and safe job identifier when available. Feedback persistence, retrieval
  execution, schemas, migrations, source-derived records, reviewer-created
  writes, exports, packet lifecycle, legal conclusions, and source-completeness
  claims are unchanged.

- Improved hosted CCLD retrieval/status progress clarity. Request results now
	state whether records came from already-loaded local/test rows or a submitted
	controlled retrieval job, identify the current state, show when records are
	ready, and name the next safe action. Retrieval job summary, history/detail,
	help, feedback examples, and the copyable feedback checklist now reinforce the
	loaded-record versus job-status boundary without changing retrieval behavior,
	schemas, migrations, exports, packet lifecycle, reviewer-created writes,
	source-derived records, feedback persistence, legal conclusions, or source-
	completeness claims.

- Improved the README live-mode queue and reviewer-detail screenshot
	composition so the public landing page better shows the review-priority
	decision flow, recommended next record action, source traceability summary,
	reviewer-created state separation, and safe note/status action context. This
	is documentation and asset composition only; it does not change application
	behavior, retrieval behavior, schemas, migrations, packet lifecycle, export
	behavior, reviewer-created writes, or committed ignored evidence artifacts.

- Replaced the README fixture/mock screenshots with reviewed live-mode hosted
	CCLD RecordsTracker screenshots for the start page, retrieval-result review
	queue, and reviewer detail workflow. The README remains product-oriented and
	no application behavior, retrieval behavior, schemas, migrations, packet
	lifecycle, export behavior, reviewer-created writes, or ignored evidence
	artifacts were added.

- Clarified hosted reviewer source-confidence next steps across queue, reviewer
	detail, help, and feedback copy so testers know to check source traceability,
	use cautious reviewer-created notes/status, report confusing cues through
	feedback, and continue from the same queue context without treating local/test
	cues as verification, completeness, correction, assignment, or legal
	sufficiency.

- Refreshed the root README as a product-oriented public repository landing page.
	The README now leads with the hosted CCLD RecordsTracker review workflow,
	target users, current milestone status, safe fixture/mock screenshots,
	public-source and packet-readiness boundaries, and lower-priority local setup
	commands. This is documentation and presentation only; it does not add routes,
	schemas, migrations, extraction behavior, retrieval behavior, export behavior,
	packet lifecycle state, source-derived mutation, reviewer-created writes,
	feedback persistence, legal conclusions, source-completeness claims, or
	committed ignored evidence folders/ZIPs.

- Improved hosted reviewer export-readiness clarity. Packet preview and packet
	draft now define packet readiness as local/test review readiness for manual
	review, browser copy, or browser print after checking active facility/date
	context, included records, source-derived values, source traceability,
	reviewer-created note/status cues, and possible correction-readiness concerns.
	Feedback and help cues now name packet/export-readiness confusion and preserve
	the boundary that packet pages are not legal reports, final exports, certified
	reports, product-generated exports, packet lifecycle state, or source-
	completeness proof. This does not add schemas, migrations, export generation,
	export persistence, packet lifecycle, retrieval behavior, correction behavior,
	source-derived mutation, reviewer-created writes from GET rendering, note/status
	behavior changes, legal conclusions, source-completeness claims, or committed
	evidence files.

- Improved hosted reviewer status-filter accessibility and readability. The
	local/test CCLD request queue now states the active reviewer-created status
	filter, records shown under that filter, total records in the same
	facility/date queue, available status filters, filtered-empty recovery, and
	safe feedback cues in visible text. This preserves existing reviewer-created
	status behavior and does not add routes, schemas, migrations, persistence,
	retrieval behavior, workflow-engine state, reviewer-created state kinds,
	note/status behavior changes, packet export behavior, source-derived mutation,
	correction behavior, feedback persistence, legal conclusions,
	source-completeness claims, or committed evidence files.

- Improved hosted reviewer keyboard-flow accessibility. Shared workflow pages now
	state keyboard-flow guidance in text, facility/request/reviewer/feedback forms
	expose clearer helper text for moving through existing controls, and local
	acceptance/evidence checks look for those cues across the hosted review path.
	This does not add routes, schemas, migrations, persistence, retrieval behavior,
	workflow-engine state, reviewer-created state kinds, note/status behavior
	changes, packet export behavior, source-derived mutation, correction behavior,
	feedback persistence, legal conclusions, source-completeness claims, or
	committed evidence files.

- Improved hosted correction-readiness guidance. Reviewer detail, source
	traceability, note/status guidance, save confirmations, packet preview/draft,
	help, and feedback now explain how testers should check source traceability
	first, capture possible correction concerns in reviewer-created notes or
	feedback for now, and understand that the public CCLD portal remains the
	source of record. This guidance does not add canonical fields, schemas,
	migrations, correction tables, correction persistence, correction forms,
	correction write routes, correction status values, correction decision
	behavior, annotation workflow, connector behavior, retrieval behavior,
	extraction behavior, exports, packet lifecycle changes, source-derived
	mutation, reviewer-created writes from GET rendering, note/status behavior
	changes, legal conclusions, source-completeness claims, or committed evidence
	files.

- Improved hosted source-traceability review readiness. Queue/worklist, reviewer
	detail, packet preview/draft, help, and feedback cues now more clearly label
	existing source traceability values, missing local/test traceability values,
	and check-before-relying guidance for source-derived values without adding
	source fields, schemas, migrations, connector behavior, retrieval behavior,
	extraction behavior, exports, source-derived mutation, reviewer-created writes
	from GET rendering, legal conclusions, or source-completeness claims.

- Improved hosted tester-readiness acceptance closure. The non-mutating hosted
	reviewer acceptance verifier now checks the primary local/test workflow route
	set across home, facility lookup, request/context, review queue, reviewer
	detail, packet preview/draft, feedback, and help; reports route-level
	acceptance status; preserves packet empty/context assertions and draft
	workflow-indicator skip/pass behavior; and packages captured evidence folders
	as ignored local review ZIP artifacts without adding retrieval behavior,
	persistence, schema changes, migrations, product packet generation, export
	lifecycle, source-derived mutation, reviewer-created writes from GET rendering,
	legal conclusions, or committed evidence files.

- Improved hosted packet copy/print preparation guidance. Packet preview now
	identifies the local/test preparation scope, adds a visible before-copying-or-
	printing checklist, clarifies browser copy/print use, source-traceability
	meaning, reviewer-created status/note attention, and feedback handoff for
	copy/print concerns; packet draft now opens with compact browser copy/print
	preparation guidance and explicit not-legal-report, not-final-export,
	not-certified-report, and not-source-completeness-proof boundaries without
	adding export generation, packet lifecycle, persistence, schema changes,
	retrieval changes, source-derived mutation, reviewer-created writes from GET
	rendering, or evidence files.

- Improved hosted review-session accessibility. The shared workflow rail now
	exposes screen-reader-readable step purpose text, and facility lookup controls
	use more descriptive search, selected-facility change, and facility-use action
	text while preserving existing local/test workflow behavior, source/reviewer
	boundaries, retrieval behavior, persistence, and packet/feedback behavior.

- Improved the hosted review-session start handoff. Home, facility lookup,
	request intake, and help now make the first steps clearer: start with facility
	lookup or direct facility/license entry, choose a complaint date range, load or
	retrieve local/test complaint records, continue through queue, reviewer detail,
	packet preparation, and feedback, while preserving source-of-record,
	local/test, no-legal-conclusion, no-final-export, and no-source-completeness
	boundaries without changing retrieval behavior or adding persistence.

- Improved the hosted feedback handoff review loop. Queue/worklist, filtered
	queue recovery, reviewer detail, reviewer-created save confirmation, packet
	preview, and packet draft now link to `/feedback` with bounded safe local/test
	context so testers can report confusing queue order, missing or unexpected
	records, source-traceability questions, note/status action confusion, packet
	readiness concerns, copy/print preparation concerns, wording, keyboard flow, or
	accessibility issues without adding feedback persistence, GitHub Projects
	behavior, automatic submission, schema changes, retrieval changes, source-
	derived mutation, reviewer-created writes from GET rendering, or legal
	conclusions.

- Improved packet preview and packet draft as local/test review-readiness
	checkpoints. The packet surfaces now show included-record readiness counts,
	source-traceability cues, reviewer-created status/note cues, records needing
	source check or reviewer attention, and review-before-copy/print guidance
	while preserving the local/test preparation boundary with no packet lifecycle,
	export persistence, server-side PDF/Word/ZIP generation, schemas, migrations,
	retrieval changes, source-derived mutation, or legal conclusions.

- Improved hosted reviewer detail as the continuation of the priority worklist.
	Detail pages now show active facility/date request context, selected record
	identity, cautious worklist-priority rationale, source-derived values to check
	first, same-context queue return, next-record guidance, local/test packet
	preparation links, and clearer cautious note/status guidance without changing
	note/status writes, audit behavior, source-derived records, schemas,
	migrations, retrieval, auth, exports, or legal conclusions.

- Improved the hosted local/test CCLD review-priority queue as a decision screen.
	The queue now shows active facility/date context, local/test reference source,
	source-derived complaint counts, reviewer-created status/note cues, review-flag
	and source-traceability counts, a recommended next-record action with cautious
	reasons, record-level decision cards, filtered recovery, and local/test packet
	preparation links without adding persistence, workflow-engine state, retrieval
	behavior, exports, schemas, migrations, auth, or legal conclusions.

- Added acceptance checklist and non-mutating verification script for the hosted reviewer local/test flow: `docs/developer/hosted-reviewer-acceptance.md` and `scripts/verify-hosted-reviewer-acceptance.ps1`. The verifier defaults to non-mutating GET checks, can optionally run evidence capture, and checks packet-preview/draft empty/context routes and draft workflow-step assertions.

- Added a print-ready local/test attorney review packet draft at
	`/reviewer/packet/draft`. The draft preserves facility/date context, provides
	browser Print / Save as PDF guidance, summarizes included complaint records,
	review flags, findings, reviewer-created status/note cues, source traceability
	readiness, limitations, and a static copyable packet summary. It does not
	create server-side PDFs, Word files, ZIPs, CSVs, downloadable legal packets,
	export persistence, lifecycle state, delivery, archival, deletion, schemas, or
	migrations.

- Added a local/test attorney review packet preview at `/reviewer/packet/preview`.
	The preview summarizes the current facility/date context, included complaint
	records, reviewer-created status/note cues, cautious inclusion reasons, review
	flags, findings, and source traceability readiness without generating export
	files or mutating source-derived, reviewer-created, audit, import, or
	operational metadata. It is a preparation view only, not a legal report, final
	export, production packet, or source-completeness proof.

- Made hosted reviewer detail an intentional guided review action screen. The
	page now leads from complaint overview to why the record is flagged, a
	near-top `Record review action` panel for existing reviewer-created status and
	note controls, source traceability summary, and record/key-date context. Save
	confirmations now state what reviewer-created state changed, what source-
	derived records did not change, and how to return to the facility queue or
	open the next priority record. This uses the existing note/status and audit
	paths only; no schema, migration, retrieval, export, auth, deployment, or new
	persistence domain changed.

- Added a facility-centered attorney case brief to successful hosted CCLD
	retrieval results and the reviewer queue. The brief summarizes facility scope,
	complaint record counts, review flags, findings represented, source
	traceability availability, reviewer-created notes/statuses, and a suggested
	first record to open with cautious source-derived reasons. Reviewer detail now
	also shows a compact "Why this record is flagged" section near the top. This
	uses existing source-derived and reviewer-created state only; no retrieval,
	extraction, schema, migration, auth, export, or deployment behavior changed.

- Added a repeatable hosted UI evidence packet workflow: `capture-hosted-ui-evidence.ps1`
	captures canonical RecordsTracker routes from an already-running local hosted
	URL into ignored `data/processed/ui-evidence/` with manifest, route status,
	HTML/text snapshots, lightweight accessibility summaries, assertion notes, and
	optional screenshots when local tooling is available. Added a convenience
	wrapper, developer documentation, and tests without changing app routes,
	retrieval, extraction, schemas, auth, reviewer-created state, exports, or
	deployment behavior.

- Reduced the hosted CCLD RecordsTracker UI with a So What information-
	architecture pass: Home now has one dominant start decision, Facility no longer
	renders a generic empty results panel before search, Retrieve focuses on
	facility/date intake, result pages collapse diagnostics, queue guidance,
	feedback checklists, and advanced local/operator actions, Jobs collapse
	runtime/boundary guidance and table views, Reviewer detail keeps summary,
	traceability, and reviewer-created state first while moving navigation/help
	handoffs into details, Feedback is form-first, and Help no longer repeats the
	workflow indicator. The change preserves CCLD-only scope, live/fixture mode
	separation, source traceability, cautious legal-boundary language, accessibility,
	and existing retrieval behavior.

- Implemented the final product-ready hosted CCLD visual design: ordinary page
	sections are no longer framed as stacked scaffold cards, the shared shell uses
	the specified restrained legal-review palette, the workflow rail is compact and
	non-card-like, Home is a launch screen, Facility is a search/select intake page,
	Retrieve success and recovery states prioritize primary actions over diagnostics,
	Retrieval Jobs render card-based status lists with table details collapsed,
	Reviewer queue cards show human-readable date labels and review-flag summaries,
	Reviewer detail uses a summary-first top grid with reviewer-created state beside
	the complaint summary, and Feedback uses a support-intake layout with safety and
	examples collapsed. No backend behavior, schemas, migrations, sources, exports,
	extraction behavior, or unsupported legal conclusions were added.

- Redesigned the hosted CCLD UI as an attorney-focused public-record review
	workspace: the product shell is now `CCLD RecordsTracker`, the workflow strip is
	compact and legal-review oriented, home starts with facility complaint review,
	facility lookup uses `Review this facility`, retrieval results lead with
	`Complaint records ready for attorney review`, recovery and job pages keep
	technical details secondary, reviewer queue/detail pages lead with complaint
	summaries, source traceability, cautiously labeled review flags, and
	reviewer-created/source-derived separation, and feedback/help use legal-review
	support language. The redesign uses existing safe source-derived and
	reviewer-created values only; it does not add backend behavior, schemas,
	migrations, exports, sources, or unsupported legal/facility-wide conclusions.

- Fixed route-aware top navigation: `/ccld/help` now highlights `Help` instead
	of `Retrieve`. Root cause: `_render_help_page()` called the shared `_page()`
	helper without setting `active_path`, so it inherited the default
	`CCLD_RECORD_REQUEST_PATH`. Fix: pass `active_path=CCLD_HELP_PATH` explicitly.
	Also fixed `/ccld/retrieval/jobs/detail` error pages (not-found and invalid-ID)
	that similarly defaulted to showing `Retrieve` as active; they now show `Jobs`.
	Added `active_path` parameter to `_render_message_page()`. Expanded
	`_step_id_for_path()` to cover `/ccld/help` and sub-paths of `/reviewer` and
	`/ccld/retrieval/jobs`. Added 4 regression tests covering exact `aria-current`
	placement for all primary nav routes and confirming no substring-match false
	positives.
- Replaced the facility selector on `/ccld/facilities` and `/ccld/records/request`
	with a polished inline type-ahead combobox: accessible label/input pair,
	concise placeholder, JSON-embedded reference data, keyboard-navigable
	suggestion list, selected-facility confirmation card, and a "Change" affordance
	— all in plain vanilla JS with no external dependencies. Internal scaffold
	labels (e.g., "Tiny committed CCLD facility fixture fallback") no longer appear
	in the primary UI; they are confined to a collapsed `<details>` block. A
	"Limited reference list" note appears when only the tiny fallback is active.
	The `/ccld/facilities` result cards now carry descriptive `aria-label` values
	on their "Use for retrieval" links.
- Productized the hosted `CCLD RecordsTracker Pilot` guided UI so it no longer
	foregrounds scaffold-style navigation or runtime language: the stepper is more
	compact, Home is a simpler launch screen, developer/operator commands are
	collapsed, primary navigation excludes diagnostic links, request recovery keeps
	technical preparation details collapsed, and the reviewer queue leads with a
	worklist, `Open next record`, compact status counts, and collapsed technical
	runtime details while preserving behavior and safety boundaries.
- Replaced the hosted CCLD pilot page stack with a guided `CCLD RecordsTracker
	Pilot` workflow assistant: launch-screen home, compact functional stepper,
	progressive facility/date/retrieve request flow, focused imported-record and
	recovery result screens, product-grade facility selector, status-center job
	pages, worklist-style reviewer queue, summary-first complaint review workspace,
	card-prefilled feedback, and collapsible help without adding frontend
	dependencies, non-CCLD sources, auth/session/account work, exports, public
	deployment, or unrelated workflow features.
- Added `scripts/run-hosted-complaint-retrieval-live.ps1`, an explicit local
	live-public-CCLD startup command that enables browser-triggered complaint
	retrieval with ignored raw storage, real public CCLD HTTP retrieval, safe live
	mode status labels, and more specific no-import warnings while preserving the
	fixture/mock demo path.
- Added `scripts/run-hosted-complaint-retrieval-demo.ps1`, a one-command local
	fixture-backed complaint retrieval demo that starts the hosted scaffold with
	explicit local-dev auth, retrieval enablement, ignored raw storage, and
	mock-success retrieval so `/ccld/records/request` can create a safe local job
	without manual environment setup.
- Tightened controlled CCLD retrieval so hosted complaint retrieval jobs discover
	complaint-section report links for the requested facility, prefilter those links
	to the requested date range before fetching, preserve raw/source traceability,
	and report safe no-match warnings without broadening beyond complaint records.
- Polished the existing local/test hosted tester UI shell with a shared visual
	layout, consistent navigation, stronger focus/table/form styling, clearer home
	start actions, and feedback guidance without adding routes, workflows, frontend
	dependencies, auth, retrieval capability, exports, or deployment behavior.
- Added the final QNAP pilot readiness completion marker to the readiness index,
	clarifying that the documented pre-invite operator path is complete after real
	pilot inputs, the access-method decision, and the evidence packet are supplied,
	while production OIDC, production deployment, anonymous public access, and
	broader product functionality remain unimplemented.
- Added `docs/developer/qnap-pilot-access-method-decision.md`, a concise
	pre-invite operator scaffold for recording the temporary QNAP pilot access
	method, limits, owner, scope, expiration, revocation path, evidence-packet
	relationship, and deferred production-auth work before any external tester
	link, credential, network rule, VPN rule, or reverse proxy route is shared.
- Added `scripts/build-qnap-pilot-evidence-packet.ps1`, an optional read-only
	local command that assembles a redacted Markdown QNAP pilot evidence packet
	under ignored `data/processed/qnap-pilot-evidence/` from the existing verifier,
	seeded import evidence, route evidence, and operator decisions without creating
	an audit export, product export packet, public report, GitHub issue, or
	certification.
- Added `docs/developer/qnap-pilot-readiness-index.md`, an ordered pre-invite
	readiness path that ties together QNAP scope, environment setup, seeded import
	evidence, route evidence, auth readiness, tester invitation decisions, evidence
	packet contents, do-not-invite gates, and deferred work.
- Added `docs/developer/qnap-pilot-tester-invitation-decision.md`, a concise
	operator decision gate for who may be invited to the QNAP pilot, role/scope
	limits, approval and revocation expectations, deferred real auth/invitation
	implementation, required evidence packet contents, and no-secret/no-conclusion
	guardrails before inviting early external stakeholder organization testers.
- Added `scripts/summarize-qnap-pilot-route-evidence.ps1`, an optional GET-only
	QNAP pilot route evidence command that probes expected hosted routes, accepts
	expected protected/setup-required/safe-empty states, and avoids imports,
	retrieval, GitHub calls, response-body printing, secrets, raw artifacts, raw
	server paths, and legal/completeness conclusions.
- Added `docs/developer/qnap-pilot-auth-readiness.md`, a concise QNAP pilot
	auth readiness guide covering production auth mode, local-dev auth exclusion,
	safe `/auth/status` evidence, deferred real OIDC/login/session behavior,
	host-local provider placeholder handling, and no-secret/no-local-dev guardrails
	before inviting early testers.
- Added `scripts/summarize-qnap-pilot-seeded-import-evidence.ps1`, an optional
	read-only QNAP pilot evidence command that summarizes env readiness decisions
	and PostgreSQL-backed hosted import/source-derived counts without running
	imports, retrieval, live CCLD calls, GitHub calls, or printing secrets, raw
	artifacts, raw server paths, or legal/completeness conclusions.
- Added `docs/developer/qnap-pilot-seeded-import-evidence.md`, a concise
	operator evidence guide for proving a QNAP pilot can see PostgreSQL-backed
	validated CCLD source-derived records before inviting testers. The guide covers
	preconditions, migration/current checks, import batch and source-derived row
	counts, safe traceability linkage evidence, route evidence, feedback/retrieval
	decisions, backups, and no-completeness/no-legal-conclusion guardrails.
- Added `docs/developer/qnap-pilot-operator-checklist.md`, a concise operator
	checklist for QNAP pilot scope, preflight, `.env` setup, verifier and Compose
	checks, startup, migrations, raw artifact storage, route verification,
	local-dev-only mock-success validation, readiness evidence, backups, rollback,
	and do-not-do guardrails before inviting early external stakeholder organization testers.
- Hardened the QNAP pilot environment template and verifier. `.env.example` now
	uses clearer QNAP pilot sections, keeps GitHub feedback intentionally disabled
	by default, keeps mock-success retrieval blank by default, and the verifier now
	checks missing env files, unsafe local-dev auth, mock-success misuse, retrieval
	without raw storage, half-configured GitHub feedback, intentional disabled
	states, placeholder warnings, and committed-looking token patterns.
- Added a QNAP hosted tester pilot workflow checker at
	`scripts/verify-qnap-pilot-workflow.ps1`. It validates required untracked `.env`
	keys, PostgreSQL/page-data/auth/retrieval raw-storage settings, Compose config,
	optional running container/PostgreSQL/Alembic state, and optional route probes
	without committing secrets, adding deployment automation, enabling production
	fake data, or adding retrieval capability.
- Added an explicit local-dev controlled retrieval demo mode,
	`CCLD_RETRIEVAL_DEMO_MODE=mock-success`, for scaffold validation. When local-dev
	auth, retrieval enablement, and raw storage are explicitly configured, the
	browser can run a fixture-backed successful retrieval that creates a job,
	preserves mocked raw artifact/hash metadata through the existing path, imports
	source-derived rows, and links to status, history, detail, and queue pages
	without making live CCLD calls or enabling fake behavior in production mode.
- Added a small controlled CCLD retrieval job detail page at
	`/ccld/retrieval/jobs/detail?job_id=`. History rows now link to a read-only
	detail view for one job showing safe request context, state, timestamps,
	imported-record count, warning/error summaries, raw-artifact-preserved status,
	review-queue links when records were imported, and feedback/help/history links
	without adding audit export, raw artifact viewing, retrieval capability, new
	record types, live test calls, or broad UI changes.
- Added a small controlled CCLD retrieval job history/status page at
	`/ccld/retrieval/jobs`. The page lists recent jobs from existing operational
	metadata, shows facility/date/type request context, state, timestamps, import
	counts, safe warning/error summaries, status messages, review-queue links
	when records were imported, and `/feedback` guidance without adding audit
	export, retrieval capability, new record types, raw path display, live test
	calls, or broader UI redesign.
- Improved controlled CCLD retrieval status usability. Setup-required, validation,
	queued/running/completed/completed-with-warnings/failed/rate-limited, and result
	states now use clearer tester and operator guidance, include safe request/job
	context and result counts, distinguish warning states from failures, and point
	confusing states to `/feedback` without broadening retrieval beyond the
	complaint-only ADR-0016 slice.
- Implemented the first controlled browser-triggered, server-executed CCLD
	retrieval job slice. The CCLD request page now includes record type selection
	for complaint records or all supported record types, currently resolving to
	complaints only; can trigger a server-side retrieval job when configured;
	preserves raw source artifacts and SHA-256 hashes; imports validated
	source-derived rows into PostgreSQL; renders safe job state/result counts; and
	links completed jobs back to the hosted queue. Tests use mocked CCLD retrieval
	only and cover validation, auth blocking, source allowlists, rate limits, safe
	failures, no-secret output, feedback separation, and existing page/reviewer
	behavior. Production OIDC, cloud deployment, non-CCLD sources, direct browser
	crawling, statewide crawling, GitHub feedback export, GitHub Projects, and
	legal/completeness conclusions remain deferred.
- Added ADR-0016 approving a narrow browser-triggered, server-executed CCLD
	retrieval job boundary for future implementation. The decision keeps retrieval
	CCLD-only, authenticated, facility/date/type bounded, server-side, raw-source-
	preserving, PostgreSQL-imported, rate-limited, secret-safe, and test-mocked,
	while leaving live retrieval implementation, connector code changes, schema
	changes, production OIDC, deployment changes, GitHub feedback export, GitHub
	Projects, UI redesign, non-CCLD sources, direct browser crawling, statewide
	crawling, and legal/completeness conclusions deferred.
- Added server-side GitHub Issues tester feedback intake at `/feedback` with an
	accessible form, exact feedback type options for bug/problem reports, feature
	requests, data connector/source requests, wording/navigation feedback, and
	other feedback, safe validation/unconfigured/success/failure
	states, server-side `GITHUB_FEEDBACK_REPO` and `GITHUB_FEEDBACK_TOKEN`
	configuration, label-based classification, mocked-client tests, and no local
	feedback persistence, live GitHub calls in tests, token exposure, GitHub
	Projects setup, issue-type dependency, schema changes, retrieval jobs, or
	source-derived mutations.
- Added a cloud-portability deployment guide comparing QNAP Docker, AWS, Azure,
  DigitalOcean, Render, Fly.io, Railway, Supabase, and Neon paths for the hosted
  CCLD runtime. The guide separates app runtime, PostgreSQL, raw file storage,
  secrets, backups, custom domains/HTTPS, and future retrieval jobs without
  adding cloud deployment, provider credentials, paid-service dependency, hosted
  URLs, provider lock-in, or production launch claims.
- Changed core hosted page data selection so production-style runtime defaults to
	PostgreSQL-backed page data via `CCLD_HOSTED_PAGE_DATA_MODE=postgres`, while
	fixture/demo reads are isolated behind explicit `fixture-demo` mode. Facility
	lookup can now render from staged PostgreSQL source-derived facility records,
	request queues and reviewer detail continue to use the existing database-backed
	source-derived and reviewer-created route contexts, and missing PostgreSQL
	setup shows safe operator guidance without weakening source traceability,
	mutating source-derived records, exposing raw narrative fields, or adding live
	crawling, cloud-specific code, retrieval jobs, data dumps, or secrets.
- Added the first provider-agnostic hosted tester auth runtime boundary for the
	external stakeholder organization pilot direction: production mode now blocks anonymous browser workflow
	routes, explicit local-dev mode enables the fixture tester actor for local
	scaffold testing, `/auth/login`, `/auth/logout`, and `/auth/status` expose safe
	placeholders/status only, reviewer pages show a safe signed-in tester label,
	QNAP/env docs list OIDC/OAuth2 placeholder variables, and focused tests cover
	production blocking, local-dev opt-in, role/scope permissions, disabled or
	revoked actors, out-of-scope actors, and no-secret output without adding custom
	password storage, sessions, cookies, token handling, raw provider claims,
	provider secrets, hosted URLs, or the user's employer-specific assumptions.
- Added a portable QNAP-first Docker Compose runtime envelope for the hosted CCLD
	scaffold with a Python app container, PostgreSQL container, named volumes,
	health checks, Alembic startup migration guidance, no-secret `.env.example`,
	QNAP deployment notes, cloud portability notes, and static tests for the Docker
	and environment examples without adding production auth, hosted deployment,
	browser-triggered live retrieval, connector execution, schema changes, or
	optional paid platform dependencies.
- Improved first-run local/test CCLD review session orientation across home,
  request/help, queue, reviewer detail, and feedback checklist wording so testers
  can follow facility lookup, request context, loaded local/test queue, reviewer
  detail source review, note/status confirmation, same-queue refresh, next-record
  continuation, and manual checklist copy behavior without adding saved sessions,
  persisted queue state, duplicate checklist behavior, feedback persistence,
  schema changes, auth, workflow-engine behavior, live browser retrieval,
  connector execution, artifact building from browser requests, or non-CCLD scope.
- Improved local/test CCLD queue-to-detail checklist continuity so testers know
	queue observations and reviewer-detail observations belong in the same existing
	manual feedback checklist without adding duplicate checklist behavior, feedback
	persistence, export behavior, schema changes, parser/extraction changes,
	source scoring, source verification workflow, live browser retrieval,
	connector execution, or non-CCLD scope.
- Improved local/test reviewer detail feedback checklist bridge cues so testers
	can carry record-specific source traceability, source-confidence, field-note,
	note/status confirmation, and return-to-queue observations into the existing
	manual feedback checklist without adding a duplicate checklist, feedback
	persistence, export behavior, schema changes, parser/extraction changes,
	source scoring, source verification workflow, live browser retrieval,
	connector execution, or non-CCLD scope.
- Improved local/test reviewer detail field-note guidance so testers can phrase
	reviewer-created notes/status observations cautiously after source traceability
	and source-confidence review without adding automated note generation, parser,
	extraction, schema, persistence, source scoring, source verification workflow,
	new note fields, workflow automation, live browser retrieval, connector
	execution, or non-CCLD scope.
- Improved local/test reviewer detail and queue source-confidence cues so testers
	can see present source-derived fields, missing local/test fields, existing
	proxy flags, and source-traceability review reminders without adding parser,
	extraction, schema, persistence, automated source verification, queue
	assignment, workflow-engine behavior, live browser retrieval, connector
	execution, or non-CCLD scope.
- Improved local/test CCLD terminology consistency across home, facility lookup,
	request/help, queue, reviewer detail, note/status, no-match/load, filtered-
	empty, next-record, and manual feedback checklist wording without changing
	behavior, persistence, schema, queue assignment, workflow-engine behavior,
	live browser retrieval, connector execution, or non-CCLD scope.
- Improved local/test CCLD queue filtered-empty recovery guidance so testers can
	see when a reviewer-status filter hides all rows, clear the filter for the same
	facility/date request context, and report confusing filter behavior without
	adding persisted queue state, assignments, workflow-engine behavior, schema
	changes, live browser retrieval, connector execution, or non-CCLD scope.
- Improved local/test reviewer detail next-record navigation cues so testers know
	how to return to the same CCLD facility/date queue, resubmit when needed, and
	use refreshed suggested-next-record guidance without adding persisted queue
	state, assignments, automatic record claiming, workflow-engine behavior,
	schema changes, live browser retrieval, connector execution, or non-CCLD scope.
- Improved local/test reviewer detail feedback handoff cues so testers know which
	record-specific observations to carry into the existing manual CCLD feedback
	checklist after source traceability review, note/status confirmation, and
	return-to-queue refresh without adding persisted feedback, schema changes,
	new note/status behavior, live browser retrieval, connector execution, or
	non-CCLD scope.
- Improved local/test CCLD request no-match and local validated load guidance so
	testers can confirm facility/date criteria, understand results depend on
	currently loaded local/test data, use the existing load/refresh path when
	appropriate, and follow the outside-browser live-fetch/artifact-builder
	workflow without adding browser retrieval, connector execution, persistence,
	schema changes, or non-CCLD scope.
- Improved local/test reviewer note/status saved confirmations and queue wording
	so testers know queue progress and note/status cues are derived from
	reviewer-created state, may require resubmitting the same CCLD request context,
	and can continue to the next record without adding persistence, queue state,
	live retrieval, connector execution, schema changes, or non-CCLD scope.
- Improved the local/test reviewer detail source traceability section with clearer
	selected-record identifiers, available/missing traceability cues, local/test
	boundary language, and pre-note/status guidance without adding schema,
	persistence, live retrieval, connector execution, legal/completeness
	conclusions, or non-CCLD scope.
- Improved the local/test CCLD facility lookup and request flow with visible
	request-context confirmation showing whether the request came from lookup or
	manual entry, the facility/license number, date range, active facility
	reference source, and change-facility/date navigation without adding schema,
	persistence, live retrieval, connector execution, auth, deployment, or
	non-CCLD scope.
- Improved local/test reviewer note/status confirmations on reviewer detail so
	testers see clearer saved-state messages, validation guidance, read-after-write
	state display, and return-to-queue next steps without changing reviewer-created
	state persistence, audit behavior, source-derived records, schema, live
	retrieval, connector execution, or non-CCLD scope.
- Improved local/test CCLD first-run accessibility and visible-text guidance
	across the home page, facility lookup, request/result queue, reviewer records,
	reviewer detail, and feedback checklist surfaces with skip links, clearer
	start-here and next-step sections, more specific form/action text, and clearer
	manual feedback copy guidance without adding persistence, schema changes,
	live retrieval, connector execution, JavaScript-dependent workflow, or
	non-CCLD scope.
- Improved the local/test CCLD request/result queue and reviewer records queue
	with clearer triage summaries, status/progress counts, reviewer note/status
	cues, source-traceability availability cues, suggested next-record links,
	more specific reviewer-detail action text, CCLD workflow navigation, and
	filtered-empty guidance without adding persistence, schema changes, live
	retrieval, connector execution, new note/status behavior, or non-CCLD scope.
- Improved the local/test reviewer detail page with a plain-language record
	summary, clearer CCLD return navigation, source-traceability explanation,
	related context guidance, reviewer note/status help text, and record-specific
	feedback clues without changing source-derived reads, reviewer-created
	note/status writes, schema, persistence, live retrieval, or non-CCLD scope.
- Added a deferred-readiness/product-benefit gate to existing governance and
	roadmap docs so backend readiness, hardening, planning, and checklist work stays
	tracked but does not automatically become the next branch unless it unlocks a
	user-facing CCLD MVP capability or resolves a concrete MVP-blocking risk.
- Added safe full local/test CCLD facility reference CSV support for
	`/ccld/facilities`. The lookup now uses `CCLD_FACILITY_REFERENCE_CSV` or the
	ignored `data/raw/ccld/facility-reference.csv` convention when available, shows
	which reference source is active, falls back to the committed tiny fixture when
	the full CSV is unavailable or malformed, and keeps lookup read-only,
	CCLD-only, non-persistent, and limited to safe scalar display fields.
- Added a CCLD-only local/test facility lookup page at `/ccld/facilities` backed
	by the committed CCLD program facility reference CSV fixture. Local testers can
	search by facility/license number, facility name, city, county, ZIP code,
	facility type, or status, see a bounded safe result list, and use a selected
	facility to prefill `/ccld/records/request` while manual facility/license entry
	remains available. The lookup does not run live CCLD retrieval, execute
	connectors, persist lookup data, mutate source-derived/reviewer-created/audit
	or operational rows, add schema changes, or add non-CCLD sources.
- Added a CCLD-only local/test guided request/result queue UI: the home page now
	points first-time testers into the CCLD request flow, `/ccld/help` explains
	the workflow and key terms, `/ccld/records/request` includes contextual field
	help and feedback guidance, and matching request results render as a
	facility/date-scoped complaint review queue with source traceability,
	reviewer-state indicators, queue progress counts, status filtering, clear
	reviewer-detail actions, and a structured copyable tester feedback checklist
	derived from the current request and queue state without adding live browser
	crawling, connector execution, persisted feedback, schema changes, non-CCLD
	sources, production auth, exports, audit UI, or deployment.
- Added a CCLD-only local/test hosted artifact builder that converts validated
	CCLD SQLite pipeline output into hosted seeded-corpus JSON consumable by the
	existing `/ccld/records/request` local validated import/reload action. The
	builder accepts a SQLite path, CCLD facility/license number, optional date
	filters, and deterministic local/test metadata, preserves source URL, raw
	SHA-256, raw path, connector metadata, retrieval timestamp, stable keys,
	entity types, source traceability, and original values, validates required
	traceability before writing, rejects private or absolute raw paths, and does
	not run live crawling, execute browser-triggered connectors, add schema
	changes, add non-CCLD sources, mutate reviewer-created state, or create audit
	rows.
- Added a narrow local/test CCLD-only import/reload seam from validated hosted
	seeded-corpus JSON output into existing hosted source-derived records, plus a
	bounded `/ccld/records/request` action that lets a local tester load or refresh
	matching CCLD facility/date-scoped records without running live crawling from
	browser requests. The path preserves source URL, raw SHA-256, raw path,
	connector metadata, and idempotent source-derived keys, reports new, refreshed,
	duplicate-avoided, and deferred rows, and does not mutate reviewer-created
	state, create audit rows, add schema changes, add non-CCLD sources, add
	production auth, or execute reset/reload destructively.
- Added a browser-accessible local/test CCLD record request page at
	`/ccld/records/request` where a local tester can enter a CCLD
	facility/license number and optional date range, read matching records from
	the existing seeded source-derived corpus, and open matching rows in the
	hosted reviewer UI. The page validates CCLD-only digit input and date ranges,
	shows no-match guidance with the existing explicit CCLD live-fetch command,
	and does not mutate source-derived, reviewer-created, audit, or operational
	metadata rows; run live crawling, execute connectors, import data, add schema
	changes, add production auth, deploy, or add a frontend build pipeline.
- Added a thin browser-accessible local/test hosted reviewer UI shell at
	`/reviewer` and `/reviewer/records`, backed by the existing seeded source-
	derived read route, reviewer workflow shell, reviewer-created state route, and
	audit scaffold. A local tester can open the page, search/select a seeded
	source-derived complaint record, see list-level reviewer-created note/status
	indicators before opening detail, view safe source traceability fields and safe
	related seeded bundle context, submit a bounded reviewer note, submit a
	bounded reviewer status, and see read-after-write reviewer-created state
	with clearer no-search-results, missing-record, invalid-form, and permission-
	blocked guidance without mutating source-derived rows, exposing sensitive narrative fields, adding
	schema changes, production auth, cookies, sessions, exports, reset/reload
	execution, live crawling, connector execution, deployment, hosted URLs, or a
	frontend build pipeline.
- Added a narrow local/test audit coverage planning seam that summarizes current
	audit scaffold coverage, identifies deferred ADR-0013/ADR-0014 audit event
	categories, and returns deterministic non-persistent readiness steps with
	audit-read authorization and focused no-secret/no-mutation tests, without
	adding audit writes, audit UI, audit export, schemas, migrations, provider
	login, production auth, reset/reload execution, exports, retention automation,
	live crawling, connector execution, deployment, or hosted URLs.
- Added a narrow local/test auth provider integration planning seam for the
	ADR-0014 managed OpenID Connect/OAuth 2.0 provider class, returning bounded
	non-secret readiness and configuration-planning steps with user-role-admin
	authorization and focused no-secret/no-mutation tests, without adding real
	login, callbacks, token handling, sessions, cookies, provider registration,
	hosted URLs, user tables, role persistence, schema changes, migrations,
	external network calls, production auth, deployment, live crawling, or
	connector execution.
- Added a narrow local/test reset/reload seeded corpus execution-plan route seam
	that converts existing dry-run summaries and planning metadata context into an
	ordered bounded non-destructive action plan, with optional persistence through
	the existing operational planning metadata scaffold and focused no-mutation
	tests, without adding reset/reload execution, archive/clear/reload behavior,
	scheduler behavior, production auth, deployment, live crawling, connector
	execution, schema changes, or migrations.
- Added a narrow local/test reviewer workflow shell action for recording bounded
	reviewer status values from the selected source-derived detail context,
	delegating to the existing reviewer-created state write/audit path so source-
	record binding, auth/scope checks, audit creation, read-after-write visibility,
	and source-derived no-mutation behavior stay centralized without adding schema
	changes, status editing/deletion, queues, full workflow engine, exports,
	reset/reload execution, production auth, deployment, live crawling, or
	connector execution.
- Added a narrow local/test reviewer workflow shell action for creating reviewer
	notes from the selected source-derived detail context, delegating to the
	existing reviewer note creation route so source-record binding, auth/scope
	checks, reviewer-created state persistence, audit creation, read-after-write
	visibility, and source-derived no-mutation behavior stay on the existing
	service boundary without adding schema changes, note editing/deletion, full
	annotations, corrections, review status transitions, exports, reset/reload
	execution, production auth, deployment, live crawling, or connector execution.
- Added a narrow local/test authenticated reviewer note creation route over the
	existing reviewer-created state scaffold, storing bounded non-secret note text
	as reviewer-created scaffold payload under the existing state kind, creating
	the existing audit event on successful writes, and making notes visible through
	the existing reviewer-created state read routes and workflow shell associated
	state detail without adding schema changes, note editing/deletion, full
	annotations, corrections, review status transitions, exports, reset/reload
	execution, production auth, deployment, live crawling, or connector execution.
- Added narrow local/test filtering/search support for persisted reviewer-created
	state reads, with a bounded `q` search over existing non-secret scaffold fields
	and workflow detail pass-through for associated state filters, plus focused
	tests for search success, empty results, auth and scope rejection, and
	no-mutation behavior without adding writes, schema changes, full workflow
	execution, exports, reset/reload execution, production auth, deployment, live
	crawling, or connector execution.
- Added a narrow local/test reviewer workflow shell state summary on selected
	detail responses, derived only from the already-composed associated reviewer-
	created state read route output, with focused tests for empty state, one row,
	multiple rows, deterministic summary fields, permission separation, non-secret
	payloads, and no-mutation behavior without adding writes, schema changes, full
	workflow execution, production auth, exports, reset/reload execution,
	deployment, live crawling, or connector execution.
- Added a narrow local/test reviewer workflow shell detail integration that
	composes persisted reviewer-created state read route output for the selected
	source-derived record, with focused tests proving authenticated success, empty
	associated state, missing source records, auth rejection, source-read versus
	reviewer-state-read permission separation, non-secret payloads, and no-mutation
	behavior without adding reviewer-created state writes, full workflow execution,
	annotations UI, corrections UI, audit UI, export behavior, real login flow,
	auth middleware, deployment, live crawling, or connector execution.
- Added narrow local/test read-only reviewer-created state routes for persisted
	scaffold rows, with JSON list and fetch-by-ID handlers, schema-backed filters,
	reviewer-state read authorization, and focused tests proving empty list,
	missing-record, auth rejection, filtering, non-secret payloads, and no-mutation
	behavior without adding reviewer-created state writes, full reviewer workflows,
	annotations UI, corrections UI, audit UI, export behavior, real login flow,
	auth middleware, deployment, live crawling, or connector execution.
- Added narrow local/test read-only reset/reload planning metadata routes for
	persisted dry-run planning records, with JSON list and fetch-by-ID handlers,
	schema-backed filters, import/reload authorization, and focused tests proving
	empty history, missing-record, auth rejection, filtering, non-secret payloads,
	and no-mutation behavior without adding reset/reload execution, scheduler,
	archive/clear/reload behavior, production auth middleware, deployment, live
	crawling, or connector execution.
- Added a minimal local/test PostgreSQL/Alembic-backed reset/reload operational
	metadata scaffold, with one separate planning table, opt-in dry-run persistence,
	operator/admin-style import/reload authorization, safe readback helpers, and
	focused tests proving unauthorized actors, invalid options, secret-like context,
	and all destructive reset/reload behavior remain rejected without mutating
	source-derived, reviewer-created, or audit rows.
- Added a narrow local/test authenticated audit history read route seam for the
	first audit event scaffold, with JSON list and fetch-by-ID handlers, scoped
	filters, audit-read authorization, and focused tests proving empty history,
	missing-event, auth rejection, filtering, and no-mutation behavior without
	adding audit UI, audit export, full audit coverage, retention automation, real
	login flow, auth middleware, deployment, live crawling, or connector execution.
- Added a minimal local/test audit event persistence scaffold for successful
	reviewer-created state scaffold writes only, with a separate audit table,
	authenticated actor attribution, source-derived target context, atomic
	reviewer-state-plus-audit write behavior, reset/reload dry-run counting, and
	focused tests proving source-derived rows and reviewer-created rows are not
	modified by audit persistence, without adding full audit coverage, audit UI,
	audit export, retention automation, full reviewer workflows, annotations UI,
	corrections UI, real login flow, auth middleware, deployment, live crawling, or
	connector execution.
- Added a minimal local/test PostgreSQL/Alembic-backed reviewer-created state
	persistence scaffold, with one separate table linked to staged source-derived
	record keys, authenticated actor attribution, role/scope write guards,
	invalid-reference rejection, scoped readback, reset/reload dry-run counting,
	and focused tests proving source-derived rows are not modified, without adding
	full reviewer workflows, annotations UI, corrections UI, audit persistence,
	exports, reset/reload execution, real login flow, auth middleware, deployment,
	live crawling, or connector execution.
- Added a local/test authenticated seeded corpus reset/reload dry-run seam that
	reports existing seeded import batches, source-derived record counts by entity,
	future reviewer-created state handling modes, required permissions,
	validation requirements, audit requirements, and explicitly deferred destructive
	actions without deleting, truncating, overwriting, archiving, importing,
	reloading, persisting audit events, running live crawling, executing connectors,
	deploying, or changing schemas outside the narrow opt-in operational planning
	metadata scaffold.
- Added the first narrow local/test authenticated reviewer-facing workflow shell
	over staged seeded corpus source-derived records, with JSON queue and detail
	handlers that consume the authenticated source-derived read route seam and
	return record identity, original values, source traceability, source document
	metadata, import batch context, and explicit reviewer-created state deferral
	without adding real login flow, tokens, cookies, sessions, auth middleware,
	reviewer-created state persistence, annotations, corrections, review status,
	audit persistence, exports, reset/reload, production automation, hosted live
	crawling, connector execution, deployment, or schema changes.
- Added a narrow local/test authenticated HTTP/API route seam for staged
	source-derived reads, with JSON list, fetch-by-key, and fetch-by-stable-
	identity handlers that reuse the hosted auth boundary and database-backed read
	service while preserving import batch context, source traceability, original
	source-derived values, and the source-derived versus reviewer-created state
	boundary without adding real login flow, tokens, cookies, sessions, auth
	middleware, reviewer-created state, audit persistence, exports, reset/reload,
	production automation, hosted live crawling, connector execution, deployment,
	or schema changes.
- Added a focused hosted tester auth/authz boundary scaffold with managed
	OIDC/OAuth2 provider-class configuration validation, immutable actor, role,
	scope, target, and audit-context models, and protected source-derived read
	service guards for authenticated, disabled, role-denied, and out-of-scope
	local/test paths without adding real login flow, provider registration,
	secrets, tokens, cookies, auth middleware, user tables, reviewer-created
	state, audit persistence, API routes, deployment, live crawling, or connector
	execution.
- Added a narrow database-backed source-derived read service for staged hosted
	seeded corpus records, with list and fetch helpers that preserve import batch
	context, source traceability, original values, and the source-derived versus
	reviewer-created state boundary without adding HTTP API routes, auth
	middleware, reviewer workflows, reset/reload behavior, production import
	automation, hosted live crawling, connector execution, or deployment.
- Added a controlled hosted tester seeded corpus import path with a PostgreSQL/
	Alembic migration for import batch metadata and source-derived record staging,
	a local JSON artifact importer, a tiny validated fixture artifact, and focused
	tests that preserve source traceability, import batch identity, original
	source-derived values, and the separation from reviewer-created state without
	adding reset/reload behavior, API routes, auth middleware, reviewer workflows,
	production automation, hosted live crawling, or connector execution.
- Added minimal hosted tester PostgreSQL/Alembic project wiring, scaffold-only
	persistence/API boundary descriptors, dependency declarations, and focused
	tests for safe configuration validation and ADR-0010 data-domain separation
	without adding domain tables, migration revisions, API routes, database reads,
	imports, reset/reload commands, auth middleware, reviewer workflows, secrets,
	hosted URLs, deployment, live crawling, or connector execution.
- Added ADR-0015 choosing PostgreSQL and Alembic-managed migrations for the
	hosted tester MVP database and migration tooling direction, unblocking minimal
	hosted schema/API scaffold, seeded corpus import/reset, reviewer-created state
	persistence, audit event persistence, export packet state, tester feedback,
	reset/reload metadata, and the first authenticated tester workflow without
	adding app code, schemas, tables, migrations, API routes, import logic, reset
	commands, auth middleware, secrets, provider configuration, hosted URLs,
	deployment, live crawling, or connector execution.
- Added ADR-0014 choosing a managed standards-based OpenID Connect/OAuth 2.0
	provider class and hosted tester MVP role implementation direction, unblocking
	focused authentication, database/migration, schema/API, and first
	authenticated tester workflow branches without adding app code, auth
	middleware, API routes, schemas, tables, migrations, secrets, provider
	configuration, hosted URLs, deployment, imports, live crawling, or connector
	execution.
- Added ADR-0013 defining hosted tester MVP operational boundaries for audit
	logging, export generation, reset/reload, and tester data retention,
	unblocking the next product-moving implementation path toward provider-specific
	authentication, concrete database/migration decisions, minimal hosted
	schema/API scaffold, seeded corpus import/reset, and the first authenticated
	tester workflow without adding schemas, APIs, app code, imports, exports,
	audit tables, reset commands, retention automation, or deployment behavior.
- Added a local-only facility source coverage panel to hosted scaffold facility
	detail pages, linking committed tiny facility-master fixture rows to related
	fixture/sample source-record context where the sample mapping exists while
	keeping unmapped fixture rows clearly labeled and avoiding live source,
	database, import/sync, authentication, reviewer-created state, schema, or
	deployment behavior.
- Added a local-only hosted scaffold `/facilities` read-only sample view and
	detail pages backed by the committed tiny public-source facility fixtures,
	showing facility master fields and manifest traceability placeholders without
	adding live data loading, ignored raw CSV access, generated profiling output
	access, database access, import/sync, authentication, reviewer-created state,
	schema changes, or deployment behavior.
- Added tiny synthetic public-source facility fixtures, fixture documentation,
	and tests for future fixture-backed source/facility view planning, without
	committing raw source files, generated profiling outputs, imports, schemas,
	connectors, or hosted app behavior.
- Added local-only public-source CSV profiling tooling with synthetic fixtures,
	focused tests, ignored JSON/CSV/log outputs, and documentation of the boundary
	that raw files and generated profiles stay ignored and no imports, connectors,
	schema changes, canonical fields, or hosted app behavior are created.
- Added fixture/sample-only source traceability summary panels to the hosted
	scaffold `/source-records` list and detail shell, showing visible sample
	source URL, raw SHA-256, connector, retrieval timestamp, report index,
	extraction warning, jurisdiction, and source-family indicators without adding
	live source loading, database access, import/sync, authentication,
	reviewer-created state, schema changes, or deployment behavior.
- Added local-only sample filtering/search to the hosted scaffold
	`/source-records` shell using query, jurisdiction, and source-family controls
	over fixture/sample records only, without adding live source loading,
	database access, import/sync, authentication, reviewer-created state,
	schema changes, or deployment behavior.
- Added a public-source data inventory for CCLD report pages, CCLD public CSV
	download planning, CalHHS/CHHS facilities data planning, uploaded CSV example
	usage, conceptual multi-source adapter metadata, attorney focus-area planning,
	and gated feedback or GitHub intake planning without implementing source
	behavior.
- Added a governance inventory and gap analysis for the current
	production-discovery phase, local hosted scaffold state, completed ADRs,
	deferred decisions, stale-guidance assessment, and next hosted implementation
	gaps without changing product behavior.
- Added local-only semantic/accessibility validation coverage for the hosted
	scaffold source-record list and detail shell using Python standard-library
	HTML parsing, without browser automation or frontend test dependencies.
- Added the first local-only read-only source-derived hosted view shell with
	fixture/sample records, sample source-traceability-style fields, and explicit
	labels that no live data, database, import/sync, authentication, or
	reviewer-created state persistence is active.
- Added local hosted scaffold setup-check tooling for verifying Python and
	development-tool prerequisites on Windows without installing software,
	requiring admin rights, or requiring Node, Docker, QNAP, cloud resources, or a
	public URL.
- Updated the local secret-check script to ignore conventional `.venv*` local
	virtual environment directories so developer validation does not scan installed
	third-party packages.
- Added the first local hosted tester MVP scaffold with a Python
	standard-library app shell, health route, smoke check, focused tests, and
	Windows PowerShell run documentation while intentionally deferring cloud,
	QNAP, Docker, schema, authentication, authorization, import/sync, queues,
	annotations, corrections, exports, reset/reload, hosted deployment,
	reviewer-created state persistence, and extraction behavior.
- Added ADR-0012 defining the hosted tester MVP scope and scaffold sequencing
	boundary, allowing hosted implementation to begin through a scaffold-first
	sequence while keeping schemas, authentication, authorization, import/sync,
	queues, annotations, corrections, exports, reset/reload, hosted deployment,
	and extraction behavior out of the first scaffold branch.
- Added ADR-0011 defining the hosted tester MVP authentication and access
	boundary, requiring authenticated invited or provisioned tester access,
	simple role-based access, revocable tester accounts, permissioned
	import/reload/reset and export actions, and auditable reviewer-created actions
	where feasible while deferring provider, identity storage, session,
	authorization middleware, role schema, user table, invitation, audit schema,
	and deprovisioning implementation decisions.
- Added ADR-0010 defining the hosted tester MVP schema and migration strategy
	boundary, requiring future hosted schema work to separate import metadata,
	source-derived imported records, reviewer-created state, audit events, export
	packet state, tester feedback, and operational/reset metadata while deferring
	actual schema files, migrations, database product, migration tooling, import
	implementation, reset/reload implementation, retention, backup, and app
	scaffold decisions.
- Added ADR-0009 defining the hosted tester MVP import/sync strategy, keeping
	the Python pipeline as the source-derived data producer, starting with
	controlled snapshot imports from validated pipeline output, and deferring
	schema, migration, import implementation, reset/reload implementation,
	retention, backup, authentication, hosting, and app scaffold decisions.
- Added ADR-0008 defining the hosted tester MVP data and review-state model
	boundary, separating source-derived imported records from reviewer-created
	review state while deferring schema, migration, import/sync, authentication,
	export, audit, retention, and scaffold decisions.
- Added Copilot next-prompt quality governance, including prompt-mode guidance,
	project-aware synthesis requirements, validation expectations, PR body
	requirements, final handoff requirements, and a rule against including a next
	branch command unless the user asks for one.
- Added ADR-0007 evaluating hosted tester MVP production stack options and
	recommending a hybrid transition direction that preserves the Python
	ingestion/extraction pipeline and retained SQLite/Datasette validation layer
	while planning a hosted relational reviewer-state store and hosted reviewer
	app/API boundary.
- Added ADR-0006 for hosted tester MVP architecture boundaries, preserving
	source-derived data separately from reviewer-created state, retaining Datasette
	for validation and transition comparison, and deferring production stack
	decisions to future ADRs.
- Added minimum production-discovery requirements for the future hosted primary
	reviewer application, including hosted reviewer workflows, review-state
	boundaries, annotation and correction constraints, tester readiness, and
	source-traceable export packet expectations.
- Added Datasette exit governance for the production-discovery phase: Datasette
	is retained for validation, inspection, debugging, local exploration, and
	export support, while future primary reviewer UX work moves to requirements
	and architecture decisions.
- Added a small fixture-backed multi-facility sample corpus that exercises
	facility identifier intake diagnostics, controlled fetch summaries,
	multi-facility source traceability, facility comparison, and review-bundle
	export paths without live public requests.
- Expanded the local review bundle with multi-facility source traceability and
	facility comparison CSV files plus cautious README notes for attorney-review
	handoff packets.
- Added a facility comparison review view and repeated category/finding saved
	query for cautious cross-facility source-review queues over the local derived
	dataset.
- Added a multi-facility source traceability review view and facility-filtered
	saved query for checking source traceability status and linked derived-record
	counts by source document across facilities.
- Added clearer controlled multi-facility live fetch outcome summaries for
	records discovered, no records discovered, discovery failures,
	skipped-by-limit reports, partial report failures, and written records.
- Added facility identifier intake diagnostics to controlled live fetch runs so
  reviewers can see accepted identifiers, duplicates ignored, ignored file
  values, and invalid-format rejection before public requests begin.
- Expanded the local review bundle into a source-traceable public-record review
	packet with complaint timeline, field source traceability, and facility
	pattern CSV exports plus cautious README notes.
- Added a `facility_pattern_review` Datasette view and
	`facility_patterns_with_review_flags` saved query for comparing finding mix,
	allegation categories, missingness, report-date proxy usage, review flags, and
	source document counts across facilities without treating counts as findings.
- Added a field-level `field_source_traceability_review` Datasette view and
	`field_traceability_by_facility` saved query for reviewing extracted values,
	source text, warnings, confidence, extraction method, and source document
	traceability together.
- Added a source-traceable `complaint_timeline_review` Datasette view and
	`complaint_timeline_by_facility` saved query for reviewing complaint milestone
	dates and extracted event dates without treating missing dates as proof that
	an event did not occur.
- Added a source-traceable `public_record_allegation_search` Datasette saved
	query for cautious keyword discovery over source-derived allegation text,
	categories, and findings, with local review documentation and metadata
	coverage.
- Hardened CCLD facility name extraction for source layouts that use a
  `FACILITY NAME;` semicolon label variant, with fixture-backed regression
  coverage.
- Added data quality coverage that verifies source document hashes match the
  preserved raw files referenced by `raw_path`.
- Added data quality coverage that verifies source document hashes are present
  as lowercase SHA-256 hex values.
- Added data quality coverage that verifies complaint date ordering and stored
  delay calculation fields against deterministic date math.
- Added data quality coverage that checks sample-derived canonical tables for
  duplicate record identifiers and duplicate source URLs.
- Updated the roadmap to remove a completed local review workflow grouping item
  from current priorities and hardened documentation validation against stale
  completed roadmap priorities.
- Added a data quality test that verifies derived complaint, allegation, event,
  and extraction audit records trace back to source documents with required
  source URL, raw hash, connector metadata, and retrieval timestamp.
- Improved the `review_home` Datasette saved query with a `workflow_group`
  column so reviewers can scan local review paths by user task before opening
  implementation tables or detailed views.
- Hardened CCLD finding extraction for source layouts that split a
	`Finding :` spaced-colon label from its value, with fixture-backed regression
	coverage.
- Hardened CCLD facility number extraction for source layouts that use a
	`FACILITY NUMBER :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD facility name extraction for source layouts that use a
	`FACILITY NAME :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD complaint control number extraction for source layouts that use
	a `COMPLAINT CONTROL NUMBER :` spaced-colon label variant, with
	fixture-backed regression coverage.
- Hardened CCLD visit date extraction for source layouts that use a
	`VISIT DATE :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD date signed extraction for source layouts that use a
	`Date Signed :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD report date extraction for source layouts that use a
	`Report Date :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`ALLEGATION(S) -` section heading variant, with fixture-backed regression
	coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`INVESTIGATION FINDINGS -` section heading variant, with fixture-backed
	regression coverage.
- Hardened CCLD report type extraction for source layouts where the complaint
	investigation report heading includes trailing punctuation, with
	fixture-backed regression coverage.
- Hardened CCLD complaint received date extraction for source layouts where
	punctuation separates the narrative received-date phrase from the date value,
	with fixture-backed regression coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`INVESTIGATION FINDINGS` section heading without a trailing colon, with
	fixture-backed regression coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`ALLEGATION (S):` section heading variant, with fixture-backed regression
	coverage.
- Hardened CCLD report type extraction for source layouts where the complaint
	investigation report heading uses different casing, with fixture-backed
	regression coverage.
- Hardened CCLD facility number extraction for source layouts where a standalone
	`FACILITY NUMBER` label is followed by the facility number value, with
	fixture-backed regression coverage.
- Hardened CCLD facility name extraction for source layouts where a standalone
	`FACILITY NAME` label is followed by the facility name value, with
	fixture-backed regression coverage.
- Hardened CCLD complaint control number extraction for source layouts where a
	standalone `COMPLAINT CONTROL NUMBER` label is followed by the complaint
	control number value, with fixture-backed regression coverage.
- Hardened CCLD visit date extraction for source layouts where a standalone
	`VISIT DATE` label is followed by the visit date value, with fixture-backed
	regression coverage.
- Hardened CCLD date signed extraction for source layouts where a standalone
	`Date Signed` label is followed by the signed date value, with fixture-backed
	regression coverage.
- Hardened CCLD report date extraction for source layouts where a standalone
	`Report Date` label is followed by the date value, with fixture-backed
	regression coverage.
- Hardened CCLD complaint received date extraction for source layouts that use a
	`complaint was received in our office on` narrative phrase, with
	fixture-backed regression coverage.
- Hardened CCLD finding extraction for source layouts where an inline `Finding -`
	label precedes the normalized finding value, with fixture-backed regression
	coverage.
- Hardened CCLD finding extraction for source layouts where normalized finding
	values include trailing punctuation, with fixture-backed regression coverage.
- Hardened CCLD allegation extraction for source layouts that use allegation
	section headings without a trailing colon, with fixture-backed regression
	coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`INVESTIGATION FINDING:` section heading variant, with fixture-backed
	regression coverage.
- Hardened CCLD allegation extraction for source layouts that use an
  `ALLEGATIONS:` section heading variant, with fixture-backed regression
  coverage.
- Hardened CCLD finding extraction for source layouts where a standalone
	`Finding` label is followed by the normalized finding value on the next line,
	with fixture-backed regression coverage.
- Hardened CCLD allegation extraction for source layouts where one allegation
	wraps across adjacent lines, with fixture-backed regression coverage.
- Hardened CCLD finding extraction for source layouts where the normalized
  finding appears after an explicit `Finding:` label, with fixture-backed
  regression coverage.
- Improved sample and live fetch script output by grouping next review steps by
	task: what to open first, delay triage, source verification, CSV export, and
	other useful review paths.
- Hardened CCLD complaint received date extraction for source layouts where the
	received date appears inline in the narrative sentence, with fixture-backed
	regression coverage.
- Added fixture-backed CCLD missing visit date coverage to preserve report-date
	proxy delay review behavior and source traceability.
- Established the governed CCLD complaints proof-of-concept structure, including
	project charter, data contract, source connector contract, testing strategy,
	documentation strategy, accessibility requirements, security rules, decision
	log, and Copilot instructions.
- Adopted Python, SQLite, and Datasette for local ingestion, storage, and review
	without a custom frontend during the proof of concept.
- Added the CCLD connector workflow for discovering explicitly provided facility
	report records, preserving raw source files, computing raw SHA-256 hashes, and
	normalizing extracted records.
- Added fixture-backed sample ingestion and regression coverage for known CCLD
	reports.
- Added controlled live fetch scripts for explicitly provided facility numbers,
	including multi-facility input and request-limit controls.
- Added SQLite persistence for facility, source document, complaint, allegation,
	event, and extraction audit records.
- Added Datasette review views, metadata labels, column descriptions, and saved
	query examples for complaint review, facility summaries, delay review flags,
	source traceability, and CSV export workflows.
- Added design and usability governance for local review workflows, including
	plain-language delay flag guidance and accessible export expectations.
- Added documentation validation for required governance, user, developer,
	roadmap, changelog, setup, runbook, and Copilot workflow guidance.
- Expanded documentation validation to cover all required developer docs and
	the required user searching and filtering guide.
- Added release checklist guidance for validation, accessibility review, PR
	checks, merge cleanup, and next-task handoff.
- Added next-task selection guidance so Copilot handoffs prefer active roadmap
	product and technical milestones over repeated documentation-only work.
- Added copy/paste-safe handoff formatting rules for PowerShell commands, PR
	title/body separation, post-merge cleanup, and next-branch creation.
- Improved Datasette review usability with additional source-traceable saved
	queries and clearer script launch guidance for common review workflows.
- Added a local review bundle export script that writes complaint review, delay
	triage, and source traceability CSV files with source URL, raw hash, connector
	metadata, retrieval time, report index, and delay-flag caution notes.
- Hardened CCLD allegation extraction for report layouts where numeric allegation
	markers and allegation text appear on the same line, with fixture-backed
	regression coverage.
- Added governance rules requiring bug and CI-failure fixes to include root-cause
	governance review, and requiring raw fixture hashes to be verified against
	Git-normalized fixture bytes governed by `.gitattributes`.
- Added GitHub CLI governance for repeatable PR status checks, check watching,
	squash merge automation, and authentication-secret hygiene.
- Added live fetch summary output so reviewers can see discovered, selected,
	skipped, fetched, written, and failed report counts before opening logs.
- Tightened GitHub CLI completion governance so automated PR workflows still
	include the next branch and exact next Copilot prompt, and so roadmap work
	continues through explicit user checkpoints rather than unattended loops.
- Added governance requiring GitHub branch protection or repository rulesets for
	`main`, with required `validate`, `docs-check`, `fixtures`, and `security`
	status checks before squash merge, plus `gh` availability verification before
	PR automation.
- Added a local output accessibility checklist covering Datasette views,
	generated metadata, saved queries, CSV exports, review bundles, and script
	output.
- Added a `complaint_review_start_here` Datasette saved query with source URL,
	raw hash, connector metadata, retrieval time, and report index for guided
	review and export-safe triage.
- Added a `review_home` Datasette saved query that gives reviewers one
	task-based start-here surface for complaint review, delay triage, facility
	comparison, source verification, and CSV export paths before any dashboard or
	custom web interface decision.
- Added contextual help to primary Datasette review views and saved queries so
	reviewers can see when to use each item, what not to conclude, and what source
	traceability to preserve when exporting.
- Added a low-noise `complaint_first_pass_review` Datasette view and guided
	query path that hide implementation-heavy fields during first-pass review
	while preserving source URL, raw hash, raw path, connector metadata,
	retrieval time, report index, and lower-level IDs for follow-up.
- Updated the roadmap to prioritize incremental local review usability work,
	including a review home, task-based workflow grouping, contextual help,
	low-noise review views, script-output navigation, and a web app transition
	path that later informed the Datasette primary review UX exit decision.
