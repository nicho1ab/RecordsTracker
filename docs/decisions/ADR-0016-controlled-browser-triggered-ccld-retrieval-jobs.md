# ADR-0016: Approve Controlled Browser-Triggered CCLD Retrieval Jobs

## Status

Accepted

## Context

The project is a public-interest hobby project for early ylc.org testers. It is
not a DSCC project. The hosted CCLD path now has a QNAP-first Docker/PostgreSQL
runtime envelope, provider-agnostic auth boundary, PostgreSQL-backed hosted page
data mode, cloud portability guidance, and server-side GitHub Issues tester
feedback intake.

The next product blocker is controlled browser-triggered CCLD retrieval. The
current `/ccld/records/request` page lets testers find or enter a CCLD
facility/license number, provide an optional date range, load prepared validated
hosted seeded-corpus output, and review matching imported records. When matching
records are not already prepared, it still points testers to an outside-browser
live-fetch and artifact-builder handoff.

ADR-0009 intentionally rejected direct hosted live crawling, hosted connector
execution, and automatic source expansion for the tester MVP unless a later ADR
approved them. ADR-0013 and ADR-0015 repeated that boundary for operational and
persistence safety. That blocker was correct while the project did not yet have
an approved execution model, runtime envelope, auth boundary, page data mode, or
feedback path.

This ADR is that later decision. It approves a narrow browser-triggered,
server-executed CCLD retrieval job boundary. It does not implement retrieval in
this branch.

## Decision

The hosted CCLD app may add a controlled retrieval workflow in a later
implementation branch:

- The browser may trigger a retrieval job with bounded CCLD inputs.
- The browser must not perform scraping, crawling, source discovery, fetching,
  extraction, normalization, validation, import, or raw artifact storage.
- The server performs controlled CCLD source discovery, fetch, raw artifact
  preservation, deterministic extraction, normalization, validation, and
  PostgreSQL import.
- Retrieval is CCLD-only, facility/date/type bounded, authenticated, role/scope
  permissioned, rate-limited, request-limited, timeout-limited, retry-limited,
  auditable or status-evented, and source-traceable.
- Imported source-derived records remain separate from reviewer-created state,
  audit events, retrieval job metadata, operational metadata, and feedback
  issues.

This decision supersedes only the parts of ADR-0009, ADR-0013, and ADR-0015
that described hosted CCLD live crawling, hosted CCLD connector execution, or
browser-triggered CCLD retrieval as not approved. Those statements remain true
for unbounded crawling, non-CCLD sources, private/authenticated sources,
statewide crawl behavior, direct browser crawling, and any implementation that
does not satisfy this ADR.

## Approved Workflow

The approved future workflow is:

1. Tester opens the CCLD request page.
2. Tester selects or enters a CCLD facility/license number.
3. Tester selects one supported CCLD record type or all supported CCLD record
   types.
4. Tester enters a bounded start date and end date.
5. Server validates the input.
6. Server creates a retrieval job.
7. Server performs controlled CCLD source discovery and fetch.
8. Server preserves raw source files or artifacts in configured server-side raw
   storage.
9. Server computes and stores raw source hashes.
10. Server extracts and normalizes records deterministically.
11. Server validates extracted records against the data contract and schemas.
12. Server imports validated source-derived records into PostgreSQL.
13. Server exposes job status and safe result counts.
14. Tester reviews imported records in the existing hosted queue.
15. Tester can submit product feedback through the GitHub Issues feedback
   workflow added in PR #178.

## Allowed Inputs

The browser-triggered request may accept only these inputs:

- CCLD facility/license number.
- CCLD record type.
- All supported CCLD record types.
- Start date.
- End date.

The implementation must define a CCLD record type allowlist before enabling the
workflow. It must not accept arbitrary source URLs, source domains, query
strings, connector names, Python import paths, shell commands, filesystem paths,
raw HTML, cookies, headers, credentials, GitHub tokens, provider tokens, or
private/authenticated source configuration from the browser.

## Required Boundaries

- Browser triggers the job; server performs retrieval.
- Browser must not perform scraping.
- Browser must not receive connector credentials.
- Browser must not receive GitHub tokens.
- Browser must not receive server-side secrets.
- Retrieval must be CCLD-only.
- Retrieval must be facility/date/type bounded.
- Statewide crawling is not approved.
- Automatic source expansion outside approved CCLD sources is not approved.
- Non-CCLD source implementation is not approved by this ADR.
- Private or authenticated source scraping is not approved.
- The app must not make legal, facility-wide, public-source completeness, harm,
  abuse, neglect, liability, rights-deprivation, or unsupported automated
  complaint-finding conclusions.
- Raw source evidence must be preserved before extraction.
- Source-derived records remain separate from reviewer-created state.
- Reviewer-created state remains separate from audit events.
- Retrieval job and operational metadata remain separate from source-derived
  and reviewer-created state.
- Feedback issues remain separate from CCLD source-derived and reviewer-created
  state.
- QNAP Docker is the first deployment target.
- PostgreSQL is the active production-style data store.
- Raw source storage must use configured server-side volumes or paths.
- Platform portability to AWS, Azure, DigitalOcean, Render, Fly.io, Railway,
  Supabase/Neon paired with an app host, or another host must remain possible.

## Required Controls

The implementation branch must define and test these controls before any
browser-triggered retrieval is enabled:

- Authenticated tester access before production use.
- Role and scope permission required to trigger retrieval.
- Server-side allowlist for CCLD source domains and URL patterns.
- Maximum date range.
- Record type allowlist.
- Facility/license number validation.
- Per-job request limit.
- Per-user or per-actor rate limit.
- Timeout limit.
- Retry limit.
- Job status states.
- Safe failure and error messages.
- No raw stack traces to users.
- Secret-safe logging.
- Audit or status event requirements.
- Raw artifact path and hash preservation.
- Import validation status.
- Duplicate and idempotency expectations.
- Operator runbook expectations.
- Backup and restore expectations for PostgreSQL and raw artifacts.
- Tests that mock network retrieval; CI must not make live CCLD calls.

The server-side allowlist must include only approved public CCLD source domains
and URL patterns, such as the public CCLD facility detail and facility report
patterns already used by the existing CCLD connector. The implementation must
reject redirects, unexpected hosts, unsupported schemes, caller-supplied URLs,
and private or authenticated sources.

## Job States

The implementation must support at least these job states:

- `queued`: accepted and waiting for execution.
- `running`: server-side retrieval, extraction, validation, or import is active.
- `completed`: job finished and all required validation/import steps succeeded.
- `completed_with_warnings`: job finished with non-fatal warnings, skipped
  records, partial public-source failures, duplicate-avoided rows, or validation
  warnings that are safe to display as counts or concise messages.
- `failed`: job could not complete after bounded attempts.
- `blocked_by_validation`: user input, source allowlist checks, record type,
  date range, source validation, raw hash validation, extraction validation, or
  import validation blocked execution or import.
- `rate_limited`: per-user, per-actor, per-job, or system request limits blocked
  the request.

The implementation may add `cancelled` only if cancellation behavior is planned
and tested. It may add `expired` only if job retention and expiry behavior are
planned and tested.

## Data and Persistence Boundaries

Retrieval job metadata is operational metadata. It is not a canonical
source-derived field and must not be stored in canonical source-derived tables.
It may reference imported source-derived records, import batches, raw artifacts,
audit/status events, and authenticated actors through stable identifiers, but it
must remain physically and semantically separate from:

- Source-derived imported records.
- Reviewer-created state.
- Audit events.
- Feedback issues.
- Auth role/scope assignments.
- Export packet state.

Imported records must preserve the existing data-contract traceability fields:
source URL, raw SHA-256 hash, raw path or artifact reference when available,
connector name, connector version, retrieval timestamp, source document identity,
report index or document type where available, extraction audit context where
available, original extracted values, validation status, and warnings where
available.

Duplicate and idempotency behavior must prefer stable source-derived identity.
Re-running the same bounded request should not create duplicate source-derived
records or duplicate reviewer-created state. It may refresh, confirm, skip, or
mark source-derived rows as changed according to an implementation-specific
import policy, but reviewer-created state must not be overwritten by retrieval.

## Security and Privacy Requirements

The retrieval job implementation must keep secrets server-side. Browser HTML,
browser JavaScript, job status JSON, logs, audit/status payloads visible to
testers, issue bodies, screenshots, tests, and documentation must not expose:

- Provider subjects or issuers.
- Raw provider claims.
- Tokens.
- Cookies.
- Private headers.
- Connection strings.
- Client secrets.
- GitHub tokens.
- Connector credentials.
- Hosted/private URLs.
- Server-side filesystem paths beyond safe relative artifact references.

Public CCLD narrative content may be sensitive even when public. Job status and
result pages should expose safe counts, source-traceability indicators, warnings,
and queue links rather than raw narrative content.

## Runtime and Portability Requirements

QNAP Docker with PostgreSQL is the first production-like target. The retrieval
implementation may run in the app process for a narrow first slice or in a
separate worker process/container/task, but the design must keep the boundary
portable:

- Configuration comes from environment variables or host secret storage.
- Raw artifacts use configured server-side volumes, paths, or a later approved
  object-storage adapter.
- PostgreSQL remains the production-style data store unless a later ADR changes
  it.
- Job workers must not rely on QNAP-specific application code paths.
- Backups must cover PostgreSQL and raw artifacts.
- Cloud moves must be able to map the same app, database, raw storage, secret,
  backup, and worker responsibilities to provider-native services without
  changing source-derived or reviewer-created data boundaries.

## Testing Requirements

The implementation branch must add tests at the level it implements. At a
minimum, tests must prove:

- Browser-triggered retrieval accepts only facility/license number, record type
  or all supported record types, start date, and end date.
- Invalid facility/license numbers, invalid date ranges, unsupported record
  types, excessive date ranges, too many requests, and out-of-scope actors are
  blocked without network calls.
- Authenticated tester role/scope permission is required before production use.
- Server-side URL/domain allowlist blocks caller-supplied URLs, unsupported
  schemes, redirects to unapproved hosts, private/authenticated sources, and
  non-CCLD sources.
- Per-job request limits, per-user/per-actor rate limits, timeouts, and retry
  limits are enforced.
- Network retrieval is mocked; CI makes no live CCLD calls.
- Raw source artifacts are saved before extraction.
- Raw SHA-256 hashes are computed and preserved.
- Deterministic extraction, normalization, schema validation, and import
  validation occur before PostgreSQL import is reported as successful.
- Source-derived records import idempotently and do not mutate reviewer-created
  state, audit rows, operational metadata, or feedback issues except for the
  explicitly implemented retrieval-job metadata/status/audit path.
- Job states and safe result counts are deterministic and accessible.
- Failure states do not show raw stack traces, secrets, tokens, cookies,
  private headers, connection strings, provider claims, GitHub tokens, or
  unnecessary narrative content.
- Operator runbook, backup/restore, and known-limitation documentation remain
  current.

## Implementation Non-Goals

This ADR branch does not implement live retrieval.

This ADR does not approve or implement:

- No connector code changes in this branch.
- No schema changes in this branch.
- No production OIDC implementation.
- No deployment changes.
- No GitHub feedback export.
- No GitHub Projects.
- No UI redesign.
- No source-derived data mutation through review pages.
- No direct browser crawling.
- Statewide crawling.
- Non-CCLD sources.
- Private/authenticated source scraping.
- Optional paid-platform dependency requirements.

## Consequences

Benefits:

- The previous implementation blocker is resolved with a narrow, testable,
  source-traceable boundary.
- Testers can later request CCLD records from the browser without turning the
  browser into a scraper or exposing server-side secrets.
- The boundary preserves raw evidence, deterministic extraction, PostgreSQL
  import, data-domain separation, and QNAP/cloud portability.
- The next branch can implement the retrieval job without reopening the broad
  governance question.

Tradeoffs and risks:

- Implementation complexity moves from an explicit local script handoff into a
  server-side job path with auth, rate limits, status, storage, and operational
  expectations.
- Public CCLD availability, source layout changes, and partial fetch failures
  remain real operational risks and must be surfaced as job states, warnings, or
  safe operator logs rather than conclusions about the public source.
- Backup/restore must cover both PostgreSQL and raw artifacts because source-
  derived rows depend on preserved raw evidence.

## Work Now Approved

Future focused implementation branches may add controlled browser-triggered,
server-executed CCLD retrieval job behavior inside this ADR's boundaries. The
first implementation branch should be the smallest useful slice that validates
input, creates a job, mocks retrieval in tests, preserves raw artifacts,
imports validated source-derived records into PostgreSQL, exposes safe job
status/result counts, and links the tester back to the existing hosted queue.

## Work Not Approved By This ADR

This ADR does not approve implementation of live retrieval in this branch and
does not approve direct browser scraping, source expansion, statewide crawling,
non-CCLD connectors, private/authenticated source scraping, production OIDC,
deployment changes, GitHub feedback export, GitHub Projects, UI redesign,
source-derived mutation through review pages, legal conclusions, public-source
completeness conclusions, harm/abuse/neglect/liability conclusions, or
unsupported automated complaint findings.