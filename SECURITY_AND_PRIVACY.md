# Security and Privacy

## Principles

- Use public data only unless explicitly approved.
- Do not store secrets in source control.
- Do not log credentials, cookies, tokens, or private headers.
- Do not scrape private or authenticated systems.
- Respect source terms, robots directives, rate limits, and applicable law.
- Preserve source traceability and disclaimers.

## Source handling

The initial source is a public portal. Before expanding to new sources, document:

- Source URL
- Terms/conditions reviewed
- Access method
- Rate limiting approach
- Data sensitivity concerns
- Retention approach

The Issue #518 ArcGIS connector is limited to the approved public CDSS CCL
Facilities catalog/item/service/layer and exact query identities. It sends
unauthenticated GET requests without caller-supplied URLs, query expressions,
credentials, cookies, authorization headers, user information, or fragments.
It rejects redirects, unapproved parameters, export/replica/cache/Azure paths,
signed or opaque queries, incomplete pagination, and non-reconciling ObjectIds.
Original public responses remain under the Git-ignored
`data/raw/source-profiling/issue-518-live-query/` retention boundary. Tracked
evidence may include only sanitized public identities, aggregate counts,
fingerprints, hashes, and limitations—not live facility rows or bulk response
bodies. The connector has no retry, production activation, canonical/reviewer
write, scheduler, operator mutation, deployment, QNAP, Cloudflare, or Hosted
acceptance path.

## Secrets

Local secrets must use environment variables or untracked `.env` files. `.env` is ignored by Git.

The QNAP-first Docker Compose runtime uses `.env.example` only for placeholders.
Deployment hosts must keep real PostgreSQL passwords in an untracked `.env` file
or host-managed secret store. Database URLs, passwords, tokens, provider
configuration, private URLs, and cloud credentials must not be committed,
rendered into HTML or browser JavaScript, logged, or copied into tests or docs.
QNAP-specific host paths and backup locations should stay in host-local
configuration or operator notes, not application code.

The QNAP pilot workflow checker reads an untracked env file and runs local
validation commands. It must not print secret values, commit env files, create
tokens, or replace host-managed secret storage. Treat warnings about placeholder
values as deployment readiness prompts, not as permission to commit real values.

## Agent capability and tool boundaries

Repository capabilities are maximum grants, not a way to create tools or
access. An agent may use RO, II, HV-READ, HV-WORKFLOW, RL-PREPARE, or RL-MERGE
only when the current task grants it and the active environment supports the
required tool. Stop and report an unavailable capability or tool instead of
substituting another mechanism. Capabilities expire at the task's exact stop
point and never carry into another task or conversation.

HV-READ is limited to approved read-only GET/navigation, responsive, keyboard,
accessibility, print, screenshot, and evidence activity on the task's browser
and network allowlists. HV-WORKFLOW is limited to the task's exact named
ordinary-user mutations, designated account, routes, maximum scope, cleanup or
state disposition, evidence, and stop point. Neither permits operator actions,
infrastructure or authentication administration, QNAP access, database
administration, Cloudflare, credential inspection, or destructive actions.

RL-PREPARE is limited to the assigned branch, worktree, and one PR and does not
include merge or cleanup. RL-MERGE requires separate current-task user
authorization plus successful required checks, no merge blockers, and completed
review and evidence gates. Neither capability permits reading or displaying
tokens, cookies, credentials, private repository settings, or other secrets.

HQ is permanently human-only. Agents may locally verify a release SHA, prepare
and inspect a clean archive, calculate its hash, generate transfer and QNAP
command text from the authoritative runbook, prepare hosted-acceptance
checklists, and interpret safe operator-pasted output. Agents may never invoke
SSH through PowerShell, Git Bash, WSL, Python, libraries, MCP, browser terminals,
or another indirect mechanism; run remote shell or QNAP Docker/Compose; inspect
or modify QNAP `.env`; connect to QNAP PostgreSQL; transfer or deploy; roll back;
restore PostgreSQL; or administer Cloudflare. The user performs archive transfer
and every QNAP command through the approved local transfer workflow and
standalone SSH client.

## Hosted tester access

Hosted tester MVP access must be authenticated and limited to explicitly
invited or provisioned testers, operators, and administrators. Anonymous hosted
tester access is not allowed because the hosted workflow includes
reviewer-created state, tester feedback, annotations, proposed corrections,
export decisions, audit history, and potentially sensitive review context.

ADR-0014 selects a managed standards-based OpenID Connect/OAuth 2.0 identity
provider class for the hosted tester MVP. The project must not build custom
password storage for the tester MVP. Provider secrets, client credentials,
tenant IDs, app registrations, callback URLs, hosted URLs, private URLs, tokens,
and account-specific configuration must not be committed.

The current hosted auth boundary scaffold validates only the accepted managed
OIDC/OAuth2 or Cloudflare Access provider class through
`CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS` and models authenticated actor identity,
account status, role assignments,
project/corpus scopes, authorization targets, and audit-ready actor context for
local/test use. The current runtime auth boundary also reads
`CCLD_HOSTED_TESTER_AUTH_MODE`, `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH`,
`CCLD_HOSTED_TESTER_OIDC_ISSUER`, `CCLD_HOSTED_TESTER_OIDC_CLIENT_ID`,
`CCLD_HOSTED_TESTER_OIDC_CALLBACK_PATH`, and
`CCLD_HOSTED_TESTER_OIDC_SCOPES` as provider-agnostic environment configuration
placeholders. Production mode is the default and blocks anonymous workflow pages
and actions when no authenticated route context exists. Explicit local-dev mode
can supply the fixture tester actor for local scaffold validation only. A narrow local/test auth provider integration planning seam can
validate the accepted provider class, require user-role-admin planning access,
accept only non-secret readiness inputs, and return bounded provider readiness
steps without persistence. It does not implement provider login, token
validation, session storage, cookies, callback handling, provider registration,
hosted URLs, user tables, role tables, provider tenant configuration, client
secrets, or production auth middleware. The browser may display only a safe
tester label when available; it must not render provider subjects, issuers, raw
claims, tokens, cookies, private headers, or secrets. Protected service helpers must reject
unauthenticated, disabled or revoked, role-denied, and out-of-scope actors
before future reviewer-created workflows are enabled.

For the QNAP pilot feedback path, `cloudflare-access` is a narrow bridge rather
than an app login system. Cloudflare Access protects the public hostname, and
RecordsTracker validates only the `Cf-Access-Jwt-Assertion` header using the
configured team-domain JWKS, issuer, AUD tag, expiration/not-before, and
configured email allowlists before creating a minimal feedback actor. The app
must not trust cookies, query string tokens, arbitrary email headers, or
caller-provided actor fields for that bridge. It must not render raw JWTs, raw
claims, provider subjects or issuers, real team domains, AUD tags, tester
allowlists, cookies, GitHub tokens, private URLs, tunnel tokens, or other
secrets in HTML, JSON, logs, tests, docs, screenshots, or GitHub issue bodies.
The bridge does not add app passwords, sessions, user tables, migrations, or a
full OIDC login UI.

The current page-data seam defaults production-style runtime to
`CCLD_HOSTED_PAGE_DATA_MODE=postgres`. PostgreSQL-backed pages must use the
hosted source-derived/import/reviewer-created service contexts and show
setup-required guidance when data is unavailable. Fixture/demo reads are allowed
only through explicit local/demo configuration. Pages must not silently expose
fixtures as production data, expose raw narrative source text, mutate
source-derived records through review actions, or run live retrieval or connector
execution.

The current ADR-0016 retrieval seam implements the first controlled browser-
triggered, server-executed CCLD retrieval job slice. The browser may submit only a CCLD facility/license
number, allowed record type or all supported record types, and bounded start/end
dates. The browser must not scrape, crawl, fetch source pages, receive connector
credentials, receive GitHub tokens, receive provider tokens, receive cookies, or
receive server-side secrets. Server-side retrieval must require authenticated
tester access before production use, require a retrieval permission and matching
project/corpus scope, validate facility/date/type inputs, use a CCLD source
domain and URL-pattern allowlist, enforce date-range maximums, record-type
allowlists, per-job request limits, per-user or per-actor rate limits, timeout
limits, retry limits, and safe job states. It must preserve raw CCLD source
artifacts in configured server-side storage before extraction, compute raw
SHA-256 hashes, deterministically extract/normalize, validate before PostgreSQL
import, and expose only safe status, counts, warnings, and queue links to
testers. It must not expose raw stack traces, tokens, cookies, private headers,
connection strings, provider claims, GitHub tokens, private URLs, server-specific
absolute paths, or unnecessary narrative content in HTML, JSON, logs, audit/
status events, tests, screenshots, issue bodies, or docs.

Controlled retrieval remains CCLD-only and currently supports complaint records
only; all supported record types resolves to complaint records. Statewide
crawling, automatic source expansion, non-CCLD sources, private or authenticated
source scraping, and direct browser crawling remain prohibited. Retrieval job
metadata is operational metadata and remains separate from source-derived
records, reviewer-created state, audit events, and feedback issues.

The command-based batch complaint retrieval loader is an operator path over the
same controlled retrieval/import seam. It must default to dry-run, require an
explicit apply flag before mutations, select facilities from preloaded public
facility reference rows, split date ranges into bounded windows, write ignored
JSONL manifests under processed output, and skip already-loaded windows unless
forced. Console output and manifests may include safe facility/date context,
retrieval job IDs, counts, warnings, and safe artifact identities, but must not
include database URLs, connection strings, tokens, cookies, private host values,
raw artifact contents, raw server paths, stack traces, private URLs, or secrets.

`CCLD_RETRIEVAL_DEMO_MODE=mock-success` is allowed only for explicit local-dev
scaffold validation when local-dev auth is enabled and retrieval raw storage is
configured. It uses committed fixtures through a fixture-backed retrieval client,
does not make live CCLD calls, does not call GitHub, and must not be honored for
anonymous production, QNAP/pilot-like runtime, or any future public deployment.
The demo path may create local operational retrieval metadata and local source-
derived rows through the existing import path, but it must not expose raw
artifact contents, raw server paths, provider values, tokens, cookies, private
headers, connection strings, stack traces, or source completeness claims.

The retrieval job history and detail pages at `/ccld/retrieval/jobs` and
`/ccld/retrieval/jobs/detail?job_id=` are read-only status surfaces over that
existing operational metadata. They must require the same authenticated local/
test or production workflow access as the CCLD request flow, show only safe
request context, job state, timestamps, result counts, warning or error
summaries, status messages, raw-artifact-preserved indicators, and review links
when records were imported. They must not expose provider subjects or issuers,
raw provider claims, tokens, cookies, private headers, connection strings,
client secrets, raw stack traces, raw source narrative content, raw artifact file
contents, or server-specific absolute paths.

The current tester feedback seam can create GitHub Issues server-side only when
`GITHUB_FEEDBACK_REPO` and `GITHUB_FEEDBACK_TOKEN` are configured on the host.
The token must never be rendered into HTML, JavaScript, logs, tests, issue
bodies, screenshots, or documentation. Feedback issue bodies may include only
safe context such as feedback type, description, safe page path, timestamp, app
version when configured, safe actor display label, workflow area,
facility/license number, date range, complaint/control number, retrieval job ID,
visible workflow state, and action attempted. They must not include tokens,
cookies, raw provider claims, provider subject or issuer values, private
headers, connection strings, raw source narrative text, hosted/private URLs, or
secrets. GitHub Projects and GitHub issue types are not required; labels are the
reliable classification mechanism.

The current source-derived HTTP/API read route seam is local/test only and must
receive an explicit fixture or test actor context from the caller. It reuses the
auth boundary to reject unauthenticated, disabled or revoked, role-denied, and
out-of-scope reads before serializing staged source-derived records. It does not
parse or store provider tokens, create sessions or cookies, add production auth
middleware, persist audit events, expose reviewer-created state, or commit
provider, tenant, callback, hosted URL, or secret configuration.

The current reviewer workflow shell is also local/test only and must receive an
explicit workflow shell context backed by source-derived and reviewer-created
state read route contexts. It consumes the authenticated source-derived route
seam for read-only queue and detail payloads, and the detail payload can compose
associated reviewer-created state read route output for the selected source
record plus a compact summary derived only from that route output.
It can also create a bounded non-secret reviewer note and a bounded reviewer
status value through narrow local/test workflow-shell actions that first resolve
the selected source-derived detail context, then delegate to existing reviewer-
created write routes and the audit path using that resolved source record key.
Source-derived record reads still require source-derived read access,
and associated reviewer-created state reads separately require reviewer-state
read access; source-derived read permission alone does not grant the associated
state context, and reviewer note or status creation separately requires
reviewer-state write access. The shell preserves unauthenticated, disabled or revoked,
role-denied, and out-of-scope rejection behavior. It does not authenticate
browser users, parse or store provider tokens, create sessions or cookies, add
production auth middleware, create anonymous reviewer-created state, trust
conflicting caller-provided source record bindings, persist new audit events
through reads, or commit provider, tenant, callback, hosted URL, or secret
configuration.
The associated state summary must remain non-secret and limited to fields
already exposed by the reviewer-created state read route output.

The current browser-accessible reviewer UI shell is local/test only and runs at
`/reviewer` when the local scaffold process is started. It supplies a fixture
local/test actor context from the scaffold process, loads only the tiny seeded
fixture corpus into process-local test state, and delegates reads, note writes,
status writes, reviewer-created state readback, and audit creation to the
existing workflow, reviewer-created state, source-derived, and audit seams. The
HTML output is limited to safe source traceability fields, safe scalar source-
derived values, safe related seeded bundle context, reviewer-created note/status
indicator/display values, non-secret actor display labels, record-summary,
navigation, feedback-guidance, and local/test boundary text. The reviewer detail
page may show a concise source narrative excerpt and keeps longer loaded
narrative behind disclosure. It must not expose provider
subjects or issuers, email addresses, tokens, cookies, private headers,
connection strings, client secrets, raw provider claims, hosted URLs, private
URLs, or unnecessary sensitive narrative content. It does not implement real
login, sessions, cookies, token validation, auth middleware, anonymous writes,
exports, reset/reload execution, hosted live crawling, connector execution,
deployment, or public launch behavior.
Reviewer note/status confirmations may state that reviewer-created state was
saved, show non-secret read-after-write reviewer-created state, and link back to
the CCLD request queue. They must not expose raw provider claims, credentials,
private values, or unnecessary sensitive narrative content.
The local/test complaint review matrix CSV route may expose only safe source-
derived complaint fields, safe source URL/source-traceability cues, request
context, and clearly separated reviewer-created status/note presence metadata
already available through existing read seams. It must not expose raw narrative
source text, raw server paths, provider claims, tokens, cookies, private headers,
connection strings, client secrets, hosted URLs, private URLs, environment values,
or credentials, and it must not create a final legal packet/export workflow.

The current browser-accessible CCLD record request page is local/test only and
runs at `/ccld/records/request` when the local scaffold process is started. It
accepts only a digit CCLD facility/license number and optional date range, reads
existing seeded source-derived rows through the same local/test route seams, and
can load or refresh matching records from local validated hosted seeded-corpus
output through the existing source-derived import path, and links matching
seeded complaint rows into the reviewer UI. The page can also render first-time
workflow help, feedback guidance without persistence, a structured copyable
feedback checklist that testers must paste into an external channel manually,
and a guided request result queue over safe CCLD complaint context with progress
counts, reviewer note/status cues, source-traceability availability cues,
suggested next-record links, filtered-empty guidance, and status filters derived
from existing reviewer-created state. It can include skip-to-main links, visible
first-run next-step guidance, specific form/action text, and manual feedback-copy
instructions. Its HTML output must
remain limited to safe scalar source-derived context, source traceability-style
identifiers, reviewer-state indicators, queue counts, local/test boundary text,
local validated load counts, non-persistent checklist prompts, and the explicit
external live-fetch command shape. It
must not expose narrative source text, provider
claims, email addresses, tokens, cookies, private headers, connection strings,
client secrets, hosted URLs, private URLs, or credentials. It does not run live
crawling, execute connectors, write reviewer-created state from the request
page, create audit events from the request page, persist operational metadata,
persist feedback, implement auth middleware, or support non-CCLD sources.

The current browser-accessible CCLD facility lookup page is local/test only and
runs at `/ccld/facilities` when the local scaffold process is started. It can
read a configured full local/test CCLD program facility reference CSV, or fall
back to the committed tiny fixture when the full CSV is not configured,
unavailable, or malformed. It searches safe scalar fields such as
facility/license number, facility name, city, county, ZIP code, facility type,
and status, displays which reference source is active, and carries a selected
facility/license number into the request page. It must not expose unnecessary
address, telephone, administrator, licensee, complaint-summary, private, token,
cookie, provider, connection, hosted URL, or secret-like fields. It does not run
live crawling, execute connectors, query external services, write source-derived
records, write reviewer-created state, create audit events, persist lookup data,
persist operational metadata, implement auth middleware, or support non-CCLD
sources. Raw/full facility CSV files must remain outside the repository.

The local/test CCLD hosted artifact builder runs only as an explicit developer
command or function outside browser requests. It converts already validated CCLD
SQLite output into hosted seeded-corpus JSON, rejects missing required
traceability, rejects private or absolute raw paths, and writes no secrets,
tokens, cookies, private headers, provider claims, hosted URLs, private URLs,
connection strings, client secrets, or credentials. It does not run live public
web requests, execute connectors from the browser, mutate reviewer-created
state, create audit events, persist operational metadata, implement auth
middleware, or support non-CCLD sources.

The current reset/reload dry-run seam is local/test only and must receive an
explicit database, actor, and corpus scope context from tests or local callers.
It reuses the auth boundary to require import/reload permission, reject
unauthenticated, disabled or revoked, role-denied, and out-of-scope actors, and
report what a future seeded corpus reset/reload would affect. It performs
read-only inspection queries only, including a scoped count of the narrow
reviewer-created state scaffold table and audit event scaffold table when
present. When local/test code explicitly requests persistence, it can store a
separate operational planning metadata record with non-secret actor attribution,
permission used, scope, generated timestamp, validation summary, impact summary,
and planning context. That metadata path rejects unauthenticated, disabled or
revoked, role-denied, and out-of-scope actors, and rejects secret-like planning
context. It does not delete, truncate, overwrite, archive, import, reload,
create new dry-run audit events, parse or store provider tokens, create sessions
or cookies, add production auth middleware, store connection strings, or commit
provider, tenant, callback, hosted URL, or secret configuration.

The current reset/reload execution-plan seam is local/test only and must receive
an explicit database, actor, and corpus scope context from tests or local
callers. It reuses the dry-run permission and scope checks, summarizes existing
seeded import, source-derived, reviewer-created, audit, and planning metadata
context, and returns ordered bounded non-destructive action steps. When local/
test code explicitly requests persistence, it stores only a non-secret
operational planning metadata record that identifies the artifact as an
execution plan and records that no reset/reload data mutation was performed. It
does not execute reset/reload, archive, clear, relink, reload, run live
crawling, execute connectors, create audit events, parse or store provider
tokens, create sessions or cookies, add production auth middleware, store
connection strings, or commit provider, tenant, callback, hosted URL, or secret
configuration.

The current reset/reload planning metadata read route seam is local/test only
and must receive an explicit database, actor, and corpus scope context from
tests or local callers. It requires import/reload permission, rejects
unauthenticated, disabled or revoked, role-denied, and out-of-scope actors, and
serializes only non-secret persisted planning fields. It does not create,
modify, delete, execute, archive, clear, relink, reload, or schedule
reset/reload work, and it does not expose tokens, cookies, private headers,
connection strings, raw provider claims, or unnecessary sensitive narrative
content.

The current reviewer-created state persistence scaffold is local/test only. It
requires an explicit authenticated actor context, reviewer-state write
permission, active account status, and matching project or corpus scope before
it writes a scaffold row. Rows are stored separately from staged source-derived
records, reference source-derived records by staged stable record key, and
capture provider subject, provider issuer, display label, actor category, write
permission, and generated timestamp for attribution. The scaffold does not
store provider secrets, tokens, cookies, sessions, private headers, production
roles, or user tables, and it does not implement real login flow, auth
middleware, annotations, corrections, note or status editing or deletion, export decisions,
tester feedback, or stateful reviewer workflows. The local/test reviewer note
creation route stores only bounded non-secret note text as reviewer-created
scaffold payload and rejects secret-like note text. The local/test reviewer
status creation route stores only bounded status values as reviewer-created
scaffold payload. Successful scaffold writes also create a narrow
local/test audit event row in a separate table; if that audit row cannot be
created, the reviewer-created scaffold write is rolled back rather than silently
leaving unaudited reviewer-created state.

The current reviewer-created state read route seam is local/test only and must
receive an explicit database, actor, and scope context from tests or local
callers. It requires authenticated, active, reviewer-state-read-permitted, role
and scope-allowed access before listing or fetching persisted scaffold rows.
Read access to source-derived records alone does not grant reviewer-created
state read access. The route supports only schema-backed filters and bounded
search over existing non-secret scaffold fields already represented in the read
payload. It serializes only non-secret scaffold fields and does not create,
modify, delete, or execute reviewer-created state, source-derived records, audit
rows, or operational metadata. It does not expose tokens, cookies, private
headers, connection strings, raw provider claims, or unnecessary sensitive
narrative content.

The current audit event persistence scaffold is local/test only and covers
successful reviewer-created state scaffold writes only. It captures provider
subject and issuer, display label when available, actor category, permission
used, project or corpus scope, action, reviewer-created target ID,
source-derived target key and stable identity, source document ID, generated
timestamp, and concise non-secret metadata. It must not store provider secrets,
tokens, cookies, sessions, private headers, connection strings, raw provider
claims, or unnecessary sensitive narrative content. It does not implement full
audit policy coverage, audit UI, audit export, retention automation,
production auth middleware, real login flow, or audit coverage for reset/reload,
exports, feedback, annotations, corrections, provider login, role changes, or
operational actions. The current audit history read route seam is also
local/test only, must receive an explicit database, actor, and scope context,
requires audit-read permission, rejects unauthenticated, disabled or revoked,
role-denied, and out-of-scope actors, and serializes only non-secret audit row
fields for the narrow scaffold table without creating, modifying, or deleting
audit events, source-derived records, or reviewer-created rows.

The current audit coverage planning seam is local/test only, must receive an
explicit database, actor, and scope context, requires audit-read permission,
and returns non-secret current/deferred audit coverage planning output without
creating audit events, persisting planning records, mutating hosted scaffold
tables, exposing raw provider claims, storing credentials, or implementing audit
UI, audit export, production auth, provider login, reset/reload execution,
export generation, retention automation, hosted URLs, or deployment.

Identity storage, sessions, authorization middleware, user tables, role tables,
invitation flow, account recovery, final multi-factor requirements, and user
deprovisioning implementation remain deferred to later implementation
decisions. Future implementation must enforce role, permission, and
project/corpus scope before reviewer-created state is enabled and must preserve
audit identity context without logging credentials, cookies, tokens, private
headers, or unnecessary sensitive narrative content.

ADR-0015 chooses PostgreSQL and Alembic-managed migrations for hosted tester MVP
persistence. Future database implementation must not store provider secrets,
tokens, cookies, private headers, connection strings, or unnecessary sensitive
narrative content. Reviewer-created state, audit events, feedback, export packet
state, and role/scope assignments must remain separated from source-derived
records and must be scoped to authenticated actors or approved system identities
where applicable.

## Public repository hygiene

Public repository content must not include personal paths, account details, secrets, tokens, private URLs, local machine names, personal handles, personal email addresses, or other machine-specific identifiers. Use neutral placeholders such as `<repo-root>`, `<local-project-path>`, `<your-github-org-or-user>`, and `<repository-name>` in examples.

## Logging

Logs must not include secrets or unnecessary personal information. Logs should include source URL, document ID, connector name, and error details.

## Data sensitivity

Even public complaint data may include sensitive narrative content. Treat raw files and exports carefully. Avoid unnecessary redistribution of raw narrative text unless needed for the project purpose.
