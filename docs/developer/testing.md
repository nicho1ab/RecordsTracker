Status-usability coverage should assert plain-language labels plus machine-
readable state, safe status messages, result counts, warning/error separation,
review links only when records were imported, and `/feedback` guidance for
confusing retrieval states.
# Testing

## Run all tests

```powershell
.\scripts\test.ps1
```

## Run linting and type checks

```powershell
.\scripts\lint.ps1
```

## Test the review bundle exporter

The export bundle workflow is covered by integration tests. To manually check it after sample ingestion:

```powershell
.\scripts\run-ccld-sample.ps1
```

```powershell
.\scripts\export-review-bundle.ps1
```

Confirm the generated CSV files keep clear headers and source traceability columns, and that the generated README describes delay flags, timeline rows, facility pattern counts, multi-facility traceability rows, and facility comparison rows as screening aids.

The integration tests also build a small fixture-backed multi-facility corpus with `populate_multi_facility_sample_database`. That corpus uses tracked fixtures only and exercises facility identifier intake diagnostics, controlled fetch summary output, multi-facility source traceability, facility comparison, and review-bundle exports without live public requests. Keep it small and deterministic; do not treat fixture counts as public-source completeness or facility conclusions.

## Test design

Prefer fixture-based tests over ad hoc manual verification. Every important source report should have:

- Raw fixture
- Expected JSON
- Parser test
- Data quality test

Data quality tests should include source traceability checks for derived records.
At minimum, complaints, allegations, events, and extraction audit rows should
trace back to a source document with source URL, raw SHA-256 hash, connector
metadata, and retrieval timestamp.

Hosted auth provider integration planning tests must prove the accepted managed
OpenID Connect/OAuth 2.0 provider class is enforced, readiness inputs are
non-secret and deterministic, unsupported providers and missing readiness fields
are rejected, secret-like values and real URLs are rejected without being echoed,
user-role-admin permission and scope are required, no provider configuration is
persisted, and existing hosted scaffold tables are not mutated.

Hosted audit coverage planning tests must prove current and deferred audit
coverage output is authenticated, audit/admin-scoped, deterministic,
non-secret, and non-persistent; unauthenticated, disabled or revoked,
role-denied, and out-of-scope actors are rejected; no audit rows are created;
and import, source-derived, reviewer-created, audit, operational, and auth-
related scaffold rows are not mutated.

Hosted reset/reload planning tests must prove the implemented layer is
non-mutating. Dry-run tests should check affected seeded import batches,
source-derived record counts, scoped reviewer-created scaffold counts, scoped
audit scaffold counts,
reviewer-created state handling options, permission failures, invalid requests,
and before/after table counts without executing imports, reloads, archives,
clears, truncates, deletes, overwrites, or new dry-run audit-event persistence.
Operational metadata tests should also prove planning records are persisted only
when explicitly requested, remain separate from source-derived, reviewer-created,
and audit rows, reject unauthenticated, disabled or revoked, role-denied, and
out-of-scope actors, reject secret-like planning context, and never execute
reset/reload.
Execution-plan tests should prove the action plan is ordered, bounded,
permissioned, non-secret, and non-executing; rejects invalid requested mode and
reviewer-created state handling options; persists planning metadata only when
explicitly requested; and does not mutate import, source-derived, reviewer-
created, audit, or operational rows except for the optional planning metadata row.
Planning metadata read route tests should prove persisted planning rows are
readable only through authenticated, role/scope-allowed local/test routes,
support approved schema-backed filters, return non-secret payloads, and do not
mutate operational metadata, source-derived rows, reviewer-created rows, or
audit rows.

Hosted reviewer-created state scaffold tests must prove reviewer-created rows
are stored separately from source-derived rows, source-derived records and
original extracted values are not modified, authenticated actor context is
required, write permission and project/corpus scope are enforced, disabled or
revoked actors are rejected, invalid source-derived references are rejected, and
basic scoped readback works where implemented.

Hosted reviewer workflow shell state-read integration tests must prove selected
source-record detail payloads can compose associated reviewer-created state read
route output only through authenticated, active, role/scope-allowed local/test
contexts. When detail payloads include a derived associated-state summary, tests
should prove the summary comes from that route output and covers empty state,
one row, multiple rows, deterministic summary fields, and non-secret actor
attribution labels. Tests should cover authorized detail readback, empty
associated state, missing source records, unauthenticated actors, disabled or
revoked actors, role-denied actors, out-of-scope actors, source-derived read
versus reviewer-state read permission separation, non-secret associated state
payloads, and before/after table counts proving detail reads do not mutate
source-derived rows, reviewer-created rows, audit rows, or operational metadata.
Workflow shell note action tests should also cover successful note creation from
the selected detail context, forced source-record binding from that selected
context, permission failures, invalid or missing source records, invalid note
payloads, successful audit creation, no audit/state mutation on failure,
read-after-write visibility through existing read routes and workflow detail
output, and no source-derived mutation.
Workflow shell status action tests should cover successful bounded status
creation from the selected detail context, forced source-record binding from
that selected context, permission failures, invalid or missing source records,
invalid status payloads, successful audit creation, no audit/state mutation on
failure, read-after-write visibility through existing read routes and workflow
detail output, and no source-derived mutation.
Hosted reviewer UI shell tests should cover browser-accessible local/test
landing and detail HTML pages over the seeded fixture corpus, list-level
reviewer-created note/status indicators and latest reviewer-created timestamp,
plain-language record summaries, safe source traceability display, source-
confidence cues for present, missing, and proxy-flagged local/test complaint
fields, field-note guidance for cautious reviewer-created observations, safe
related seeded bundle context with sensitive narrative fields hidden,
clear missing-value wording for unavailable local/test traceability values, labeled search/
note/status controls, note/status form delegation to the existing workflow
actions, read-after-write reviewer-created state display, same-request
return-to-queue progress guidance, CCLD return navigation, record-specific
feedback guidance, non-conclusion boundary wording, no-match search, missing-record, invalid note/
status form, and blocked-request next-step guidance, unauthenticated, disabled or revoked, role-denied, out-of-scope,
and source-read-versus-reviewer-state permission separation blocking, no-secret
HTML output, successful audit creation, and no source-derived mutation.
Record-specific feedback handoff coverage should verify that detail pages tell
testers what source traceability, source context, note/status confirmation,
same-queue return, queue refresh, unexpected-record, confusing label, wording,
keyboard-flow, or next-step observations to carry into the existing manual
checklist without adding feedback persistence.
Feedback checklist bridge coverage should verify that reviewer detail points
those observations to the existing manual checklist without rendering a second
checklist, storing feedback, sending feedback, exporting feedback, or mutating
source-derived, reviewer-created, audit, import, or operational metadata rows.
Queue-to-detail checklist continuity coverage should verify that queue pages,
reviewer detail pages, and note/status confirmations point to the same existing
manual checklist for queue-level and detail-level observations while preserving
single-checklist/manual-copy behavior.
First-run review session orientation coverage should verify that home,
request/help, queue, reviewer detail, note/status confirmation, and checklist
surfaces explain the current CCLD-only path in order: facility lookup or manual
entry, request-context confirmation, loaded local/test queue, reviewer detail
source traceability/source-confidence/field-note review, reviewer-created
note/status observations, same-queue refresh, next-record continuation, and
manual checklist copy. Coverage should also prove the wording does not add saved
sessions, persisted queue state, duplicate checklists, feedback persistence,
live browser fetch, connector execution, artifact building, schema changes, auth,
workflow-engine state, or mutations.
Next-record navigation coverage should verify that queue and detail pages tell
testers how to return to the same request context, resubmit when needed, and use
suggested-next cues derived from existing reviewer-created state without
implying persisted assignment, record claiming, or workflow-engine state.
Queue source-confidence wording coverage should verify that queue summaries are
labeled as source-derived display summaries and point testers to reviewer detail
before relying on missing, confusing, or proxy-related fields in notes/status or
manual feedback.
Field-note guidance coverage should verify that reviewer detail gives short,
cautious wording guidance for present, missing, proxy-flagged, and confusing
fields while preserving existing note/status write behavior and no-mutation
boundaries.
Filtered-empty queue coverage should verify that the selected reviewer-status
filter, same request context, all-status recovery action, reviewer-created-state
basis, no-missing-record wording, and manual feedback guidance render without
changing queue behavior or persisted state.
Terminology consistency coverage should verify that request/help, queue,
reviewer detail, note/status, no-match/load, filtered-empty, next-record, and
manual checklist wording uses the same plain-language terms without changing
behavior or persistence.

Hosted CCLD request and import/reload tests should cover digit-only facility/
license input, optional date ranges, empty hosted source-derived state, loading
from local validated hosted seeded-corpus JSON output, source URL/raw SHA-256/
raw path/connector traceability preservation, duplicate-safe refresh behavior,
deferred no-match behavior, reviewer UI links after load, no browser live
crawling, no generic connector execution, no reviewer-created state or audit
mutation, no operational metadata mutation, guided request result queue
rendering, help page rendering, contextual facility/date/load/review help,
no-match guidance that distinguishes currently loaded local/test rows from
public-source absence and tells testers when to change criteria, load local
validated data, run outside-browser preparation, or report missing/unexpected
records in the feedback checklist,
first-time workflow overview, queue triage summaries, reviewer note/status cues,
source-traceability availability cues, suggested next-record links,
filtered-empty guidance, skip-to-main links, visible next-step guidance,
specific form/action text, lookup-selected and manual-entry request-context
confirmation, deterministic copyable feedback checklist guidance
without persistence, accessibility-oriented headings/labels/captions/link text,
and no-secret HTML output.
Hosted reviewer UI shell tests should also cover skip-to-main links, CCLD
workflow navigation, first-run detail steps, and record-specific note/status
button text, saved-state confirmation wording, return-to-queue links, and
read-after-write detail state while preserving existing read/write and audit
behavior.
Hosted CCLD facility lookup tests should cover committed tiny fixture fallback,
configured full local/test CCLD facility reference CSV loading, safe scalar field
display, partial and case-insensitive matching by facility/license number,
facility name, city, county, ZIP code, facility type, and status, bounded result
lists, empty-search and no-match guidance, missing or malformed full CSV fallback
guidance, active reference-source messages, selected facility carry-forward into
`/ccld/records/request` with lookup-origin context, manual entry preservation, no browser live retrieval, no
direct browser crawling, no connector execution, no persistence, no source-derived/reviewer-created/audit/
import/operational metadata mutation, accessible headings/labels/captions/link
text, and no-secret HTML output.
Hosted CCLD artifact builder tests should build fixture-backed validated SQLite
output, convert it into hosted seeded-corpus JSON, validate the JSON through the
existing hosted seeded parser, import it through the existing hosted seeded
import path, exercise the CCLD import/reload path against that generated
artifact, prove deterministic ordering, prove source traceability preservation,
reject missing or unsafe traceability fields, and prove no live crawling or
browser-triggered connector execution is required.

Controlled CCLD retrieval job tests cover the ADR-0016 boundary before and after
browser-triggered retrieval is enabled. Tests should prove only facility/license
number, record type or all supported record types, start date, and end date are
accepted; invalid inputs, excessive date ranges, unsupported record types,
unauthenticated actors, role-denied actors, out-of-scope actors, rate limits, and
request limits block before network calls; server-side CCLD source allowlists
block caller-supplied URLs, unsupported schemes, redirects to unapproved hosts,
private/authenticated sources, and non-CCLD sources; network retrieval is mocked
so CI makes no live CCLD calls; raw artifacts are preserved before extraction;
raw SHA-256 hashes and source traceability are preserved; deterministic
extraction, validation, and PostgreSQL import happen before successful status;
job states and safe result counts are deterministic; re-runs are duplicate-safe;
source-derived records, reviewer-created state, audit rows, feedback issues, and
unrelated operational metadata are not mutated outside the implemented retrieval
metadata/status path; and errors never expose stack traces, secrets, tokens,
cookies, private headers, connection strings, provider claims, GitHub tokens,
private URLs, or unnecessary narrative content.
The first implementation tests also cover the request-page record type dropdown,
safe setup-required state when retrieval configuration is missing, mocked
successful retrieval/import, queue links after import, and feedback route
separation.
Retrieval job history/status tests should cover `/ccld/retrieval/jobs` rendering
for an allowed local/test actor, production anonymous blocking, safe empty state,
recent job rows with facility/date/type/state/timestamps/counts, warning versus
failed guidance, queue links only after imports, `/feedback` guidance for
confusing or failing jobs, no raw private values in HTML, no source-derived row
mutation during reads, existing request/status behavior, existing `/feedback`
behavior, and no live CCLD calls.
Retrieval job detail tests should also cover
`/ccld/retrieval/jobs/detail?job_id=` links from history rows, allowed local/test
detail rendering, production anonymous blocking, safe missing/invalid job ID
states, completed job queue links, warning versus failed/rate-limited guidance,
raw-artifact-preserved indicators without raw file contents or server paths, no
private values in HTML, no source-derived or reviewer-created mutation, existing
history behavior, existing request/status behavior, existing `/feedback`
behavior, and no live CCLD calls.

Docker runtime tests should statically validate `Dockerfile`,
`docker-compose.qnap.yml`, and `.env.example` for the QNAP-first PostgreSQL
runtime. They should prove the examples use placeholder-only environment values,
PostgreSQL in Docker, named volumes, health checks, Alembic migration startup,
portable paths, and no committed secrets. When Docker is available, developers
may also run a bounded Compose configuration validation, but Docker availability
is not required for the standard local non-Docker scaffold workflow.

Hosted reviewer-created state read route tests must prove persisted scaffold
rows are readable only through authenticated, active, role/scope-allowed local/
test routes with reviewer-state read permission. Tests should cover authorized
list and fetch paths, empty list, missing records, schema-supported filters,
bounded search success and empty search results, unauthenticated actors,
disabled or revoked actors, role-denied actors, out-of-scope actors, invalid
requests, note creation with reviewer-state write permission, invalid note
payload and missing source rejection, read-after-write visibility through the
existing read routes and workflow shell detail composition, status creation with
reviewer-state write permission, invalid status rejection, successful note/status
audit event creation, non-secret payloads, and before/after table counts proving
reads do not mutate source-derived rows, reviewer-created rows, audit rows, or
operational metadata.

Hosted audit event scaffold tests must prove successful reviewer-created state
scaffold writes, including reviewer note writes, create separate audit rows with
authenticated actor attribution, permission, project/corpus scope, action,
target, and source-derived context;
failed reviewer-created writes do not create successful audit rows; audit
persistence failure rolls back the reviewer-created write; source-derived and
reviewer-created rows are not modified by audit persistence; audit read
permission is enforced; and audit context metadata does not store secrets,
tokens, cookies, private headers, connection strings, or unnecessary sensitive
narrative content.

Hosted audit history route tests must prove the implemented read seam is scoped,
authenticated, role-allowed, non-mutating, and limited to non-secret audit row
fields. Tests should cover authorized list and fetch paths, empty history,
missing events, schema-supported filters, unauthenticated actors, disabled or
revoked actors, role-denied actors, out-of-scope actors, invalid requests, and
before/after table counts.

## Regression rule

When fixing extraction behavior, add the failing case as a fixture before changing parser code.

## CI failure rule

When fixing a CI failure, identify the exact failing workflow command and run it
locally when it does not require secrets or live external requests. If local and
CI results differ, check cross-platform behavior such as line endings, path
separators, filesystem glob ordering, locale-sensitive output, and Git-
normalized fixture bytes.

Every bug or CI-failure fix must include a root-cause governance review. If a missing or unclear rule contributed to the failure, update the relevant governance, testing, fixture, connector, or workflow documentation in the same change. If no governance rule is needed, state why in the PR or handoff.

## Fixture hash rule

Raw fixtures with expected SHA-256 hashes must use the line endings required by `.gitattributes`. Compute expected hashes from Git-normalized bytes, not from platform-specific working-tree bytes.

Use this check when changing raw fixtures:

```powershell
git ls-files --eol tests\fixtures\ccld\raw\<fixture-name>.html
```
