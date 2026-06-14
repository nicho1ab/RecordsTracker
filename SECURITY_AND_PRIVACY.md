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

## Secrets

Local secrets must use environment variables or untracked `.env` files. `.env` is ignored by Git.

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
OIDC/OAuth2 provider class through `CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS` and
models authenticated actor identity, account status, role assignments,
project/corpus scopes, authorization targets, and audit-ready actor context for
local/test use. A narrow local/test auth provider integration planning seam can
validate the accepted provider class, require user-role-admin planning access,
accept only non-secret readiness inputs, and return bounded provider readiness
steps without persistence. It does not implement provider login, token
validation, session storage, cookies, callback handling, provider registration,
hosted URLs, user tables, role tables, provider tenant configuration, client
secrets, or production auth middleware. Protected service helpers must reject
unauthenticated, disabled or revoked, role-denied, and out-of-scope actors
before future reviewer-created workflows are enabled.

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
derived values, reviewer-created note/status display values, non-secret actor
display labels, and local/test boundary text. It must not expose provider
subjects or issuers, email addresses, tokens, cookies, private headers,
connection strings, client secrets, raw provider claims, hosted URLs, private
URLs, or unnecessary sensitive narrative content. It does not implement real
login, sessions, cookies, token validation, auth middleware, anonymous writes,
exports, reset/reload execution, hosted live crawling, connector execution,
deployment, or public launch behavior.

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
