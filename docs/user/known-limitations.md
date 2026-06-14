# Known Limitations

- The public portal remains the source of record.
- Extracted data may contain errors.
- Some reports may have missing or inconsistent fields.
- Report date may not be the same as first investigation activity date.
- Delay review flags are screening aids and do not prove that an investigation was delayed.
- When `first_investigation_activity_date` is missing, delay review may rely on visit date or report date as a proxy basis. Report date alone does not establish when investigation activity began.
- Narrative extraction may require manual review.
- The first CCLD extraction fixture covers one public facility report for facility number `157806098`; additional report layouts need their own fixtures before broader use.
- The local sample database is populated only from bundled fixtures. It does not make live web requests and currently writes the single report fixture that has bundled raw content.
- Live CCLD fetch mode is explicitly user-invoked, accepts only provided facility numbers, and depends on the public site being available when the command runs. It does not perform statewide crawling or automatic search expansion.
- Facility identifier intake accepts digit-only public facility numbers, ignores
  duplicate, blank, comment, and header values, and rejects invalid values before
  public report discovery begins.
- Live fetch summaries distinguish no-record, skipped-by-limit, discovery
  failure, report failure, and written-record run states. These are workflow
  states in the derived dataset, not conclusions about the public source.
- Live fetched raw report files are saved under the local ignored `data/raw/ccld` path by default. Treat public narrative content carefully when sharing exports or raw files.
- Live fetched records reflect the public response at retrieval time. Public reports may later change, be corrected, become unavailable, or use layouts the current extractor does not fully understand.
- The local hosted scaffold `/facilities` pages are read-only fixture/sample
  pages backed only by committed tiny public-source facility fixtures and
  manifest placeholder metadata. Source coverage panels and related
  source-record links on those pages are fixture/sample display patterns only.
  They do not load live public-source data, read ignored raw CSVs or generated
  profiling outputs, use SQLite or a hosted database through API routes,
  perform real provider login, persist reviewer-created state, or prove statewide
  coverage, source completeness, official facility status, or legal or
  facility-wide conclusions.
- The hosted seeded corpus import path is controlled and local/test-oriented.
  It stages source-derived records from a validated JSON artifact into the
  PostgreSQL/Alembic import batch and source-derived table group only. A narrow
  local/test read service can list and fetch those staged records with import
  batch context and source traceability, and local/test auth guards can protect
  those service reads by actor role, account status, and scope. A narrow
  local/test HTTP/API route seam can serialize those authenticated
  source-derived reads when tests provide an explicit route context, and a
  narrow local/test reviewer workflow shell can return read-only queue/detail
  payloads over that route seam, compose associated reviewer-created state read
  route output plus a compact summary derived from that output on selected
  detail responses, and expose narrow note/status actions when tests provide an
  explicit workflow context.
  A narrow local/test auth provider integration planning seam can validate the
  accepted managed OpenID Connect/OAuth 2.0 provider class and return
  deterministic non-secret readiness steps when tests or local callers provide
  explicit actor and scope context. It does not persist provider configuration,
  register a provider, create hosted URLs, handle callbacks, exchange or
  validate tokens, create sessions or cookies, or implement production auth.
  A narrow local/test audit coverage planning seam can summarize current
  scaffold audit coverage and deferred hosted tester audit categories when
  tests or local callers provide explicit database, actor, and scope context
  with audit-read permission. It does not create audit rows, persist planning
  records, add schemas or migrations, provide audit UI/export, or implement full
  audit coverage.
  A narrow local/test reviewer-created state
  persistence scaffold can
  store attributed placeholder rows separately from source-derived records only
  when tests or local callers provide an explicit database, authenticated actor,
  and corpus scope context. A local/test reset/reload dry-run seam can report
  seeded import batch metadata, source-derived record counts, scoped reviewer-
  created scaffold row counts, future reviewer-created state handling modes,
  permissions, validation requirements, audit requirements, and deferred
  destructive actions when tests provide an explicit dry-run context. A narrow
  local/test reset/reload execution-plan seam can turn those summaries into
  ordered bounded non-destructive action steps when tests or local callers
  provide explicit database, actor, and scope context. It can persist a separate
  operational planning metadata record only when local/test code explicitly
  requests it; that record is planning metadata only and is stored separately
  from source-derived, reviewer-created, and audit rows. The execution-plan seam
  can also persist an execution-plan artifact through that same planning
  metadata table only when explicitly requested. A narrow local/test read-only
  route can list or fetch those planning records
  when tests or local callers provide explicit database, actor, and scope
  context with import/reload permission. A narrow local/test read-only reviewer-
  created state route can list or fetch persisted scaffold rows with schema-
  backed filters and bounded search when tests or local callers provide explicit
  database, actor, and scope context with reviewer-state read permission.
  Source-derived read permission alone does not
  grant this reviewer-created state read access, including when the workflow
  shell composes associated state context and its derived summary for a selected
  source record. Reviewer note and status creation through the workflow shell
  separately require reviewer-state write permission and force source-record
  binding from the selected detail context. A narrow local/test reviewer note creation route can write
  bounded non-secret note text through the existing reviewer-created state
  scaffold and audit path when explicit local/test code supplies reviewer-state
  write context; it does not add a new schema kind, note editing/deletion, full
  annotations, corrections, exports, or production auth behavior. A narrow
  local/test reviewer status creation route can write bounded status values
  through the same scaffold and audit path; it does not add a new schema kind,
  status editing/deletion, queue assignment, full workflow engine behavior,
  exports, or production auth behavior. A browser-accessible local/test reviewer
  UI shell at `/reviewer` and `/reviewer/records` now wraps those existing seams
  for the tiny seeded fixture corpus only: a local tester can list/search a
  seeded source-derived complaint record, see list-level reviewer-created
  note/status indicators, open detail, view safe source traceability fields plus
  safe related seeded bundle context, submit a bounded reviewer note, submit a
  bounded reviewer status, and see read-after-write reviewer-created state.
  No-search-results, missing-record, invalid-form, and permission-blocked states
  provide local/test next-step links but do not diagnose production access or
  data availability.
  Narrative source fields are hidden in the browser
  shell. The UI uses process-local seeded test state and a fixture actor context; it is not production
  authentication, durable hosted deployment, full reviewer workflow behavior, or
  complete public-source coverage. The path does not run live crawling,
  execute connectors, automate production imports,
  execute reset/reload, delete or overwrite source-derived records, archive or
  clear reviewer-created state, execute persisted planning or execution-plan metadata, mutate
  planning metadata or reviewer-created state through reads, persist
  audit events beyond successful reviewer-created state scaffold writes,
  authenticate browser users, validate
  real provider tokens, implement full reviewer workflows,
  expose production reviewer views or production API framework
  behavior, or prove source completeness. The audit event scaffold is local/test
  only, stored separately, and records only successful reviewer-created state
  scaffold writes with actor, permission, scope, action, target, and source-
  derived context. A narrow local/test audit history read route can list or
  fetch those scaffold audit rows when tests or local callers provide explicit
  database, actor, and scope context with audit-read permission. It does not
  provide full audit coverage, audit UI, audit export, retention automation, or
  audit coverage for reset/reload, exports, feedback, annotations, corrections,
  provider login, role changes, or operational actions.
- The local hosted scaffold `/ccld/records/request` page accepts a CCLD
  facility/license number and optional date range, reads only existing seeded
  source-derived rows, can load or refresh matching rows from local validated
  hosted seeded-corpus output, and links matching rows into the reviewer UI. It
  does not run live retrieval, execute connectors, mutate reviewer-created
  state, create audit rows, persist operational metadata, prove public-source
  completeness, or support non-CCLD sources. When records are missing from the
  local validated output or outside the requested date range, it only explains
  the explicit live-fetch command and the remaining future need for a controlled
  artifact builder that converts validated CCLD SQLite pipeline output into
  hosted seeded-corpus JSON outside browser requests.
- Datasette accessibility depends partly on the installed Datasette version, browser, and assistive technology. Validate keyboard navigation, table headers, focus visibility, and exported table usability before treating a release as stable.
