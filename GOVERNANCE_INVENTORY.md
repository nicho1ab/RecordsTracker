# Governance Inventory

## Current state

- Active phase: production-discovery with local hosted scaffold implementation
  now started under ADR-0012.
- Current implementation state: the Python, SQLite, and Datasette proof of
  concept has proven governed ingestion, deterministic extraction, raw source
  preservation, source traceability, local validation and review support, and
  source-traceable exports. The hosted tester work currently consists of a
  local Python standard-library scaffold, health and smoke validation, local
  setup checks, and a read-only `/source-records` list/detail shell with local
  sample filtering/search and fixture/sample-only source traceability summary
  panels over fixture/sample records, plus a read-only `/facilities` list/detail
  sample view backed by committed tiny public-source facility fixtures and
  manifest placeholder metadata. Facility detail pages now include fixture-only
  source coverage indicators and related fixture/sample source-record context
  where the local sample mapping exists. Hosted tester PostgreSQL/Alembic work
  now includes dependency declarations, no-secret database URL validation, an
  Alembic script location, one narrow domain migration for controlled seeded
  import batch metadata and source-derived record staging, a local validated
  JSON artifact importer, a local/test database-backed read service over staged
  source-derived records, a local/test auth boundary scaffold for actor, role,
  account-status, scope, target, and audit-context checks, a narrow local/test
  auth provider integration planning seam that validates the ADR-0014 provider
  class and returns non-secret readiness steps without persistence, a narrow local/test
  authenticated source-derived HTTP/API read route seam, a narrow local/test
  authenticated reviewer workflow shell over that route seam with read-only
  queue/detail payloads, associated reviewer-created state read output, a
  compact derived summary on selected detail responses, and a narrow local/test
  note action and status action that resolve the selected source-derived detail
  context before delegating to existing reviewer-created write routes, a thin
  browser-accessible local/test reviewer UI shell that lets a local tester list/
  search seeded source-derived records, see list-level reviewer-created
  note/status indicators, open detail, view a plain-language record summary,
  safe source traceability fields with clearer selected-record and missing-value
  guidance, safe related seeded bundle context,
  reviewer-created notes/statuses, CCLD return links, and clearer record-specific
  feedback handoff cues, submit note/status forms through those existing workflow
  actions, see clearer saved-state confirmations, same-request return-to-queue
  progress guidance, and next-record steps,
  and see read-after-write
  reviewer-created state without exposing sensitive narrative fields, a browser-
  accessible local/test CCLD facility lookup page at `/ccld/facilities` that
  reads configured full local/test or committed tiny CCLD program facility
  reference CSV rows, searches safe scalar fields, shows the active reference
  source and fallback guidance, and carries a selected facility/license number
  into the request workflow without persistence, a browser-
  accessible local/test CCLD record request page at `/ccld/records/request` that
  accepts a CCLD facility/license number and optional date range, reads matching
  seeded source-derived rows, can load or refresh matching rows from local
  validated hosted seeded-corpus output through the existing source-derived
  import path, renders matching complaints as a guided facility/date-scoped
  request result queue with visible lookup/manual-entry request-context
  confirmation, first-time help, progress counts, reviewer-status
  filtering, reviewer note/status cues, source-traceability availability cues,
  suggested next-record links, clearer no-match/local validated load guidance,
  filtered-empty guidance, and a structured
  copyable tester feedback checklist, plus skip-to-main links and visible
  first-run next-step guidance, links matches
  into the reviewer UI, and explains the explicit
  external CCLD live-fetch and local/test artifact-builder commands when broader retrieval is needed without
  running live crawling, connector execution, reviewer-created state mutation,
  audit writes, feedback persistence, or non-CCLD behavior from browser requests, a narrow
  local/test reviewer-created state persistence scaffold table/service with
  authenticated actor attribution and stable source-derived record references,
  a narrow local/test authenticated reviewer-created state read route seam over
  those persisted scaffold rows with schema-backed filters and bounded search,
  a narrow local/test authenticated reviewer note creation route that stores
  bounded non-secret note text as reviewer-created scaffold payload under the
  existing state kind,
  a narrow local/test authenticated reviewer status creation route that stores
  bounded status values as reviewer-created scaffold payload under the existing
  state kind,
  a narrow local/test audit event persistence scaffold for successful reviewer-
  created state scaffold writes only, a narrow local/test authenticated audit
  history read route seam over those scaffold audit rows, a narrow local/test
  audit coverage planning seam over current and deferred audit categories, a local/test authenticated reset/reload
  dry-run seam that reports seeded import batch, source-derived record,
  reviewer-created scaffold row, and audit scaffold row impact without mutating
  data, a narrow local/test reset/reload execution-plan seam that turns those
  summaries into an ordered bounded non-destructive action plan, and a narrow
  local/test reset/reload operational planning metadata
  scaffold that persists explicit dry-run planning records only, plus a narrow
  local/test read-only route seam for those planning records, plus source-
  derived versus reviewer-created state boundary descriptors.
- Local-only sample filtering/search: implemented for the hosted source-record
  shell using in-memory fixture/sample records only.
- Fixture/sample-only source traceability summary panels: implemented for the
  hosted source-record list/detail shell using in-memory fixture/sample records
  only.
- Recent hosted sequence: PR #106 added the local hosted scaffold foundation,
  PR #107 added local setup checks, PR #108 added the first local-only read-only
  source-record view shell, and PR #109 added local-only semantic/accessibility
  validation for that shell.
- Primary UX direction: future primary reviewer UX belongs in a hosted reviewer
  application/API boundary, separate from Datasette, with a CCLD-only
  facility/license number plus optional date-range record request flow leading
  into source-traceable reviewer pages. Source-derived records must stay
  separate from reviewer-created state. The current scaffold is an
  implementation path toward that direction, not a final production framework,
  hosted live crawler, import automation path, or stateful reviewer workflow.
- Local-only scaffold status: the scaffold is local/test only, local to a
  development workstation, and not backed by live public data, ignored raw CSVs,
  generated profiling outputs, SQLite-backed sample UI routes, real provider
  login, auth middleware, persistent authorization storage, production reviewer
  UI behavior, full reviewer-
  created workflows, queues, annotations, corrections, exports, full audit trail, reset/reload
  execution, deployment, QNAP, Azure, AWS, or public URL behavior. Current API behavior is
  limited to local/test source-derived read handlers, reviewer workflow shell
  handlers that can compose associated reviewer-created state read output and a
  compact derived summary for selected details plus narrow note/status actions
  over the selected detail context, reviewer-created state scaffold service helpers,
  reviewer-created state read handlers with schema-backed filters and bounded
  search, the local/test browser reviewer UI shell over those existing seams,
  the local/test CCLD record request page over seeded source-derived records,
  local validated CCLD hosted seeded-corpus output, a guided request result
  queue/help surface, plus a CCLD-only local/test SQLite-to-hosted-seeded-corpus
  artifact builder,
  reset/reload dry-run and execution-plan handlers, and
  explicit reset/reload planning metadata helpers and read handlers that require
  test database, actor, and scope context.
  Current auth
  behavior is limited to local/test service, route, workflow-shell,
  reviewer-created state, audit, dry-run, auth provider planning, and
  planning-metadata guards over fixture actor contexts.
- Datasette role: Datasette remains retained for validation, inspection,
  debugging, local exploration, export support, and transition comparison. It is
  not the governed primary future reviewer UX.
- Public-source expansion status: `PUBLIC_SOURCE_DATA_INVENTORY.md` inventories
  future public-source candidates, uploaded CSV example planning, conceptual
  source adapter metadata, attorney focus-area planning, and gated feedback or
  GitHub intake planning without approving imports, connectors, schemas, hosted
  behavior, issue automation, role-based UI, multi-state support, or legal
  conclusions.

## Completed ADR decisions

- ADR-0001 accepted Python, SQLite, and Datasette for the initial proof of
  concept; ADR-0005 supersedes it only for the primary future reviewer UX.
- ADR-0002-local-review-experience accepted Datasette and SQLite local review
  improvements for the proof of concept and retained local review aid workflows;
  ADR-0005 supersedes it only for the primary future reviewer UX.
- ADR-0002-raw-source-storage accepted ordinary file storage for preserved raw
  source files and source traceability.
- ADR-0003 accepted avoiding optional paid platform dependencies in the baseline
  workflow.
- ADR-0004 accepted accessibility as a release gate.
- ADR-0005 accepted the Datasette exit governance transition and retained
  Datasette as a validation, inspection, debugging, local exploration, and
  export-support layer.
- ADR-0006 accepted the hosted tester MVP architecture boundary and the
  source-derived versus reviewer-created state separation.
- ADR-0007 accepted a hybrid hosted direction: keep the Python pipeline and
  SQLite/Datasette validation layer while planning a hosted relational reviewer
  state store and hosted reviewer application/API boundary.
- ADR-0008 accepted the conceptual data and review-state model boundary.
- ADR-0009 accepted controlled imports from validated pipeline output and
  rejected hosted live crawling or hosted connector execution for the tester MVP
  unless a later ADR approves them.
- ADR-0010 accepted the future schema and migration separation strategy without
  creating schemas or migrations.
- ADR-0011 accepted authenticated, role-scoped tester access boundaries without
  choosing or implementing an authentication provider.
- ADR-0012 accepted scaffold-first hosted tester MVP sequencing. Later local
  implementation PRs used that approval only for the local scaffold, setup
  checks, read-only sample source-record shell, and semantic/accessibility
  validation.
- ADR-0013 accepted hosted tester MVP operational boundaries for audit logging,
  export generation, reset/reload, and tester data retention, clearing the next
  product-moving implementation path without implementing schemas, APIs,
  imports, exports, full audit persistence coverage, reset commands, retention automation, or
  deployment.
- ADR-0014 accepted a managed standards-based OpenID Connect/OAuth 2.0 provider
  class and hosted tester MVP role implementation direction without
  implementing auth middleware, schemas, API routes, provider configuration,
  secrets, hosted URLs, or deployment.
- ADR-0015 accepted PostgreSQL as the hosted tester MVP database product and
  Alembic-managed migrations as the migration tooling direction without
  implementing schemas, tables, migrations, API routes, imports, reset commands,
  auth middleware, secrets, provider configuration, hosted URLs, deployment, or
  CI configuration.

## Remaining deferred decisions

- Concrete frontend framework, API framework, concrete auth provider instance
  and configuration, hosting platform, deployment pipeline, retention durations
  and automation, backup/restore policy, final design system, and production
  operations model.
- Controlled import comparison against retained SQLite/Datasette validation
  output, database-backed import API behavior, production import automation,
  reset/reload behavior, and richer import validation beyond the current tiny
  validated JSON artifact path.
- Physical hosted schemas, Alembic migration files, PostgreSQL table groups,
  indexes, constraints, and ORM models beyond the current seeded import,
  reviewer-created state scaffold, and audit event scaffold tables, including
  export packet state, tester feedback, auth role/scope references, and
  operational/reset metadata.
- Real provider authentication, token validation, session handling, auth
  middleware, role storage, invitation flow, account lifecycle, access
  revocation, access review, audit schema, and user deprovisioning
  implementation.
- Full audit persistence coverage, export builder implementation,
  reset/reload command or API implementation, tester feedback persistence,
  full reviewer-created state workflows, annotations, corrections, queues, and
  review-state behavior beyond the narrow scaffold table.
- QNAP, Azure, AWS, cloud deployment, public URL behavior, hosted live crawling,
  hosted connector execution, production monitoring, incident response, and
  operational support.

## Deferred readiness and product-benefit gate

Deferred readiness items must stay visible, but they should not automatically
become the next implementation branch. Future Copilot tasks should pass this
product-benefit gate before adding backend readiness, hardening, planning, or
checklist work:

1. What user-facing CCLD MVP capability, tester productivity improvement, or
  concrete MVP-blocking risk does this branch address?
2. Why is it needed now rather than after the next facility lookup, request,
  queue, reviewer-detail, accessibility, or feedback improvement?
3. What becomes possible for a local/test CCLD tester after the branch that is
  not possible today?

If the answer is only that a future backend, audit, auth, export, deployment, or
readiness layer is theoretically important, keep the item deferred. A readiness
branch is appropriate when it directly unlocks the CCLD local/test user workflow
or removes a concrete MVP-blocking risk. MVP usability is not cosmetic polish:
clear forms, efficient facility lookup, understandable result states,
accessible structure, contextual help, low-friction reviewer actions, and useful
feedback capture are product requirements when they reduce tester confusion
without creating avoidable rework.

| Deferred item | Why deferred | User-facing milestone first | Necessary when | Needed before |
|---|---|---|---|---|
| Reviewer detail source-verification planning/checklist | Current detail pages already show safe source context; more planning should not displace lookup/request/queue usability unless testers cannot verify records. | Improve reviewer detail usability for actual CCLD complaint review. | Testers cannot reliably confirm source URL, raw hash, raw path/artifact reference, connector metadata, retrieval time, source document ID, report index/type, or visible extraction-audit context. | Local tester MVP if verification blocks useful review; otherwise pilot. |
| Production auth/provider integration | Local/test actor boundaries are enough for current workstation-only testing. | Finish the CCLD local/test request, review, notes/status, accessibility, and feedback loop. | External testers need individual access, revocation, attribution, or scoped collaboration. | Pilot. |
| Audit UI/export and fuller audit coverage | Current audit scaffold covers successful reviewer-created state writes only and no tester-facing audit UI is needed for the first local loop. | Stabilize reviewer actions and feedback context that would later need audit visibility. | Testers or operators need to inspect audit history to resolve review-state trust, support, or accountability issues. | Pilot or production, depending on use. |
| Export packet generation | Existing Datasette/review-bundle exports remain retained for validation and local handoff support. | Make CCLD review queues and detail pages useful enough to decide what should be exported. | Review handoff requires curated packet membership, source traceability, reviewer-created context, and accessible output beyond retained CSV exports. | Pilot. |
| Reset/reload execution | Dry-run and execution-plan seams exist; destructive or state-changing behavior needs stronger reviewer-created state handling and audit policy. | Prove local validated load/refresh and reviewer state are useful in repeated CCLD sessions. | Test data must be repeatedly refreshed while preserving, archiving, or explicitly clearing reviewer-created state. | Pilot. |
| Production deployment | The scaffold is local/test only and should not be hosted before the product loop is useful and access boundaries are implemented. | Complete a useful local/test CCLD review loop with accessible pages and feedback. | External tester access, secure hosting, monitoring, and support are approved and necessary. | Pilot/production. |
| Database-backed facility lookup or production facility reference import/sync | CSV-backed lookup is sufficient for local/test facility selection and avoids premature schema work. | Validate that full local/test facility CSV lookup materially helps testers find records. | Facility reference data needs refresh history, reconciliation, permissions, provenance, or query scale beyond local CSV. | Pilot or production. |
| Live browser retrieval or connector execution | Browser-triggered crawling is explicitly out of scope and raises rate-limit, audit, error, and source-preservation risks. | Keep live fetch explicit through scripts and local validated artifacts. | A later approved architecture defines safe execution, rate limits, audit, source preservation, and tester messaging. | Not needed for local tester MVP. |
| Non-CCLD sources | The first MVP remains CCLD-only. | Complete the CCLD request, review, feedback, accessibility, and validation loop. | CCLD MVP learning has stabilized and a new source has inventory, fixtures, connector contract, limitations, and governance approval. | After CCLD MVP. |
| Persisted tester feedback | Copyable checklist is enough for first local/test feedback without schema work. | Learn what feedback testers actually provide through the external channel. | Feedback volume, triage, linkage to source records, or accountability requires app-managed state. | Pilot. |
| Broader reviewer workflow layers | Current notes/status are intentionally narrow. | Validate that facility lookup, request queue, detail pages, and feedback checklist support the first review loop. | Testers need assignments, richer statuses, annotations, corrections, review history, or collaboration to continue. | Pilot. |

## Stale guidance assessment

- Datasette-primary assumptions are stale when they imply Datasette should be
  extended as the primary future reviewer UX. Datasette remains valid only for
  retained validation, inspection, debugging, local exploration, export support,
  and transition comparison.
- POC-only language remains accurate when it describes historical proof-of-
  concept decisions, but current planning should describe production-discovery
  and the local hosted scaffold implementation state.
- Older ADR statements saying app scaffold work was not approved were accurate
  when written. They are now superseded only by ADR-0012 and the later local
  scaffold implementation PRs. They do not approve schemas, authentication,
  authorization, imports, queues, annotations, corrections, exports, reset/
  reload, hosted deployment, hosted live crawling, hosted connector execution,
  source-derived canonical field changes, reviewer-created state persistence, or
  extraction behavior changes.
- Roadmap items for the first hosted scaffold, local setup checks, local-only
  read-only source-record shell, semantic/accessibility validation, and
  local-only sample filtering/search, and fixture/sample-only source
  traceability summary panels, local CSV profiling, tiny public-source facility
  fixtures, the first fixture-backed facility master sample view, and the
  fixture-only facility source coverage panel are complete. ADR-0013 completed
  the operational boundary decision for audit, export, reset/reload, and
  retention planning. ADR-0014 completed the auth provider-class and role
  implementation direction decision. ADR-0015 completed the database and
  migration tooling decision. Minimal PostgreSQL/Alembic scaffold wiring,
  schema/API boundary descriptors, a controlled seeded corpus import path,
  database-backed source-derived read service, local/test auth boundary
  scaffold, local/test auth provider integration planning seam, local/test
  source-derived read route seam, and first local/test
  read-only authenticated tester workflow shell, reviewer-created state
  persistence scaffold, narrow audit event scaffold, local/test reset/reload
  dry-run planning seam, opt-in reset/reload operational metadata scaffold, and
  read-only planning metadata route seam are now in place. Next work should
  move to real provider implementation beyond this non-persistent readiness plan,
  later reset/reload execution behavior
  beyond this non-destructive execution-plan seam,
  export/feedback persistence, fuller audit coverage, or
  stateful reviewer-created workflow layers, not repeat those completed items.
- Local-only/sample-only boundaries remain active. Sample records must stay
  clearly marked as fixture/sample records and must not be presented as live,
  database-backed, complete, statewide, official, or production data.
- QNAP, Azure, AWS, public URL, cloud deployment, hosted connector execution,
  and hosted live crawling remain deferred.

## Gap analysis

- Future fixture-backed source view expansion: additional source-record fields,
  list/detail states, empty states, navigation states, filter facets, or
  traceability summary states should be backed by representative fixtures and
  semantic/accessibility validation before any live or database-backed source is
  introduced.
- Future import path into hosted view: source-derived hosted records now have a
  first controlled JSON artifact import path with batch metadata, stable
  identities, idempotent source-derived staging, and source traceability tests.
  They also have a local/test database-backed read service for list and fetch
  access that preserves import batch context and original source-derived values.
  They now have a narrow local/test authenticated HTTP/API read route seam for
  JSON list and fetch access over that read service, plus a narrow local/test
  authenticated reviewer workflow shell for read-only queue/detail payloads over
  that route seam with associated reviewer-created state read output on selected
  detail responses, a compact derived summary, and note/status actions that
  delegate to existing reviewer-created write routes after resolving the
  selected source record,
  plus a narrow local/test reviewer-created state
  scaffold that can write and read attributed placeholder rows separately from
  source-derived records, plus a narrow local/test audit event scaffold for
  successful reviewer-created state scaffold writes only, plus a narrow
  local/test audit history read route seam for those scaffold audit rows, plus a
  narrow local/test audit coverage planning seam that creates no audit rows, plus a local/test
  reviewer note creation route that writes bounded non-secret note payloads
  through the existing reviewer-created scaffold write/audit path, plus a local/test
  reviewer status creation route that writes bounded status payloads through the
  same scaffold write/audit path, plus a local/test
  authenticated dry-run seam that reports seeded corpus reset/reload impact and
  an execution-plan seam that orders those non-destructive planning steps and
  scoped reviewer-created scaffold and audit scaffold row counts without
  deleting, overwriting, archiving, importing, reloading, or creating new dry-run
  audit events, plus an opt-in operational metadata scaffold and read route seam
  for persisted dry-run planning records. ADR-0013 still defines reset/reload and audit expectations at
  the operational boundary;
  implementation still needs
  comparison against retained SQLite/Datasette validation output, production
  import operations, stateful reviewer-created workflow layers, and
  reset/reload execution behavior and full audit coverage beyond the scaffolded
  reviewer-created state write event.
- Future database/schema implementation: the current domain schema is limited to
  seeded import batch metadata and source-derived staging. Future schema work
  must use PostgreSQL and Alembic-managed migrations while preserving separate
  physical areas or table groups for reviewer-created state, audit events,
  export packet state, tester feedback, auth role/scope references, and
  operational/reset metadata.
- Future auth/access implementation: hosted tester access must use the
  ADR-0014 managed OpenID Connect/OAuth 2.0 provider class, remain explicitly
  invited or provisioned, role-scoped, project/corpus-scoped, revocable,
  reviewable, and auditable where feasible before tester workflows expose
  reviewer-created state. The current scaffold validates the provider class,
  produces a local/test non-secret provider integration readiness plan, and
  enforces local/test role, scope, and account-status checks for service seams;
  real provider login, token validation, session handling, middleware, provider
  registration, hosted URLs, and persistent role/scope assignments remain
  deferred.
- Future deployment/hosting decision: QNAP, Azure, AWS, public URL, cloud
  deployment, DNS, app registration, cloud database, and deployment credential
  choices remain deferred and must not be implied by local scaffold tooling.
- Future audit, reviewer-state, correction, export, feedback, and reset/reload
  workflows: ADR-0013 defines the operational boundaries for audit, export,
  reset/reload, and retention. Implementations must still preserve them as
  reviewer-created state and operational layers that do not overwrite
  source-derived canonical records, raw source files, source document metadata,
  extraction audit rows, source URLs, raw hashes, connector metadata, retrieval
  timestamps, or original extracted values.
- Future public-source expansion: structured CSV/open-data files, HTML portal
  pages, PDFs, metadata/catalog pages, and future multi-state sources need
  source inventory entries, local profiling, terms and sensitivity review,
  source metadata, traceability requirements, fixture plans, parser warnings,
  and caution language before connector, import, schema, or hosted-view work.
- Future attorney focus profiles and feedback intake: focus profiles may guide
  queues, filters, dashboards, and issue spotting only after implementation
  decisions define the relevant layer. Feedback or bug reports may integrate
  with GitHub only after triage, classification, privacy/secrets review,
  duplicate check, priority/severity assignment, human approval, and traceable
  issue linkage are defined.

## Safeguards preserved

- Source traceability and raw source preservation remain mandatory.
- Deterministic extraction and fixture-backed regression expectations remain in
  force.
- Accessibility, security, privacy, and cautious public-source language remain
  release gates.
- The system must not make unsupported legal, facility-wide, public-source
  completeness, delay, harm, abuse, neglect, liability, or rights-deprivation
  conclusions.
- Source-derived records remain separate from reviewer-created state.
- Sample data must stay clearly marked as sample-only.