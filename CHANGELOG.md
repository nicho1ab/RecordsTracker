# Changelog

## Unreleased

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
	guardrails before inviting early ylc.org testers.
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
	and do-not-do guardrails before inviting early ylc.org testers.
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
	accessible form, exact feedback type options for bug reports, feature
	requests, and new data sources, safe validation/unconfigured/success/failure
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
	YLC pilot direction: production mode now blocks anonymous browser workflow
	routes, explicit local-dev mode enables the fixture tester actor for local
	scaffold testing, `/auth/login`, `/auth/logout`, and `/auth/status` expose safe
	placeholders/status only, reviewer pages show a safe signed-in tester label,
	QNAP/env docs list OIDC/OAuth2 placeholder variables, and focused tests cover
	production blocking, local-dev opt-in, role/scope permissions, disabled or
	revoked actors, out-of-scope actors, and no-secret output without adding custom
	password storage, sessions, cookies, token handling, raw provider claims,
	provider secrets, hosted URLs, or DSCC-specific assumptions.
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
