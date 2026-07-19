# Known Limitations

- The authenticated operator source-coverage dashboard consumes validated
  Issue #453 v1 packages and exposes only GET summary, facility, job, aggregate
  CSV, and grouped Facility ID reads. It does not discover live packages or
  execute retry, apply, cancel, resume, backfill, retrieval, import, job or
  checkpoint mutation, persistence, scheduling, database writes, or retention
  cleanup. Retention remains `pending_policy`. Automated local fixture evidence
  does not prove current runtime, statewide completeness, freshness,
  deployment, or QNAP behavior.
- Reviewer aggregates report their loaded-record universe, denominator,
  selected date dimension/range, source coverage, and explicit zero,
  unavailable, partial, or truncated cause. These counts describe authorized
  loaded records only; they do not prove statewide or public-source completeness.
- `/ccld/facilities/intelligence` covers only authorized loaded complaint
  records. Its available, partial, and unavailable states describe original
  public-report links on those contributing records, not statewide or portal
  completeness. Monthly anomaly cues are limited to the existing governed
  24-period comparison window, and records missing the selected date dimension
  remain explicit but cannot match an active date range.
- Source-derived list reads and complaint exports have no implicit 100-row cap.
  A caller-requested limit reports eligible count, returned count, and
  truncation status. Ordinary reviewer pagination remains presentation paging,
  not an aggregate completeness claim.
- The presentation-value contract can distinguish explicit source literals,
  present blank fields, absent keys, typed invalid values, and preserved raw
  facility-reference values. When an older stored row contains only SQL null
  and no field-level/raw provenance, the original cause of that null cannot be
  reconstructed; the reviewer label remains `Not provided` rather than
  inventing unavailable or not-applicable semantics.
- Reviewer detail can identify a stored-duration mismatch only when both
  associated milestone dates and the duration are valid. If either date is
  absent, blank, unavailable, undated, or malformed, the stored duration and
  governed date-state labels remain visible without an inferred comparison.
- Complaint received date and first investigation activity date are distinct
  range dimensions. Existing PostgreSQL rows still require governed artifact
  regeneration and reimport to receive newly populated issue #447 values. No
  complete safe production refresh command exists.

- The public portal remains the public source of record.
- Extracted data is a derived dataset and may contain extraction errors.
- Public source reports may be incomplete, corrected later, or removed.
- Report date may not equal first investigation activity date.
- Delay review flags are screening aids and do not prove that an investigation was delayed.
- Report date may be used as a review proxy only when no first investigation activity date or visit date is available; report date alone does not establish when investigation activity began.
- Narrative activity dates are extracted only for governed
  investigation-findings wording with deterministic activity cues and parseable
  numeric dates. Unsupported or malformed wording remains null with explicit
  extraction audit status.
- Complaint-report facility address and city elements can be present but blank;
  the extractor preserves that distinction in audit evidence, but canonical
  storage allocation remains deferred.
- Existing hosted PostgreSQL source-derived rows do not change when extractor
  or allocation code changes. Regeneration and reimport are required. The
  controlled importer is idempotent and preserves source traceability and
  reviewer-created state, but no complete safe refresh command currently adds
  schema-version gating, aggregate dry-run changed/unchanged/skipped/failed
  planning, governed artifact regeneration, and a production recovery contract.
- Existing facility-reference rows require an Alembic upgrade and a deliberate
  preload rerun before the issue #447 visit-date arrays or `CLIENT_SERVED`
  projection are populated. Those reference-only fields are not canonical
  complaint events or facility attributes, and no cross-source canonical bridge
  is implemented. The existing preload supports explicit dry-run/apply and
  counted idempotent updates, but it is not the missing complete canonical-plus-
  reference refresh workflow.
- Local store-parity evidence executes SQLite and the hosted SQLAlchemy mapping
  path on a temporary SQLite adapter and separately compiles PostgreSQL-dialect
  SQL. It does not claim a disposable PostgreSQL service or production runtime
  inspection; runtime mode makes that distinction explicit.
- Default and PostgreSQL hosted modes do not fall back to committed tiny fixture
  records. Fixture/sample routes and the committed seeded artifact require an
  explicit local `fixture-demo` or fixture-import opt-in.
- Some older reports may have different layouts or missing fields.
- Live CCLD ingestion can persist normalized records to SQLite for one or more explicitly provided facility numbers when configured with a database path; it does not perform statewide crawling or automatic search expansion.
- Live facility identifier intake accepts digit-only public facility numbers,
  ignores duplicate, blank, comment, and header values, and rejects invalid
  values before public report discovery begins.
- Live fetch summaries distinguish no-record, skipped-by-limit, discovery
    failure, report failure, and written-record run states. These are workflow
    states in the derived dataset, not conclusions about the public source.
- Fixture-backed ingestion only extracts discovered reports when matching raw report content is supplied by the test loader.
- Live CCLD fetching is explicitly user-invoked through the local script and depends on the public site being available when the command runs.
- Live fetched raw report files are saved under the local ignored `data/raw/ccld` path by default and should be treated carefully because public narrative content may be sensitive.
- The explicit local `fixture-demo` hosted scaffold `/source-records` list uses
    fixture/sample records and local sample filtering/search plus fixture/sample-only source
    traceability summary panels only. It does not load live public-source data,
    read from SQLite or a hosted database through API routes, authenticate
    users, persist reviewer-created state, deploy publicly, or prove source
    completeness.
- The hosted seeded corpus import path is controlled and local/test-oriented.
    It stages source-derived records from a validated JSON artifact into the
    PostgreSQL/Alembic import batch and source-derived table group only. A
    narrow local/test read service can list and fetch those staged records with
    import batch context and source traceability, and local/test auth guards can
    protect those service reads by actor role, account status, and scope. A
    narrow local/test HTTP/API route seam can serialize those authenticated
    source-derived reads when tests provide an explicit route context, and a
    narrow local/test reviewer workflow shell can return read-only queue/detail
    payloads over that route seam, compose associated reviewer-created state read
    route output plus a compact summary derived from that output on selected
    detail responses, and expose narrow note/status actions when tests provide
    an explicit workflow context.
    A narrow local/test auth provider integration planning seam can validate the
    accepted managed OpenID Connect/OAuth 2.0 provider class and return
    deterministic non-secret readiness steps when tests or local callers provide
    explicit actor and scope context. It does not persist provider
    configuration, register a provider, create hosted URLs, handle callbacks,
    exchange or validate tokens, create sessions or cookies, or implement
    production auth.
    A narrow local/test audit coverage planning seam can summarize current
    scaffold audit coverage and deferred hosted tester audit categories when
    tests or local callers provide explicit database, actor, and scope context
    with audit-read permission. It does not create audit rows, persist planning
    records, add schemas or migrations, provide audit UI/export, or implement
    full audit coverage.
    A narrow local/test reviewer-created state
    persistence scaffold can
    store attributed placeholder rows separately from source-derived records
    only when tests or local callers provide an explicit database, authenticated
    actor, and corpus scope context. A local/test reset/reload dry-run seam can
    report seeded import batch metadata, source-derived record counts, scoped
    reviewer-created scaffold row counts, future reviewer-created state handling
    modes, permissions, validation requirements, audit requirements, and
    deferred destructive actions when tests provide an explicit dry-run context.
    A narrow local/test reset/reload execution-plan seam can turn those summaries
    into ordered bounded non-destructive action steps when tests or local callers
    provide explicit database, actor, and scope context. It can persist a
    separate operational planning metadata record only when local/test code
    explicitly requests it; that record is planning metadata only and is stored
    separately from source-derived, reviewer-created, and audit rows. The
    execution-plan seam can also persist an execution-plan artifact through that
    same planning metadata table only when explicitly requested. A narrow
    local/test read-only route can list or fetch those
    planning records when tests or local callers provide explicit database,
    actor, and scope context with import/reload permission. A narrow local/test
    read-only reviewer-created state route can list or fetch persisted scaffold
    rows with schema-backed filters and bounded search when tests or local
    callers provide explicit database, actor, and scope context with
    reviewer-state read permission. Source-derived read permission
    alone does not grant this reviewer-created state read access, including
    when the workflow shell composes associated state context and its derived
    summary for a selected source record. Reviewer note and status creation
    through the workflow shell separately require reviewer-state write
    permission and force source-record binding from the selected detail context.
    A narrow local/test reviewer note creation route can write bounded non-
    secret note text through the existing reviewer-created state scaffold and
    audit path when explicit local/test code supplies reviewer-state write
    context; it does not add a new schema kind, note editing/deletion, full
    annotations, corrections, exports, or production auth behavior. A narrow
    local/test reviewer status creation route can write bounded status values
    through the same scaffold and audit path; it does not add a new schema kind,
    status editing/deletion, queue assignment, full workflow engine behavior,
    exports, or production auth behavior.
    A browser-accessible local/test reviewer UI shell at `/reviewer` and
    `/reviewer/records` now wraps those existing seams for the tiny seeded
    fixture corpus only: a local tester can list/search a seeded source-derived
        complaint record, see list-level reviewer-created note/status indicators,
        open detail, view safe source traceability fields plus clearer missing-value
        guidance, view presentation-only source-confidence cues for present,
        missing, and proxy-flagged local/test complaint fields, view field-note
        guidance for cautious reviewer-created observations, view feedback
        checklist bridge cues that point to the existing manual checklist, and safe
        related seeded bundle context, see record-summary and record-specific
        feedback handoff guidance, submit a bounded
        reviewer note, submit a bounded reviewer status, see saved-state
        confirmations with same-request return-to-queue progress and next-record
        navigation guidance, and see read-after-write
        reviewer-created state.
    No-search-results, missing-record, invalid-form, and permission-blocked
    states provide local/test next-step links but do not diagnose production
    access or data availability.
    A concise source narrative excerpt can appear on reviewer detail, with longer
    loaded narrative behind disclosure. The UI uses
    process-local seeded test state and a fixture actor context; it is not production authentication,
    durable hosted deployment, full reviewer workflow behavior, or complete
    public-source coverage.
    The path does not run live crawling, execute connectors, automate production
    imports, execute reset/reload, delete or overwrite source-derived records,
    archive or clear reviewer-created state, execute persisted planning or execution-plan
    metadata, mutate planning metadata or reviewer-created state through reads,
    add source-confidence scoring, generate reviewer notes, store note templates,
    add note fields, create duplicate checklists, persist feedback, export feedback,
    automate source verification, assert source completeness,
    change parser/extraction behavior, or add schema/persistence,
    persist audit events beyond
    successful reviewer-created state scaffold writes, authenticate browser
    users, validate real provider tokens, implement full reviewer
    workflows, expose production reviewer views or production API
    framework behavior, or prove source completeness. The audit event scaffold
    is local/test only, stored separately, and records only successful reviewer-
    created state scaffold writes with actor, permission, scope, action, target,
    and source-derived context. A narrow local/test audit history read route can
    list or fetch those scaffold audit rows when tests or local callers provide
    explicit database, actor, and scope context with audit-read permission. It
    does not provide full audit coverage, audit UI, audit export, retention
    automation, or audit coverage for reset/reload, exports, feedback,
    annotations, corrections, provider login, role changes, or operational
    actions.
- The read-only `/reviewer/facilities/trends` page compares only authorized
    loaded complaint records. Period availability is bounded by the first and
    last loaded complaint-received-date period for the selected facility group;
    `Coverage unavailable` does not mean no public records exist. Complaint rows
    without a complaint received date remain in the separate `Date unavailable`
    count and are never used for anomaly comparisons. The page does not persist
    scores, predict future activity, mutate reviewer state, or make legal,
    facility-wide, or source-completeness conclusions.
- The local hosted scaffold `/ccld/records/request` page accepts a CCLD
    facility/license number and optional date range, reads only existing seeded
    source-derived rows, can load or refresh matching rows from local validated
    hosted seeded-corpus output, renders a guided facility/date-scoped complaint
    review queue with visible lookup/manual-entry request-context confirmation,
    progress counts, reviewer note/status cues, source-
    traceability availability cues, suggested next-record links, clearer no-match
    and local validated load guidance, filtered-empty recovery, consistent terminology
    guidance, and reviewer-status filters derived from existing reviewer-created
    state, includes a structured copyable feedback checklist for manual external
    sharing, provides queue-to-detail continuity cues for using that same
    checklist, and links matching rows into the reviewer
    UI. The local/test pages include skip-to-main links, visible first-run next
    steps, review session orientation, clearer form/action text, and manual
    checklist copy guidance, but these are presentation aids only and do not
    create saved review sessions, persisted queue state, persisted workflow state,
    duplicate checklists, or feedback persistence.
    It can trigger controlled server-side CCLD complaint retrieval only when the
    runtime is explicitly configured for retrieval and server-side raw storage.
    The browser still does not scrape CCLD, receive connector credentials, or
    receive raw artifact paths. The request page does not mutate reviewer-created
    state, create audit rows from the request page, persist feedback, create
    duplicate checklists, prove public-source completeness, or support non-CCLD
    sources. When records are missing from the local validated output or outside
    the requested date range, it explains the configured retrieval action or the
    explicit outside-browser CCLD live-fetch and local/test artifact-builder
    handoff. The artifact builder converts validated CCLD
    SQLite pipeline output into hosted seeded-corpus JSON outside browser
    requests, but it is still a local/test step and does not prove public-source
    completeness or automate production imports.
- The local hosted scaffold `/ccld/facilities` lookup page can read a full
    local/test CCLD facility reference CSV from `CCLD_FACILITY_REFERENCE_CSV` or
    ignored local path `data/raw/ccld/facility-reference.csv`; otherwise it falls
    back to the committed tiny CCLD program facility reference CSV fixture. It
    displays a bounded safe subset of fields for lookup assistance. It does not
    read generated profiling outputs, SQLite, a hosted database, live public-
    source data, import output, authentication state, or reviewer-created state,
    and it does not prove source completeness, statewide coverage, official
    facility status, complaint availability, or legal or facility-wide
    conclusions. Full/raw facility CSV files must not be committed.
- Approved facility-reference rows preloaded into PostgreSQL can now enrich
    hosted canonical facility type, county, and status during ordinary CCLD
    retrieval or the governed preserved-artifact backfill. This narrow bridge
    does not make the browser lookup fixture authoritative, infer missing
    values, bridge other reference fields, fetch fresh public data, or prove
    reference completeness or currency. Facilities without approved matching
    reference rows retain their existing nonblank values and setup warnings.
- The local hosted scaffold facility hub can show facility review signals from
    supported ignored uploaded public licensing/visit/citation summary CSVs.
    A directory-backed hub shows facility name, Facility ID, facility type,
    status, one composed address, county, and capacity once in the primary fact
    block; program type, regional office, and closed date appear once in a
    secondary disclosure. Raw source column names and source dataset filenames
    remain outside the primary page.
    These signals are uploaded public summary fields only, not complaint records,
    not source verification, not legal findings, not complaint-coverage
    determinations, and not source-completeness proof. Malformed, shifted, or
    unsupported rows are skipped or counted internally without displaying raw row
    contents. Missing signals do not mean a facility has no complaints, visits,
    citations, POC dates, or public-source records.
    When a facility-directory row is not available locally but supported signals
    are available, the hub can render a signal-only facility hub with only its
    safe facility name/ID and review cues. That fallback is a navigation aid over
    uploaded public summary fields only; it does not
    diagnose official directory status, validate a license, verify a source,
    prove complaint coverage, or create complaint records.
    When authorized complaint records are loaded, the same route reuses the
    cross-facility intelligence calculations for stable complaint
    deduplication, finding and serious-review distributions, monthly anomaly
    cues, report-link coverage, and deterministic recommended-next ordering.
    It also reads separate reviewer-created status/note summaries and links
    aggregates to exact complaint records. Those summaries cover only the
    authorized loaded corpus and active filters; they do not prove public-source
    completeness, statewide coverage, legal conclusions, or facility-wide
    conduct. Reviewer-created note text and raw traceability internals remain
    outside the hub.
- Production-readiness items such as source-verification planning, auth provider
    integration, audit UI/export, export packet generation, reset/reload execution,
    public deployment, production monitoring, database-backed lookup, non-CCLD
    sources, and persisted tester feedback remain deferred
    unless they directly unlock tester value or resolve a concrete MVP-blocking
    risk.
- The QNAP-first Docker Compose runtime is a production-like container envelope
    for the hosted scaffold and PostgreSQL. It is not production authentication,
    public URL approval, fully production-ready hosted CCLD retrieval, production import
    automation, monitoring, incident response, or a guarantee that external
    testers can safely access the app yet.
- The QNAP pilot workflow checker validates env, Compose, optional containers,
    PostgreSQL readiness, Alembic state, and route status. It does not start a
    public deployment, create cloud resources, replace host backups, implement
    production sign-in, or make source-completeness/legal conclusions.
- Controlled browser-triggered CCLD retrieval has a first ADR-0016 implementation
    slice for CCLD complaint records. It remains CCLD-only, facility/date/type
    bounded, authenticated, permissioned, server-side, rate-limited,
    timeout-limited, retry-limited, raw-source-preserving, PostgreSQL-imported,
    safe-status, private-value-safe, and tested with mocked CCLD network retrieval.
    A local live startup command can use the public CCLD HTTP connector for
    explicitly submitted browser retrieval jobs, while a separate fixture/mock
    startup command remains available for offline validation. Direct
    browser crawling, statewide crawling, automatic source expansion, non-CCLD
    sources, private/authenticated source scraping, legal/facility-wide/public-
    source completeness conclusions, harm/abuse/neglect/liability conclusions,
    unsupported automated complaint findings, and unsupported record types remain
    out of scope. All supported record types currently resolves to complaint
    records only.
- The command-based batch complaint retrieval loader is an operator/data-loading
    path over the same controlled Request Records retrieval/import seam. It reads
    preloaded `hosted_facility_reference_records`, defaults to dry-run, writes
    ignored JSONL manifests under `data/processed/batch-retrieval`, and requires
    `--apply` before creating retrieval jobs, fetching public CCLD, importing
    source-derived rows, or preserving raw artifacts. It is not a scheduler,
    statewide crawl, completeness check, reviewer-facing redesign, non-CCLD
    source path, production auth implementation, or raw artifact viewer.
- The representative multi-facility coverage report is a read-only measurement
    over already-loaded hosted PostgreSQL facility-reference, source-derived
    complaint, import-batch, and retrieval-job metadata. It classifies rows as
    real public-source, clearly identified fixture/demo/test, or unknown from
    persisted provenance, and excludes non-real/unknown rows from representative
    counts. It documents loaded facility types, source files, source URLs,
    snapshot/retrieval dates, traceability counts, source-document linkage,
    duplicate source-derived identity checks, import-batch differences, and job
    failure/rejection counts. It does not run live CCLD calls, preload facility
    CSVs, import data, mutate reviewer-created state, infer missing values,
    persist skipped-row counts, prove production/QNAP coverage from PostgreSQL
    rows alone, prove statewide coverage, prove public-source completeness,
    reconcile every displayed result to original source records by itself, or
    replace manual browser evidence, source reconciliation, and acceptance.
    Facility-reference skipped-row counts remain in the preload command output
    and are not persisted in the current table.
- `CCLD_RETRIEVAL_DEMO_MODE=mock-success` is an explicit local-dev scaffold
    validation mode only. It uses committed fixtures to demonstrate successful
    job/import/history/detail/queue behavior without live CCLD calls. It is not
    production retrieval, not public-source completeness proof, and must not be
    enabled for QNAP, pilot-like, or production runtime.
- The local hosted scaffold `/ccld/retrieval/jobs` page shows recent controlled
    retrieval status/history from existing operational metadata only. It is not an
    audit export, CSV export, scheduler, worker console, source-completeness report,
    legal conclusion, or proof that all CCLD records for a facility/date range were
    found. It does not show raw source narrative content, raw artifact file
    contents, or server-specific raw paths.
- The local hosted scaffold `/ccld/retrieval/jobs/detail?job_id=` page shows one
    controlled retrieval job's safe operational metadata only. It is not a raw
    artifact viewer, audit record, CSV export, legal conclusion, or source-
    completeness report, and it does not show raw source narrative content, raw
    artifact file contents, raw server paths, stack traces, or private values.
- The local hosted scaffold `/facilities` list and detail pages use committed
    tiny public-source facility fixtures and manifest placeholder metadata only.
    The facility detail source coverage panel and related source-record links
    are fixture/sample display patterns only.
    They do not read ignored raw CSVs, generated profiling outputs, SQLite, a
    hosted database, live public-source data, import output, authentication
    state, or reviewer-created state, and they do not prove source
    completeness, statewide coverage, official facility status, or legal or
    facility-wide conclusions.
- Accessibility of third-party presentation layers must be validated before release.
- GitHub Actions availability and limits may depend on project policy and platform usage limits.
