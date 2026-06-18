# Hosted Scaffold

## Purpose

This document explains how to run the first local hosted tester MVP scaffold.
The scaffold is a runnable local/test app shell. It now includes a thin
browser-accessible reviewer UI shell over the seeded fixture corpus and existing
workflow seams; it is still not a production reviewer application or stateful
hosted tester workflow.

The scaffold is local-first and must run on a Windows development workstation
for ordinary development. A separate QNAP-first Docker Compose runtime now exists
for production-like validation with PostgreSQL in Docker, but it packages the
same scaffold and does not approve public hosting. The first provider-agnostic
auth runtime boundary exists for external stakeholder organization pilot planning: production mode blocks
anonymous workflow routes, and explicit local-dev mode supplies the fixture
tester actor for local validation only. It uses Python standard-library HTTP
tooling to avoid creating a final production frontend, API, database,
authentication, hosting, or deployment commitment.

## Required local tools

- Windows PowerShell.
- Python 3.11 or newer.
- The repository development dependencies from `requirements-dev.txt` for
  tests, lint, and type checks.
- The runtime dependencies from `requirements.txt`, including Alembic,
  SQLAlchemy, and the PostgreSQL driver used by the scaffolded migration
  wiring.

Node.js is not required. Docker is not required for the local non-Docker
developer workflow. QNAP Container Station is not required for local scaffold
smoke, boundary tests, or seeded artifact parsing tests.
No local PostgreSQL server is required for scaffold smoke, boundary tests, or
seeded artifact parsing tests. A PostgreSQL-compatible database URL is required
only when a developer explicitly runs Alembic migrations or the seeded corpus
import command. The database-backed read service and auth boundary scaffold can
be exercised in unit tests against in-memory SQLite and fixture actors. The auth
provider integration planning seam can be exercised in unit tests with explicit
local/test actor and scope context and non-secret readiness inputs. The
source-derived API route seam can also be exercised in unit tests with an
explicit local/test route context. The reset/reload dry-run seam can be
exercised in unit tests with an explicit database, actor, and corpus scope
context, including optional persisted planning metadata and read-only planning
metadata route access. The reset/reload execution-plan seam can also be
exercised in unit tests with that explicit local/test context and produces only
bounded non-destructive action-plan output. No cloud resources, public URLs, app
registrations, cloud databases, DNS records, deployment credentials, secrets, or
tokens are required.

## Verify local prerequisites

Run the local setup check from the repository root after installing project
dependencies:

```powershell
.\scripts\check-hosted-scaffold-local.ps1
```

The check verifies the Python version, hosted scaffold package import, and local
development tools used for focused tests, lint, and type checks. It also checks
that Alembic, SQLAlchemy, and the PostgreSQL driver are importable for the
scaffolded migration wiring. It reports that Node/npm, Docker, a local
PostgreSQL server, QNAP, cloud resources, and a public URL are not required for
local scaffold smoke, boundary tests, or seeded artifact parsing tests.

The local setup check does not install software, does not require admin rights,
does not create secrets, and does not contact cloud services. It does not
validate the optional Docker runtime; use the Compose checks in
`docs/developer/qnap-docker-runtime.md` when working on that path.

## Install dependencies

From the repository root, create and activate a local virtual environment if one
does not already exist:

```powershell
py -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

Install runtime and development dependencies:

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Start the scaffold locally

Run the scaffold from the repository root:

```powershell
.\scripts\run-hosted-scaffold.ps1 -Port 8000
```

Open `http://127.0.0.1:8000/` on the same workstation. The page must identify
itself as a local/test scaffold. It may link to the local/test reviewer UI shell
but must not imply that real OIDC login, token handling, sessions, cookies, full
reviewer workflows, cloud hosting, QNAP, Azure, AWS, or public URLs are
available. The PowerShell script explicitly sets `CCLD_HOSTED_TESTER_AUTH_MODE`
to `local-dev` and `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH` to `enabled` when those
variables are not already set, so local browser workflow pages can use the
fixture tester actor. Production/QNAP runtime should keep local-dev auth
disabled. The same script sets `CCLD_HOSTED_PAGE_DATA_MODE=fixture-demo` unless
the variable is already set, so workstation demos can still use fixture data.
Production/QNAP runtime should use `CCLD_HOSTED_PAGE_DATA_MODE=postgres`.

To start the same local scaffold with controlled complaint retrieval enabled in
live public CCLD mode, use the explicit live wrapper instead:

```powershell
.\scripts\run-hosted-complaint-retrieval-live.ps1 -Port 8000
```

This wrapper sets explicit local-dev auth, fixture/demo page data, controlled
retrieval enablement, a blank `CCLD_RETRIEVAL_DEMO_MODE`, and ignored local raw
source storage under `data/raw/ccld/retrieval-live`. Browser-triggered jobs use
the real public CCLD HTTP connector from the server. Startup output labels Live
public CCLD retrieval mode, prints exact local URLs, and states that public CCLD
HTTP requests happen only after browser submit. The CCLD public portal remains
the source of record, and zero imported records is not proof that no complaints
exist.

For the offline fixture-backed demo, use:

```powershell
.\scripts\run-hosted-complaint-retrieval-demo.ps1 -Port 8000
```

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/ccld/records/request
http://127.0.0.1:8000/ccld/retrieval/jobs
http://127.0.0.1:8000/reviewer
http://127.0.0.1:8000/ccld/help
http://127.0.0.1:8000/feedback
```

The demo wrapper sets explicit local-dev auth, fixture/demo page data,
controlled retrieval enablement, `CCLD_RETRIEVAL_DEMO_MODE=mock-success`, and
ignored local raw source storage under `data/raw/ccld/retrieval-demo`. Normal
`run-hosted-scaffold.ps1` startup remains unchanged and still shows the setup-
required state when retrieval configuration is incomplete.
The demo startup output labels Fixture/mock demo mode, prints exact local URLs,
and states that it does not make live CCLD calls.
The home page is now a guided launch screen for `CCLD RecordsTracker Pilot`: it
shows the active retrieval mode, one dominant `Start review` action, secondary
facility/queue/jobs/feedback actions lower on the page, collapsed developer/
operator commands, and concise source-of-record boundary language. The hosted
pages share a compact non-wrapping progress component, simplified workflow
navigation without diagnostic links in the primary nav, progressive request
workflow, native facility type-ahead with manual fallback, focused retrieval
result/recovery states, status-center job pages, worklist-style reviewer queue
with technical runtime details collapsed, summary-first reviewer detail
workspace, card-prefilled feedback, collapsible help, skip-to-main links, strong
focus styling, readable tables/forms, and mode badges for Live public CCLD,
Fixture/mock demo, and Retrieval not configured. This presentation work does not
add routes, workflows, frontend dependencies, auth, exports, deployment, non-CCLD
scope, or new state behavior.

When selecting the next hosted scaffold task, apply the product-benefit gate in
`GOVERNANCE_INVENTORY.md`. Backend readiness, hardening, planning, or checklist
work should be next only when it directly improves the CCLD local/test tester
workflow or removes a concrete MVP-blocking risk; otherwise keep it tracked as
deferred readiness.

## Start the production-like Docker runtime

QNAP Docker is the first practical production-like runtime target. The runtime
uses Docker Compose, the existing Python hosted scaffold app, PostgreSQL in
Docker, named volumes, health checks, and Alembic migrations on app startup. It
keeps QNAP-specific host paths out of application code so the same environment
and volume model can move later to AWS, Azure, DigitalOcean, Render, Fly.io, or
another host.

Before starting a QNAP pilot, validate the untracked `.env` and Compose shape:

Use the full [QNAP pilot operator checklist](qnap-pilot-operator-checklist.md)
before inviting early testers.

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env
```

Copy `.env.example` to an untracked `.env` file on the Docker host, replace
placeholder values, then run:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env up --build -d
```

Open the hosted scaffold at the configured host port and check `/health` before
using the CCLD pages. See [qnap-docker-runtime.md](qnap-docker-runtime.md) for
environment variables, migrations, volumes, backup/restore, health checks, and
portability notes.

When the containers are running, the same pilot checker can also verify container
state and routes:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -CheckContainers -BaseUrl http://<host-name-or-ip>:<CCLD_HOSTED_PORT>
```

This Docker runtime does not add production sign-in, sessions, cookies, hosted
live retrieval, browser-triggered connector execution, public URL approval,
monitoring, production import automation, or a new frontend framework.

## Auth Runtime Boundary

The hosted auth boundary follows ADR-0014's managed OpenID Connect/OAuth 2.0
provider class without choosing a provider-specific tenant or committing secrets.
Production mode is the default. In production mode, browser workflow pages such
as `/reviewer` and `/ccld/records/request` return sign-in-required guidance when
no authenticated route context is available; public landing, health, and CCLD
help pages remain readable.

The scaffold includes safe placeholders:

- `/auth/login`: describes the managed OIDC sign-in seam without redirecting,
  exchanging auth codes, or creating sessions.
- `/auth/logout`: explains that no scaffold browser session exists in this
  branch.
- `/auth/status`: returns a non-secret configuration summary that reports mode,
  whether OIDC placeholders are configured, and whether local-dev actor mode is
  allowed.

Provider-specific deployment values belong only in untracked host configuration:

```text
CCLD_HOSTED_TESTER_AUTH_MODE=production
CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS=managed-oidc-oauth2
CCLD_HOSTED_TESTER_OIDC_ISSUER=<provider-issuer-placeholder>
CCLD_HOSTED_TESTER_OIDC_CLIENT_ID=<provider-client-id-placeholder>
CCLD_HOSTED_TESTER_OIDC_CALLBACK_PATH=/auth/callback
CCLD_HOSTED_TESTER_OIDC_SCOPES=openid profile
CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled
```

Do not commit provider secrets, hosted callback URLs, tenant-private values,
tokens, cookies, raw provider claims, or real user identifiers. Reviewer pages may
show a safe signed-in tester label when an actor context is present, but they
must not render provider subjects, issuers, raw claims, tokens, cookies, or
private headers.

## GitHub Issues Feedback Intake

The `/feedback` route provides the first real tester feedback workflow. It uses
a server-rendered form with exactly three feedback types: Bug report, Feature
request, and New data source. Submissions create GitHub Issues only when the
server has `GITHUB_FEEDBACK_REPO` and `GITHUB_FEEDBACK_TOKEN` configured.

Optional `GITHUB_FEEDBACK_DEFAULT_LABELS` can add comma-separated labels. Every
app feedback issue receives `feedback`, `from-app`, and `needs-triage`, plus one
type label: `bug`, `feature-request`, or `new-data-source`.

The token is server-side only. It must not appear in HTML, JavaScript, logs,
tests, screenshots, issue bodies, or docs. Tests use mocked clients and must not
make live GitHub API calls. The first implementation creates GitHub Issues
without local feedback persistence or schema changes.

## Page Data Mode

Core hosted pages now choose their data source explicitly:

- `CCLD_HOSTED_PAGE_DATA_MODE=postgres`: production-style mode. Facility lookup
  reads source-derived facility rows from `hosted_source_derived_records` through
  the hosted service context, request queues read source-derived records through
  the source-derived route seam, and reviewer detail composes source-derived plus
  reviewer-created state from database-backed contexts.
- `CCLD_HOSTED_PAGE_DATA_MODE=fixture-demo`: local/demo mode only. The scaffold
  uses the tiny committed fixture corpus and CSV fallback paths for tests and
  workstation demos.

When PostgreSQL mode is selected but no migrated/imported database context is
available, pages show setup-required guidance. They do not silently fall back to
fixtures, run live CCLD retrieval, execute connectors, mutate source-derived
records, or expose raw narrative fields. Controlled CCLD retrieval requires a
configured retrieval context and server-side raw storage; otherwise the request
page shows setup-required guidance and creates no retrieval job.

## Controlled CCLD Retrieval Jobs

The first ADR-0016 retrieval slice is server-side and CCLD-only. The browser
submits only facility/license number, record type, start date, and end date.
Supported record types are `complaints` and `all_supported`; all supported
currently resolves to complaint records only. The server validates inputs,
requires retrieval trigger permission, discovers CCLD complaint-section report
links for the requested facility, prefilters discovered links to the requested
date range before fetching reports, enforces CCLD source URL allowlists,
preserves raw source artifacts under configured server-side storage, computes raw
SHA-256 hashes, deterministically extracts/normalizes/validates, imports
source-derived rows into PostgreSQL, and renders safe job state/result counts.

Retrieval is disabled unless host configuration includes retrieval enablement and
raw storage, such as:

```text
CCLD_RETRIEVAL_ENABLED=enabled
CCLD_RETRIEVAL_RAW_DIR=/app/data/raw/ccld/retrieval
```

For local live public CCLD retrieval, use:

```powershell
.\scripts\run-hosted-complaint-retrieval-live.ps1 -Port 8000
```

For local scaffold validation only, use the fixture/mock wrapper to enable a
fixture-backed successful retrieval demo while running explicit local-dev auth
and fixture/demo page data:

```powershell
.\scripts\run-hosted-complaint-retrieval-demo.ps1 -Port 8000
```

The live wrapper leaves `CCLD_RETRIEVAL_DEMO_MODE` blank, so configured jobs use
the real public CCLD HTTP connector. The fixture/mock wrapper uses committed
CCLD fixtures through a local fixture client. It does not make live CCLD calls,
does not call GitHub, does not prove public-source completeness, and is
unavailable unless explicit local-dev auth/scaffold mode is allowed. Do not use
`CCLD_RETRIEVAL_DEMO_MODE=mock-success` for QNAP, pilot-like, or production
runtime.

The live browser-triggered path was manually verified with facility/license
number `157806098` and date range `2022-08-01` to `2022-08-31`. The job ran in
live public CCLD mode, discovered complaint candidates from public CCLD metadata,
selected and fetched one matching report bundle, imported source-derived rows,
and made the complaint visible in the reviewer queue.

Tests use mocked CCLD retrieval only. CI must not make live CCLD calls. Direct
browser scraping, non-CCLD sources, statewide crawling, private/authenticated
source scraping, production OIDC, deployment changes, and legal/completeness
conclusions remain out of scope.

Retrieval status pages now distinguish live public CCLD mode from fixture/mock
demo mode. They also distinguish setup-required, validation, queued, running,
completed, completed-with-warnings, failed, and rate-limited states with plain
next steps. Safe summaries show what was requested, whether a job was created,
whether records were imported, discovered/selected/fetched/imported counts,
where to review imported records, and when to send `/feedback` for confusing
status or wording. Zero-import warnings distinguish no complaint candidates,
candidates outside the date range, fetched/extracted records that did not match
after validation, and source/network/layout failures.

The scaffold also exposes a small read-only retrieval job history/status page at:

```text
http://127.0.0.1:8000/ccld/retrieval/jobs
```

The page reads existing `hosted_ccld_retrieval_jobs` operational metadata for the
current authorized scope. It shows recent job state, requested facility/date/type,
created and last-updated timestamps, imported-record counts, safe warning/error
summaries, status messages, raw-artifact-preserved indicators without raw paths,
links back to `/ccld/records/request`, review-queue links when records were
imported, and `/feedback` guidance for confusing or failed jobs. It is not an
audit UI, audit export, CSV export, scheduler, distributed worker queue, or broad
operational console.

Each history row links to a read-only detail page shaped like:

```text
http://127.0.0.1:8000/ccld/retrieval/jobs/detail?job_id=<job-id>
```

The detail page repeats one job's safe request context, state, timestamps,
imported-record count, warning/error summaries, raw-artifact-preserved status,
review-queue link when records were imported, and history/request/help/feedback
links. It does not show raw artifact file contents, raw source narrative text,
raw server paths, stack traces, provider values, or private configuration.

## Open the CCLD record request page

The scaffold includes a browser-accessible local/test CCLD facility lookup page at:

```text
http://127.0.0.1:8000/ccld/facilities
```

The lookup is CCLD-only. It reads a full local/test CCLD program facility CSV or
CDSS/CHHS facility-directory CSV when `CCLD_FACILITY_REFERENCE_CSV` points to one
or when a file is available at the ignored local path
`data/raw/ccld/facility-reference.csv`. When that full CSV is not configured,
unavailable, or malformed, the lookup falls back to the committed tiny fixture
CSV. Testers can search by facility/license number, facility name, city, county,
ZIP code, facility type, program type, capacity, or status code when those fields
are present. Results are bounded and display safe scalar directory fields only.
The active reference source and any fallback guidance are visible on the page.
The `Start complaint request` action carries the selected facility/license number into
`/ccld/records/request`. Manual facility/license entry on the request page remains
available.
The request page includes a polished inline type-ahead combobox (accessible
label/input pair, JSON-embedded reference data, keyboard-navigable suggestion
list, selected-facility confirmation card with a "Change" affordance) so a tester
does not have to leave the request page for ordinary facility selection. It shows
a compact no-facility-selected context card before input, then selected
request-context cards for lookup-selected, prefilled, and submitted requests.
When only the tiny committed fixture is active, a "Limited reference list" note
appears and internal scaffold labels are confined to a collapsed `<details>` block.
The page includes a skip-to-main link, start-here instructions, a labeled search
field with help text, and a no-JS submit button fallback.

The lookup does not run live CCLD retrieval, execute connectors, persist lookup
data, mutate source-derived records, mutate reviewer-created state, create audit
rows, persist operational metadata, prove public-source completeness, or support
non-CCLD sources. Full/raw facility CSV files must remain ignored local files and
must not be committed.

The scaffold includes a browser-accessible local/test CCLD record request page at:

```text
http://127.0.0.1:8000/ccld/records/request
```

The page is CCLD-only. It accepts a digit-only CCLD facility/license number and
an optional start and end date. Complaint records are the fixed record type for
this pilot. The main form distinguishes `Retrieve complaint records`, which
creates a controlled server-side retrieval job when configured, from `Show
current queue`, which displays already loaded matching records without running
retrieval. It reads the existing seeded source-derived records through the
local/test hosted route seams, shows matching seeded CCLD complaint records as a
facility/date-scoped review queue, includes scannable workflow help at
`/ccld/help`, and links matching complaint records into the hosted reviewer UI
detail or list pages.
The CCLD pages use consistent plain-language terms for request context,
facility/date request, loaded local/test CCLD records, source-derived records,
reviewer-created notes/status, reviewer-status filters, suggested next records,
and the manual feedback checklist.
Home, request/help, queue, reviewer detail, note/status confirmation, and
checklist wording now orient first-time testers to the same CCLD review session
path without creating saved review sessions or persisted workflow state.
Request and result pages visibly confirm whether the context came from facility
lookup or manual entry, the facility/license number, the date range, and the
active local/test facility reference source before a tester reviews queue rows.
When retrieval jobs complete, result cards show status and mode badges, imported
record counts, discovered/selected/retrieved/matched/imported/failure counts,
safe warnings/errors, direct `Review imported records` and `View job details`
actions, and specific zero-import reasons such as candidates outside the selected
date range or retrieval not configured.
The queue includes a triage summary, progress counts, reviewer note/status cues,
source-traceability availability cues, suggested next-record links, and a
reviewer-status filter derived from existing reviewer-created note/status rows.
Records with no reviewer status are counted as not started. After a tester saves
a note or status in the reviewer UI, returning with the same facility/date
request context and submitting the same CCLD request again shows updated queue
progress and note/status cues derived from reviewer-created state.
Filtered-empty states explain how to return to all queue records without
implying that local/test or public-source records are missing, deleted, or absent.
Queue and reviewer-detail pages now use short continuity cues to tell testers
that queue observations and detail observations belong in the same existing
manual feedback checklist.
The request and result pages include skip-to-main links, visible first-run
next-step guidance, specific request/filter/load action text, and manual
feedback-copy instructions. These are presentation-only accessibility aids and
do not change request, import/reload, reviewer note/status, or queue behavior.

When no matching hosted rows are available, the page can offer a bounded local
validated CCLD load action. That action reads committed local/test hosted
seeded-corpus JSON output, validates the CCLD facility/date request, and stages
matching CCLD source-derived rows through the existing idempotent hosted seeded
import path. The result page reports matching rows before and after the load,
new source-derived rows staged, existing rows refreshed, duplicate rows avoided,
local validated rows outside the request, any deferred reason, source
traceability summaries, loaded-record bundle context, and reviewer-state
indicators from existing reviewer-created state reads.
No-match pages also explain that the request searched only currently loaded
local/test source-derived rows. They show the searched facility/license number,
date range, local rows available before date filtering, and local validated load
state; prompt testers to change facility/date criteria when the active context is
wrong; and tell testers to use the manual feedback checklist when records seem
missing or unexpected. A no-match result is not a public-source absence,
record-completeness, legal, or facility-wide conclusion.

The page does not run live crawling, execute connectors, write reviewer-created
state, create audit rows, persist operational metadata, destructively delete or
overwrite source-derived rows, or support non-CCLD sources. When broader retrieval
is needed, it still shows the explicit outside-browser handoff: run the CCLD
live fetch command when live public requests are intended, validate the SQLite
output, run the local/test artifact builder, then return to the request page to
load or refresh the generated hosted seeded-corpus JSON.
The feedback section is guidance-only; it explains what a tester should capture
about facility lookup, request criteria, missing or unexpected records, source
traceability cues, reviewer detail, note/status confirmation, return-to-queue
behavior, confusing wording, unexpected queue or filter behavior, workflow
friction, or desired features. Request results also include a structured
copyable checklist with the facility/date request, matching record counts, queue
status counts, local validated load context, source-traceability cue context,
reviewer note/status context, reviewer-detail confirmation prompts, and
manual-copy/non-persistence boundary reminders.
The app does not save or send that checklist; testers must copy it into the
agreed external feedback channel manually.

To build that local/test hosted seeded-corpus JSON from validated CCLD SQLite
output, run:

```powershell
.\scripts\build-hosted-ccld-artifact.ps1 -DbPath data\processed\ccld.sqlite -FacilityNumber 157806098 -Overwrite
```

The default output path is
`data/processed/hosted_seeded_corpus/validated_ccld_seeded_corpus.json`. The
builder is CCLD-only, validates required source traceability before writing,
rejects private or absolute raw paths, produces deterministic output when given
deterministic metadata, and does not make live public web requests.

## Open the local/test reviewer UI shell

The scaffold includes a browser-accessible local/test reviewer UI shell at:

```text
http://127.0.0.1:8000/reviewer
```

The page loads only the tiny seeded fixture corpus into process-local test state
and supplies a fixture local/test reviewer actor from the scaffold process. It
lets a local tester search/select a seeded source-derived complaint record, see
list-level reviewer-created note/status indicators before opening detail, open
detail, view a plain-language record summary, safe source traceability fields,
clear available/missing traceability cues, source-confidence cues for present,
missing, and proxy-flagged local/test complaint fields, field-note guidance for
cautious reviewer-created observations, safe related seeded bundle context,
reviewer-created notes/statuses, CCLD return links, and record-specific
feedback handoff and checklist bridge cues, submit a bounded reviewer note, submit
a bounded reviewer status, see a saved-state confirmation with same-request
return-to-queue progress and next-record navigation guidance, and see
read-after-write reviewer-created state on the page. No-search-results,
missing-record, invalid-form, and permission-blocked states include clear
browser guidance and links back to useful local/test next steps. Narrative source fields are hidden in the browser shell.
Reviewer pages include skip-to-main links, CCLD workflow navigation, first-run
detail steps, source traceability review guidance before note/status actions,
record-specific note/status action text, record-specific feedback handoff cues,
same request-context return guidance, queue progress refresh wording, next-record
navigation wording, and confirmation guidance
while preserving the existing write and audit paths.

The UI is intentionally plain server-rendered HTML. It reuses the existing
source-derived route seam, reviewer workflow shell, reviewer-created state
write/read routes, and audit scaffold. UI actions do not mutate source-derived records; successful note/status writes create reviewer-created scaffold rows and
the existing audit scaffold row through the existing services.
Source-confidence cues are presentation-only. They do not add confidence scores,
automated source verification, parser behavior, extraction changes, schema
changes, persistence, queue assignment, workflow-engine behavior, or source-
completeness assertions.
Field-note guidance is also presentation-only. It does not generate notes, store
note templates, add note fields, edit source-derived records, or create source-
verification workflow behavior.
Feedback checklist bridge cues point to the existing manual checklist only. They
do not create a duplicate checklist, persist feedback, send feedback, export
feedback, or add a feedback workflow.
Queue-to-detail continuity cues use that same checklist for queue-level and
detail-level observations without adding a new checklist or workflow.

The UI does not implement production sign-in, real OpenID Connect login, auth
middleware, token validation, sessions, cookies, provider registration, client
secrets, hosted URLs, deployment, exports, reset/reload execution, live
crawling, connector execution, note/status editing or deletion, corrections,
tester feedback, audit UI/export, or a frontend build pipeline.

## Open the sample read-only source view shell

The scaffold includes a local-only sample source-derived view shell at:

```text
http://127.0.0.1:8000/source-records
```

The page displays fixture/sample records only. It does not load live public data,
does not read from a database, does not run import/sync, does not authenticate
users, and does not persist reviewer-created state. Its source-traceability-style
fields are sample values that exist only to exercise the future read-only
reviewer-app shape.

The list includes local sample filtering/search controls for the query text,
jurisdiction, and source family. These controls filter only the in-memory
fixture/sample records shown by the shell. They do not query live public-source
data, SQLite, a hosted database, an import process, or reviewer-created state.

The filter shape is intentionally source-family and jurisdiction aware so future
source-derived records from multiple jurisdictions and source families can be
presented through the same list/filter pattern after the relevant source,
import, schema, and hosted workflow decisions are approved. The current shell
still keeps the fixture/sample labels, read-only behavior, source-derived versus
reviewer-created state separation, semantic structure, accessibility validation,
and no-database, no-import, no-real-login, no-deployment boundary.
The source-derived versus reviewer-created state separation remains visible in
the sample shell text and tests.

The list also includes a fixture/sample-only source traceability summary panel.
It counts whether the current sample result set has visible sample source URL,
raw SHA-256, connector name, retrieval timestamp, report index, extraction
warning, jurisdiction, and source-family values. Detail pages include a matching
sample traceability block for the selected record. These panels are indicators
over in-memory fixture/sample records only. They do not verify live public-source
records, prove source completeness, read from SQLite or a hosted database, run
import/sync, or expose reviewer-created state.

The summary shape is intentionally jurisdiction and source-family aware so
future source-derived records from multiple jurisdictions and source families can
use the same list/filter/summary pattern after the relevant source, import,
schema, and hosted workflow decisions are approved.

## Open the sample facility master view

The scaffold also includes a local-only sample facility master view at:

```text
http://127.0.0.1:8000/facilities
```

The page displays read-only fixture/sample facility rows loaded only from the
committed tiny public-source facility fixtures under
`tests/fixtures/public_source_facilities/`. Detail pages are available from the
facility number links and show source-family, jurisdiction, profiled source
shape, source dataset reference, source URL placeholder, raw SHA-256 placeholder,
and retrieval-time placeholder metadata from the committed fixture manifest.
Facility detail pages also show fixture-only source coverage indicators and
related fixture/sample source-record context when the local sample mapping
connects a facility-master fixture row to a sample source record. Program-
specific fixture rows without that local mapping are labeled as not represented
in the fixture/sample mapping.

The facility sample view does not load live public-source data, read ignored raw
CSVs, read generated profiling outputs, read SQLite or a hosted database, run
import/sync, perform real provider login, persist reviewer-created state, or
prove source completeness, statewide coverage, official facility status, or
legal or facility-wide conclusions.

## PostgreSQL and Alembic seeded import wiring

The repository now includes minimal PostgreSQL/Alembic project wiring and a
controlled seeded corpus import path for hosted tester MVP persistence. The
wiring includes:

- `alembic.ini` with an empty committed database URL setting.
- `migrations/` as the Alembic script location.
- `migrations/versions/20260613_0001_seeded_corpus_import.py` with import batch
  metadata and source-derived record staging tables.
- `migrations/versions/20260614_0002_reviewer_created_state_scaffold.py` with
  one separate reviewer-created state scaffold table linked to staged
  source-derived record keys.
- `migrations/versions/20260614_0003_audit_event_scaffold.py` with one separate
  audit event scaffold table for successful reviewer-created state scaffold
  writes only.
- `migrations/versions/20260614_0004_reset_reload_operational_metadata.py` with
  one separate reset/reload operational planning metadata scaffold table for
  explicitly requested dry-run planning records only.
- `migrations/versions/20260615_0005_ccld_retrieval_jobs.py` with one separate
  controlled CCLD retrieval job operational metadata table.
- `ccld_complaints.hosted_app.persistence` for no-secret database URL validation
  and ADR-0010 persistence boundary descriptors.
- `ccld_complaints.hosted_app.auth` for managed OIDC/OAuth2 provider-class
  configuration validation, local/test actor context, role and scope guards, and
  protected source-derived read service helpers.
- `ccld_complaints.hosted_app.auth_provider_integration_plan` for local/test
  user-role-admin readiness planning over the accepted managed OIDC/OAuth2
  provider class, accepting only non-secret planning inputs and performing no
  persistence, provider registration, token handling, or network calls.
- `ccld_complaints.hosted_app.schema_api_scaffold` for scaffold-only source-
  derived and reviewer-created state API boundary descriptors.
- `ccld_complaints.hosted_app.seeded_import` for loading a controlled validated
  JSON artifact into the seeded import tables.
- `ccld_complaints.hosted_app.source_derived_reads` for local/test list and
  fetch access to staged source-derived records with import batch context.
- `ccld_complaints.hosted_app.source_derived_routes` for local/test
  authenticated JSON list, fetch-by-key, and fetch-by-stable-identity route
  handlers over staged source-derived records.
- `ccld_complaints.hosted_app.reviewer_workflow_shell` for a local/test
  authenticated review queue and detail shell over source-derived route
  responses, with read-only selected detail payloads able to compose associated
  reviewer-created state read route output and narrow note/status actions that
  delegate to existing reviewer-created write routes after resolving the
  selected source record.
- `ccld_complaints.hosted_app.reviewer_created_state` for local/test
  authenticated reviewer-created state scaffold writes and scoped reads without
  mutating staged source-derived records.
- `ccld_complaints.hosted_app.reviewer_created_state_routes` for local/test
  authenticated JSON list and fetch access over persisted reviewer-created
  scaffold rows without mutating staged source-derived, reviewer-created, audit,
  or operational metadata records.
- `ccld_complaints.hosted_app.audit_events` for local/test audit rows tied to
  successful reviewer-created state scaffold writes without mutating staged
  source-derived or reviewer-created records.
- `ccld_complaints.hosted_app.audit_coverage_plan` for local/test audit-read
  coverage planning over current and deferred audit categories without creating
  audit rows, persisting planning records, or mutating hosted scaffold tables.
- `ccld_complaints.hosted_app.audit_event_routes` for local/test authenticated
  JSON list and fetch access over those scaffold audit rows without mutating
  staged source-derived, reviewer-created, or audit records.
- `ccld_complaints.hosted_app.reset_reload_dry_run` for a local/test
  authenticated seeded corpus reset/reload dry-run route seam that reports
  future impact without mutating data and can optionally persist a non-secret
  planning metadata record when explicitly requested.
- `ccld_complaints.hosted_app.reset_reload_execution_plan` for a local/test
  authenticated seeded corpus reset/reload execution-plan route seam that turns
  dry-run summaries and planning metadata context into ordered bounded non-
  destructive action steps, with optional non-secret planning metadata
  persistence when explicitly requested.
- `ccld_complaints.hosted_app.reset_reload_planning_routes` for local/test
  authenticated JSON list and fetch access over persisted reset/reload planning
  metadata records without mutating data or executing reset/reload.
- `ccld_complaints.hosted_app.ccld_retrieval_jobs` for controlled server-side
  CCLD retrieval job validation, job state, raw artifact preservation, mocked-
  testable retrieval orchestration, and separated operational metadata.
- `ccld_complaints.cli.import_hosted_seeded_corpus` as a minimal local command
  wrapper for operator-initiated test imports.

The migration environment reads the database URL from
`CCLD_HOSTED_TESTER_DATABASE_URL` only when migrations are explicitly run. Do not
commit connection strings, usernames, passwords, provider settings, private
URLs, hosted URLs, tokens, or deployment-specific configuration.

The seeded import artifact format is intentionally narrow and fixture-backed.
It carries import batch metadata, validation status, raw hash validation status,
record counts, warnings, errors, and normalized source-derived records shaped
like validated pipeline output. The importer stages source-derived records with
stable identities, original source-derived values, source URL, raw SHA-256,
raw path when available, connector metadata, retrieval timestamp, and import
batch linkage.

The source-derived read service is intentionally small. It lists staged records
and fetches a single staged record by source record key or by entity type plus
stable source-derived identity. Read models include original values,
source-traceability fields, and import batch context. They do not include review
status, annotations, corrections, tester feedback, export packet state, audit
events, or other reviewer-created state.

The auth boundary scaffold is also intentionally small. It validates only the
accepted provider class value `managed-oidc-oauth2` through
`CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS`, defines local/test actor, role,
account-status, project/corpus scope, authorization target, and audit-context
models, and exposes guards for protected service seams. It rejects
unauthenticated actors, disabled or revoked actors, actors without the required
role permission, and actors outside the requested project or corpus scope. It
does not validate provider tokens, store sessions, create cookies, configure a
tenant, register an app, persist users or roles, or implement login/logout or
callback routes.

The source-derived HTTP/API route seam is intentionally small. It exposes
local/test JSON handlers for `/api/source-derived-records`,
`/api/source-derived-records/by-key`, and
`/api/source-derived-records/by-identity` only when the caller supplies an
explicit test route context with a database connection, authenticated actor or
unauthenticated test actor state, and seeded corpus scope. The handlers reuse
the protected read service, return source traceability and import batch context,
and reject unauthenticated, disabled or revoked, role-denied, out-of-scope,
invalid filter, invalid paging, and missing-record paths. They do not implement
production auth middleware, token parsing, cookies, sessions, reviewer-created
state, or a production API framework.

The reviewer workflow shell is intentionally small. It exposes local/test JSON
handlers for `/api/reviewer/source-derived-review/queue`,
`/api/reviewer/source-derived-review/detail`, and
`/api/reviewer/source-derived-review/detail/reviewer-note`, and
`/api/reviewer/source-derived-review/detail/reviewer-status` only when the caller
supplies an explicit workflow shell context backed by the source-derived route
context and the reviewer-created state route context. The shell consumes the
authenticated source-derived route seam, returns read-only queue and detail
payloads with source-derived record identity, original values, source
traceability, source document metadata, and import batch context, and can
compose associated reviewer-created state read route output plus a compact state
summary derived from that output for the selected source record on detail
responses. The note and status actions first resolve the selected source-derived
detail record, force the source-record binding from that resolved record, and
delegate to existing reviewer-created write routes and audit path. Source-
derived reads, associated reviewer-created state reads, note writes, and status
writes each enforce their own authenticated, active, role/scope-allowed access.
The shell does not create queue state, editable status transitions, full
annotations, corrections, tester feedback, export packet state, sessions,
cookies, production auth middleware, or a production API framework.

The reviewer-created state persistence scaffold is intentionally small. It can
create and read only local/test review-item-state scaffold rows after the caller
supplies an explicit database connection, authenticated actor context, and
seeded corpus scope. Writes require reviewer-state write permission, active
account status, matching scope, and an existing staged source-derived record key.
Rows are stored in a separate reviewer-created table with actor attribution and
do not overwrite source-derived records, original extracted values, raw source
metadata, import metadata, or source traceability. The scaffold does not
implement annotations, corrections, note/status editing/deletion, full review status workflows,
tester feedback, export packet decisions, sessions, cookies, production auth
middleware, or a production API framework. A narrow local/test reviewer note
creation route stores bounded non-secret note text as scaffold payload under the
existing state kind and reuses the existing write/audit path without changing the
schema. A narrow local/test reviewer status creation route stores bounded status
values as scaffold payload under the same state kind and reuses the same write/
audit path without changing the schema. Successful writes also create a separate local/test
audit event scaffold row with actor, permission, scope, action, target, and
source-derived context. If the audit row cannot be created, the reviewer-created
state write is rolled back.

The reviewer-created state read route seam is intentionally small. It exposes
local/test JSON handlers for `/api/reviewer-created-state` and
`/api/reviewer-created-state/by-id` only when the caller supplies an explicit
route context with a database connection, authenticated actor, and seeded corpus
scope. The handlers require reviewer-state read permission, support schema-
backed filters and bounded search over existing non-secret scaffold fields,
serialize non-secret scaffold fields, and reject
unauthenticated, disabled or revoked, role-denied, out-of-scope, invalid filter,
invalid paging, and missing-record paths. They do not create, update, delete,
execute, archive, clear, relink, reload, or otherwise mutate source-derived,
reviewer-created, audit, or operational metadata rows. Source-derived read
permission alone does not grant reviewer-created state read access.

The audit event persistence scaffold is intentionally small. It stores rows only
for successful reviewer-created state scaffold writes, using a separate audit
table linked to the reviewer-created scaffold target and source-derived context.
It does not store provider secrets, tokens, cookies, sessions, private headers,
connection strings, raw provider claims, or unnecessary sensitive narrative
content. The audit history route seam exposes local/test JSON handlers for
`/api/audit-events` and `/api/audit-events/by-id` only when the caller supplies
an explicit route context with a database connection, authenticated actor or
unauthenticated test actor state, and seeded corpus scope. The handlers require
audit-read permission, support schema-backed filters, serialize non-secret audit
fields, and reject unauthenticated, disabled or revoked, role-denied,
out-of-scope, invalid filter, invalid paging, and missing-event paths. They do
not mutate staged source-derived, reviewer-created, or audit rows. The scaffold
does not implement full audit policy coverage, production audit API framework,
audit UI, audit export, retention automation, or audit coverage for
reset/reload, exports, feedback, annotations, corrections, provider login, role
changes, or operational actions.

The reset/reload dry-run seam is intentionally small. It exposes the local/test
JSON handler `/api/operations/seeded-corpus-reset-reload/dry-run` only when the
caller supplies an explicit dry-run context with a database connection,
authenticated operator or admin-style actor, and seeded corpus scope. The
handler requires import/reload permission, reports existing import batch
metadata, source-derived record counts by entity, scoped reviewer-created
scaffold row counts, scoped audit scaffold row counts, future reviewer-created
state handling options, validation requirements, audit requirements, and deferred destructive actions. It performs
read-only inspection queries by default. When local/test code adds
`persist_planning_metadata=true`, it persists one separate operational planning
metadata record with actor attribution, permission used, scope, generated
timestamp, validation summary, impact summaries, and non-secret planning context.
The reset/reload execution-plan seam exposes the local/test JSON handler
`/api/operations/seeded-corpus-reset-reload/execution-plan` only when the caller
supplies an explicit local/test context with a database connection,
authenticated operator or admin-style actor, and seeded corpus scope. It reuses
the dry-run permission and scope checks, returns ordered bounded non-destructive
action steps, and can optionally persist an execution-plan artifact through the
same planning metadata table when local/test code adds
`persist_planning_metadata=true`.
The read-only planning metadata route seam exposes
`/api/operations/seeded-corpus-reset-reload/planning-metadata` and
`/api/operations/seeded-corpus-reset-reload/planning-metadata/by-id` only when
the caller supplies an explicit local/test context with a database connection,
authenticated operator or admin-style actor, and seeded corpus scope. The
handlers require import/reload permission, support schema-backed filters, return
non-secret planning metadata fields, and do not create, update, delete, execute,
archive, clear, relink, reload, schedule, or otherwise mutate data.
It does not delete, truncate, overwrite, archive, import, reload, create new
dry-run audit events, execute persisted metadata, run live crawling, execute
connectors, or implement a production API framework.

To run migrations or load a seeded corpus into a local PostgreSQL-compatible
test database, set `CCLD_HOSTED_TESTER_DATABASE_URL` outside the repository and
run Alembic before the import command:

```powershell
alembic upgrade head
```

```powershell
python -m ccld_complaints.cli.import_hosted_seeded_corpus tests\fixtures\hosted_seeded_corpus\validated_seeded_corpus.json
```

Do not commit connection strings, usernames, passwords, provider settings,
private URLs, hosted URLs, tokens, or deployment-specific configuration.

The current path implements only a local/test browser reviewer UI shell over the
tiny seeded fixture corpus and existing workflow seams. It does not implement
production reviewer views, real
provider login, token validation, sessions, cookies, auth middleware, user or
role persistence, full reviewer-created workflows, full audit coverage, audit UI,
audit export, export builders, reset/reload execution, reviewer-created state archive or clear behavior, production import
automation, production API framework behavior, hosted live crawling, hosted
connector execution, QNAP, Azure, AWS, public hosting, public URLs, or
production deployment. The QNAP-first Docker runtime provides a production-like
container and PostgreSQL envelope only; it does not change those application
feature boundaries.

## Run the smoke check

The smoke check starts an in-process local scaffold server, checks the health
route and placeholder app shell, then stops the server:

```powershell
.\scripts\smoke-hosted-scaffold.ps1
```

The health route is also available on a running scaffold at:

```text
http://127.0.0.1:8000/health
```

## Run scaffold tests

Run the focused scaffold tests:

```powershell
pytest tests/unit/test_hosted_app_scaffold.py
```

Run the focused hosted schema/API scaffold tests:

```powershell
pytest tests/unit/test_hosted_schema_api_scaffold.py tests/unit/test_hosted_app_local_check.py
```

Run the focused hosted seeded import tests:

```powershell
pytest tests/unit/test_hosted_seeded_corpus_import.py
```

Run the focused hosted source-derived read tests:

```powershell
pytest tests/unit/test_hosted_source_derived_reads.py
```

Run the focused hosted auth boundary tests:

```powershell
pytest tests/unit/test_hosted_auth_boundary.py
```

Run the focused hosted auth provider integration planning tests:

```powershell
pytest tests/unit/test_hosted_auth_provider_integration_plan.py
```

Run the focused hosted audit coverage planning tests:

```powershell
pytest tests/unit/test_hosted_audit_coverage_plan.py
```

Run the focused hosted source-derived API route tests:

```powershell
pytest tests/unit/test_hosted_source_derived_routes.py
```

Run the focused hosted reviewer workflow shell tests:

```powershell
pytest tests/unit/test_hosted_reviewer_workflow_shell.py
```

Run the focused hosted reviewer UI shell tests:

```powershell
pytest tests/unit/test_hosted_reviewer_ui.py
```

Run the focused hosted reset/reload dry-run tests:

```powershell
pytest tests/unit/test_hosted_reset_reload_dry_run.py
```

Run the focused hosted reset/reload execution-plan tests:

```powershell
pytest tests/unit/test_hosted_reset_reload_execution_plan.py
```

Run the focused hosted reset/reload operational metadata tests:

```powershell
pytest tests/unit/test_hosted_reset_reload_operational_metadata.py
```

Run the focused hosted reset/reload planning metadata route tests:

```powershell
pytest tests/unit/test_hosted_reset_reload_planning_routes.py
```

Run the focused hosted reviewer-created state scaffold tests:

```powershell
pytest tests/unit/test_hosted_reviewer_created_state.py
```

Run the focused hosted reviewer-created state route tests:

```powershell
pytest tests/unit/test_hosted_reviewer_created_state_routes.py
```

Run the focused hosted audit event scaffold tests:

```powershell
pytest tests/unit/test_hosted_audit_events.py
```

Run the focused hosted audit history route tests:

```powershell
pytest tests/unit/test_hosted_audit_event_routes.py
```

These tests include local-only semantic/accessibility validation for the sample
source view shell and facility master sample view. They use Python standard-library HTML parsing
to verify one page-level heading, meaningful page titles, semantic main content,
navigation links, fixture/sample caution text, read-only labels, accessible
filter labels, sample no-match behavior, source traceability summary panels,
source-derived versus reviewer-created state separation, visible
source-traceability-style fields, manifest-backed facility fixture metadata,
fixture-only source coverage indicators, and related fixture/sample source
context links.
The schema/API scaffold tests verify safe database configuration validation,
redacted connection summaries, required ADR-0010 persistence boundaries, source-
derived versus reviewer-created state API separation, and that the only enabled
domain behavior is the controlled seeded source-derived import path.
The seeded import tests verify the tiny validated artifact shape, import batch
identity, source traceability preservation, stable source-derived identity,
idempotent staging, and no reviewer-created state writes.
The source-derived read tests verify database-backed list and fetch behavior,
import batch context, source traceability preservation, stable identity lookup,
and no reviewer-created state exposure.
The auth boundary tests verify safe provider-class configuration validation,
authenticated actor context, audit-ready authorization decisions, protected
source-derived read helpers, disabled-account rejection, role-denied rejection,
out-of-scope rejection, and that source-derived read access alone does not imply
reviewer-created state read, reviewer-created state write, import/reload, or
user-administration permissions.
The auth provider integration planning tests verify accepted provider-class
planning, unsupported provider-class rejection, required non-secret readiness
inputs, secret-like input and real URL rejection without echoing values,
user-role-admin permission and scope checks, deterministic plan ordering, no
persistence, and before/after row counts proving existing hosted scaffold tables
are not mutated.
The audit coverage planning tests verify local/test audit-read planning over
current and deferred audit categories, unauthenticated, disabled or revoked,
role-denied, and out-of-scope rejections, deterministic ordering, non-secret
payloads, no audit row creation, no persistence, and before/after row counts
proving existing hosted scaffold tables are not mutated.
The source-derived API route tests verify local/test JSON list and fetch
handlers, source traceability and import batch serialization, entity filtering,
paging, missing-record responses, explicit route-context requirements, and
unauthenticated, disabled or revoked, role-denied, and out-of-scope rejections.
The reviewer workflow shell tests verify local/test authenticated queue and
detail payloads over the source-derived route seam, associated reviewer-created
state read route output for selected detail responses, derived associated-state
summary fields for empty, one-row, and multiple-row states, associated-state
filter/search pass-through, empty associated state, empty queue behavior,
missing-detail behavior, explicit workflow context requirements, source
traceability preservation, import batch context, source-derived read versus
reviewer-state read permission separation, non-secret associated state payloads,
and unauthenticated, disabled or revoked, role-denied, out-of-scope, and
read no-mutation behavior. They also verify reviewer note creation through the
workflow shell action, forced source-record binding from the selected detail
context, invalid source or note payload rejection, audit creation on success,
no audit/state mutation on failure, read-after-write visibility, and no source-
derived mutation.
The reviewer UI shell tests verify local/test browser-accessible landing and
detail HTML pages over the seeded fixture corpus, list-level reviewer-created
state indicators, safe source traceability display, safe related seeded bundle
context with narrative fields hidden, semantic form controls, note/status form
delegation to the existing workflow actions, read-after-write reviewer-created state display, clear no-match, missing-record, invalid-form, and blocked-request guidance,
unauthenticated, disabled or revoked, role-denied, out-of-scope, and permission-
separation blocking, no-secret HTML output, successful audit creation, and no
source-derived mutation from UI actions.
The reviewer-created state scaffold tests verify separate storage from staged
source-derived records, source-derived records are not modified, authenticated
actor attribution is captured, reviewer-state write permission is required,
disabled or revoked, role-denied, out-of-scope, and invalid source-derived
reference writes are rejected, and scoped readback works where implemented.
The reviewer-created state route tests verify local/test authenticated list and
fetch handlers over persisted scaffold rows, schema-backed filters, bounded
search success and empty search results, empty list, missing-record responses,
explicit route-context requirements, unauthenticated, disabled or revoked,
role-denied, and out-of-scope rejections, source-derived read permission
separation, note creation with reviewer-state write permission, invalid note
payload and missing source rejection, read-after-write visibility, successful
note audit event creation, non-secret JSON payloads, and before/after row counts
proving reads do not mutate seeded import, reviewer-created scaffold, audit
scaffold, or operational planning metadata tables.
The audit event scaffold tests verify that successful reviewer-created state
scaffold writes, including reviewer note writes, create separate audit rows with
actor attribution and target context, failed writes do not create successful audit rows, audit persistence
failure rolls back the reviewer-created state write, source-derived rows remain
unchanged, reviewer-created rows are not modified by audit persistence, audit
read permission is required, and secret-like values are not stored in audit
context metadata.
The audit history route tests verify local/test authenticated list and fetch
handlers over scaffold audit rows, schema-backed filters, empty history,
missing-event responses, explicit route-context requirements, unauthenticated,
disabled or revoked, role-denied, and out-of-scope rejections, non-secret JSON
payloads, and before/after row counts proving reads do not mutate seeded import,
reviewer-created scaffold, or audit scaffold tables.
The reset/reload dry-run tests verify local/test authenticated planning payloads,
seeded import batch, source-derived record, reviewer-created scaffold, and audit
scaffold impact counts, reviewer-created state handling options, invalid mode rejection,
explicit dry-run context requirements, unauthenticated, disabled or revoked,
role-denied, and out-of-scope rejections, and before/after row counts proving
the dry-run does not mutate seeded import, reviewer-created scaffold, or audit
scaffold tables.
The reset/reload operational metadata tests verify explicitly requested planning
metadata persistence, scoped readback, non-secret planning context, invalid
option rejection, unauthenticated, disabled or revoked, role-denied, and out-of-
scope rejection, and before/after row counts proving persisted planning metadata
does not mutate seeded import, reviewer-created scaffold, or audit scaffold
tables or execute reset/reload.
The reset/reload execution-plan tests verify authenticated success,
unauthenticated, disabled or revoked, role-denied, and out-of-scope rejections,
invalid requested mode and reviewer-state handling option rejection, default
non-persistence, optional planning metadata persistence, deterministic action-
plan ordering, and before/after row counts proving execution-plan creation does
not mutate seeded import, source-derived, reviewer-created, audit, or
operational metadata tables except for the explicitly requested planning
metadata row.
The reset/reload planning metadata route tests verify local/test authenticated
list and fetch handlers over persisted planning rows, schema-backed filters,
empty history, missing-record responses, explicit route-context requirements,
unauthenticated, disabled or revoked, role-denied, and out-of-scope rejections,
non-secret JSON payloads, and before/after row counts proving reads do not
mutate seeded import, reviewer-created scaffold, audit scaffold, or operational
planning metadata tables.
They do not require browser automation, Node.js, Playwright, Selenium, axe,
Docker, a running PostgreSQL server, cloud services, or public URLs.

Run the standard project validation before opening a PR:

```powershell
.\scripts\check-hosted-scaffold-local.ps1
```

```powershell
.\scripts\lint.ps1
```

```powershell
.\scripts\test.ps1
```

```powershell
.\scripts\docs.ps1
```

```powershell
git diff --check
```

## Intentionally not implemented

The scaffold intentionally does not implement:

- Real authentication.
- Real provider token validation, sessions, cookies, or auth middleware.
- Real provider registration, callback handling, hosted URLs, or persisted auth
  configuration.
- Persistent authorization, user, role, invitation, or scope storage.
- Production schema beyond the seeded import table group, the narrow
  reviewer-created state scaffold table, the narrow audit event scaffold table,
  and the narrow reset/reload planning metadata scaffold table.
- Full reviewer-created workflow, full audit coverage, audit UI, audit export,
  export, feedback, auth, or
  reset/reload execution tables beyond the narrow planning metadata scaffold.
- HTTP API routes outside the narrow local/test source-derived read route seam,
  reviewer workflow shell queue/detail/note-action seam, reviewer-created state
  read route seam, reset/reload dry-run seam, reset/reload execution-plan seam,
  audit history read route seam, and reset/reload planning metadata read route seam.
- Production reviewer views or full reviewer workflows beyond the local/test
  browser UI shell over the tiny seeded fixture corpus.
- Production import/sync automation.
- Queues.
- Annotations.
- Corrections.
- Exports.
- Tester feedback.
- Audit trail beyond successful reviewer-created state scaffold writes.
- Reset/reload execution.
- Hosted live crawling.
- Hosted connector execution.
- Full reviewer-created state workflow persistence.
- Source-derived canonical field changes.
- Extraction behavior changes.
- QNAP, Azure, AWS, public hosting, public URLs, or production deployment.

The sample source-derived view shell is also local-only and read-only. It is not
an import workflow, a database-backed source record route, a queue, a correction
workflow, or a reviewer-created state surface. Database-backed source-derived
reads are limited to the local/test service seam over staged seeded corpus
records.

The sample facility master view is also local-only and read-only. It is not a
CSV import, source connector, database-backed facility search, official facility
master, reviewer queue, correction workflow, or reviewer-created state surface.
Its source coverage panel is a fixture-only display pattern, not evidence of
live public-source coverage, source completeness, import status, or legal or
facility-wide conclusions.

Those layers remain deferred to later ADRs or implementation PRs with focused
validation for the affected boundary.

## Tooling impact

The hosted app shell still uses Python standard-library HTTP server primitives.
The PostgreSQL/Alembic wiring follows ADR-0015 for the hosted tester persistence
target and migration tool direction, but it is only scaffold wiring for local
and test validation. It is not a final production frontend framework, API
framework, concrete auth provider instance, hosting platform, deployment
pipeline, cloud database plan, backup policy, or retention automation decision.