# Testing Strategy

## Aggregate readiness

Aggregate and export changes test positive, verified-zero, unavailable,
partial-source, outside-range, first-investigation-activity range, more-than-100,
explicit-limit, no-limit, present-blank, and source-unavailable cases. Tests
reconcile eligible and returned counts, prove that unavailable is not numeric
zero, and exercise both SQLite execution and PostgreSQL-style result mapping.

Generate focused local evidence with:

```powershell
.\.venv\Scripts\python.exe -m ccld_complaints.aggregate_readiness_evidence --mode local --output-dir <path>
```

Generated evidence is aggregate-safe and must not be committed.

## Test categories

### Unit tests

Validate small deterministic functions such as date parsing, URL parsing, hash generation, and field extraction.

### Fixture-based extraction tests

Validate complete extraction from known raw source files into expected JSON.

### Regression tests

Every extraction bug fix must add a failing fixture or test before the fix is accepted.

Every bug fix, CI failure fix, or repeated review correction must include a root-cause review. If the root cause reveals a missing, unclear, or too-weak project rule, add or update the relevant governance, testing, fixture, connector, or workflow documentation in the same change. If no governance change is needed, state why in the PR or handoff.

Facility review signal parser fixes must include fixture-style rows that cover
the observed public CSV shape, including supported leading summary columns with
trailing repeated detail columns when those trailing values are intentionally not
rendered. Tests must prove unsupported, too-short, shifted, or private trailing
detail values are skipped or ignored without creating source-derived complaint
records or exposing private row contents.

### Contract tests

Validate connector output against JSON schemas and the source connector contract.

### Data quality tests

Validate internal consistency, including required fields, valid date order, allowed finding values, duplicate source URLs, and hash presence.

### Documentation tests

Validate that required documentation files exist and that data dictionary/schema updates are present when schema files change.

Production-discovery requirements changes must run documentation validation and
affected documentation-check tests. Hosted tester MVP implementation must add
validation for review-state separation, annotation and correction traceability,
source-traceable export packet behavior, accessibility expectations,
authentication and access governance, audit event attribution and no-secret
metadata where audit persistence is implemented, feedback collection, and
reset/reload behavior at the level of the implemented change. Reset/reload
operational metadata tests must prove any persisted planning record remains
separate, permissioned, non-secret, and non-executing. Reset/reload planning
metadata read route tests must prove authorized readback remains scoped,
non-secret, and non-mutating.
Reset/reload execution-plan tests must prove the plan is authenticated,
role/scope-checked, ordered, bounded, non-destructive, optionally persisted only
through operational planning metadata, and non-mutating across source-derived,
reviewer-created, audit, import, and operational rows except for the explicitly
requested planning metadata row.
Auth provider integration planning tests must prove the accepted provider class
is enforced, unsupported provider classes and missing readiness inputs are
rejected, secret-like inputs and real URLs are rejected without echoing values,
user-role-admin permission and scope are required, ordering is deterministic,
and no hosted scaffold tables are mutated or persisted auth configuration is
created.
Hosted auth runtime boundary tests must prove production mode is the default,
anonymous browser workflow routes are blocked in production when no authenticated
route context is available, public help remains readable, explicit local-dev
mode is required before the fixture tester actor can be used, local-dev actor
mode is rejected in production mode, role/scope checks still cover source-derived
read, feedback submission, retrieval job trigger, import/reload, and admin-style
actions, disabled or revoked actors are rejected, signed-in labels are safe, and
HTML/JSON output does not expose provider subjects, issuers, raw claims, tokens,
cookies, private headers, hosted URLs, or secrets.
Controlled CCLD retrieval job tests prove the ADR-0016 boundary before and after
browser-triggered retrieval is enabled. Tests must accept only facility/license
number, one allowed record type or all supported record types, start date, and
end date; reject invalid facility/license numbers, invalid date ranges,
excessive date ranges, unsupported record types, too many requests,
unauthenticated actors, role-denied actors, and out-of-scope actors before any
network call; enforce server-side CCLD source-domain and URL-pattern allowlists;
block caller-supplied URLs, unsupported schemes, redirects to unapproved hosts,
private/authenticated sources, and non-CCLD sources; enforce per-job request
limits, per-user or per-actor rate limits, timeouts, and retry limits; exercise
queued, running, completed, completed_with_warnings, failed,
blocked_by_validation, and rate_limited states; mock all network retrieval so CI
makes no live CCLD calls; prove raw source artifacts are saved before
extraction; prove raw SHA-256 hashes, source URLs, connector metadata,
retrieval timestamps, raw paths or artifact references, extraction audit context,
and import validation status are preserved; prove deterministic extraction,
normalization, schema validation, and PostgreSQL import happen before successful
status is reported; prove duplicate/idempotent re-runs do not create duplicate
source-derived rows or mutate reviewer-created state, audit rows, feedback
issues, or unrelated operational metadata; and prove safe errors never expose
raw stack traces, secrets, tokens, cookies, private headers, connection strings,
provider claims, GitHub tokens, private URLs, or unnecessary narrative content.
The first implemented slice also tests request-page controls, safe setup-required
state when retrieval config is missing, mocked successful import into
PostgreSQL-backed source-derived tables, queue linking, safe failure states,
feedback route separation, and existing page-data/reviewer note/status behavior.
Status usability tests should also prove setup-required pages describe missing
operator configuration without exposing private values, validation states explain
facility/date/type issues, completed-with-warnings is distinct from failed,
rate-limited and failed states provide safe next steps, and confusing retrieval
states point to `/feedback`.
Retrieval job history tests should prove the history/status route requires the
same allowed actor boundary as current workflow pages, renders an empty state
safely, lists recent jobs with facility/date/type, state, timestamps, imported
counts, safe warning/error summaries, and status messages, links to the CCLD
queue only when records were imported, points confusing or failing jobs to
`/feedback`, does not expose raw stack traces or private values, does not mutate
source-derived, reviewer-created, audit, feedback, import, or unrelated
operational rows, and uses mocked retrieval data only.
Retrieval job detail tests should prove history rows link to the detail route;
allowed local/test actors can view one job; anonymous production access is
blocked; missing or invalid job IDs render safe states; facility/date/type,
state, timestamps, imported counts, safe status messages, warning/error
summaries, raw-artifact-preserved indicators, review-queue links, and feedback
links render without exposing raw file contents, raw server paths, stack traces,
provider values, tokens, cookies, private headers, connection strings, or
secrets; and detail reads do not mutate source-derived, reviewer-created,
feedback, import, audit, or operational rows.
Local-dev retrieval demo tests should prove `CCLD_RETRIEVAL_DEMO_MODE=mock-success`
is disabled by default, rejected outside explicit local-dev auth mode, uses only
committed fixtures, creates a retrieval job, reaches completed state, imports
source-derived rows through the existing import path, shows imported counts,
links to history/detail/queue, keeps setup-required and validation-blocked states
working, makes no live CCLD or GitHub calls, exposes no private values, and does
not mutate source-derived or reviewer-created rows through review pages.
GitHub Issues feedback intake tests must prove the feedback page renders, the
feedback type dropdown has exactly bug/problem, feature request, data
connector/source request, confusing wording/navigation, and other feedback
options, description and submit controls are accessible, missing values
validate safely, missing GitHub configuration does not call GitHub and shows a
copyable safe fallback summary, configured submission uses only a mocked client,
labels are correct, missing-label failures retry safely without labels,
success/failure states are safe, tokens and provider claims are not rendered or
included in issue bodies, tests make no live GitHub calls, feedback submission
does not mutate source-derived records, and anonymous production submissions are
blocked.
Audit coverage planning tests must prove authenticated audit/admin-style access,
unauthenticated, disabled or revoked, role-denied, and out-of-scope rejection,
deterministic ordering, no secret exposure, no audit row creation, no
persistence, and no mutation of source-derived, reviewer-created, audit, import,
operational, or auth-related scaffold rows.
Reviewer-created state read route tests must prove authorized readback remains
scoped, non-secret, separated from source-derived reads, and non-mutating across
source-derived rows, reviewer-created rows, audit rows, and operational metadata.
When those reads add filtering or search, focused tests must cover matching
results, empty results, permission rejection, out-of-scope rejection, and no
mutation using only existing schema-backed and non-secret scaffold fields.
Reviewer workflow shell state-read integration tests must prove selected detail
payloads compose associated reviewer-created state read route output only
through authenticated, role/scope-allowed local/test contexts and remain
non-secret and non-mutating across source-derived rows, reviewer-created rows,
audit rows, and operational metadata. When the workflow shell derives a state
summary from that associated route output, focused tests must cover empty state,
one row, multiple rows, deterministic summary fields, permission separation,
and no mutation without adding a separate state read path.
Reviewer workflow shell note action tests must prove the selected source-derived
detail context is resolved before write delegation, conflicting caller-provided
source bindings are ignored, reviewer-state write permission is required,
invalid or missing source records and note payloads do not mutate reviewer-
created state or audit rows, successful writes create audit rows, source-derived
rows are not mutated, and existing read routes plus workflow detail output show
the note after write.
Reviewer workflow shell status action tests must prove the selected source-
derived detail context is resolved before write delegation, conflicting caller-
provided source bindings are ignored, reviewer-state write permission is
required, invalid or missing source records and bounded status payloads do not
mutate reviewer-created state or audit rows, successful writes create audit
rows, source-derived rows are not mutated, and existing read routes plus
workflow detail output show the status after write.
Hosted reviewer UI shell tests must prove browser-accessible local/test landing
and detail pages return usable semantic HTML over the seeded fixture corpus,
list-level reviewer-created note/status indicators and latest reviewer-created
timestamp are visible, plain-language detail record summaries are visible,
sensitive narrative fields remain bounded, note/status forms delegate to the
existing workflow actions, concise note/status saved confirmations include
next-step links, read-after-write reviewer-created state appears in the page,
and focused CCLD return/next-record navigation is
visible, unauthenticated, disabled or revoked, role-denied, and out-of-scope
contexts are blocked with visible next steps, no-match search, missing-record,
and invalid note/status form states show clear accessible guidance,
source-derived rows are not mutated by UI actions,
reviewer-created state and audit rows are created only through the existing
services, and HTML does not expose secrets, tokens, cookies, private headers,
raw provider claims, private URLs, hosted URLs, credentials, or unnecessary
sensitive narrative content. Reviewer detail tests should prove the
reviewer-facing tier includes complaint identity, facility identity once near the
top, source narrative, compact complaint/investigation timeline, finding and
allegation summary, review-flag badges as the primary flag expression,
reviewer-created state/actions when useful, copy affordances for core values,
and MM/DD/YYYY date display without changing stored values.
Reviewer detail tests must also prove source traceability internals are not
visible in the reviewer-facing tier: no traceability detail section, raw
SHA-256, connector metadata, source artifact identity, field-level traceability,
source-derived value-check tables, full source-derived field dumps, selected
source-derived bundle summaries, related source-derived row tables,
technical/operator details, facility-context cues, detail navigation dumps,
first-run detail steps, issue-report bridge copy, repeated issue/help/return
action dumps, source-confidence tables, or field-note guidance. These absence
tests must preserve no-mutation behavior across source-derived,
reviewer-created, audit, import, and operational metadata rows.

The `RT-SRC-002` reviewer-detail source-evidence feature requires focused tests
and exact-route visual evidence against Figma file
`SYszaxbcMK8Ce2ywrUiu4q`, section `RT-SRC-002 • Reviewer detail source
evidence`, node `64:2`. Acceptance must prove all of the following:

- Only `First investigation activity date` has the governed field-level `View
  source evidence` interaction. Facility/license number and complaint/control
  number remain contextual identifiers, and no other date, finding, allegation,
  deficiency, regulation, plan of correction, facility name, or facility type
  is presented as a supported field-level evidenced claim.
- The readable `MM/DD/YYYY` date remains visible in closed and open states.
  `Copy date`, `View source evidence` or `Close source evidence`, and `Open
  original source` are separate controls with distinct behavior and accessible
  names.
- Open evidence contains the displayed date, one bounded source event sentence,
  source section, complaint or report identity, reviewer-safe preserved-source
  status, and a separate original-source action, without a full narrative or raw
  field dump.
- Focused state tests cover `closed`, `open`, `document-only`, `field-partial`,
  `source-unavailable`, and `print`. Document-only does not imply field- or
  passage-level verification; field-partial truthfully identifies unavailable
  evidence; source-unavailable does not render a misleading active source
  action; and no fallback makes a source-completeness claim.
- Keyboard tests prove operation of every control, visible focus, the logical
  order `Copy date`, evidence trigger, opened evidence, `Open original source`,
  and focus return to the evidence trigger after closing. Accessible-name tests
  disambiguate the First investigation activity date target without relying on
  icon, color, position, hover, or pointer input.
- Responsive tests and visual evidence cover `Desktop evidence closed`,
  `Desktop evidence open`, `Narrow desktop evidence open`, `Mobile compact
  evidence open`, `200% zoom reflow`, and `Keyboard focus`. They verify the
  approved compact mobile touch target, logical reading/keyboard order, no
  clipping or detached controls, and no horizontal page scrolling.
- Print tests and `Print state` evidence prove the supported claim, bounded
  evidence, reviewer-safe source status, and readable original-source URL print;
  navigation, interactive, copy, and reviewer-created controls do not.
- Privacy and tier tests prove that the reviewer output contains no raw SHA-256,
  raw path, connector metadata, source document ID, database ID, extraction-
  audit table, full narrative, raw field dump, legal conclusion, source-
  completeness claim, secret, token, credential, private URL, or other unsafe
  internal value.
- Domain tests prove the claim, evidence, source status, and original-source
  action remain visibly and semantically grouped as source-derived and separate
  from reviewer-created notes, statuses, and actions. Opening, closing, copying,
  and source navigation do not mutate source-derived, reviewer-created, audit,
  import, or operational rows.

The exact reviewer-detail route must be captured for every approved normal,
fallback, responsive, keyboard-focus, and print state named above. Evidence must
compare each capture to node `64:2`, include DOM/content and accessible-name
inspection, and treat any unsupported field-level claim or material interaction,
reflow, focus, privacy, print, or domain-separation variance as an acceptance
failure. Passing markup tests alone does not establish conformance.

The seeded exact route for that evidence is:

`/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448`

Reviewer note/status confirmation tests should cover concise return-to-queue,
next-record, unchanged-source-derived-record, read-after-write, and no-mutation
behavior without requiring help/checklist/feedback bridge copy on the detail
page.
First-run orientation tests should cover Home, Request Records, Help, queue, and
feedback surfaces where orientation belongs. They must not require first-run,
how-to-read, field-note, source-confidence, or feedback-checklist guidance to be
visible on reviewer detail.
Reviewer detail next-record navigation tests should prove return-to-same-queue
guidance, note/status confirmation next-record wording, queue suggested-next
wording, and no-assignment/no-claim/no-workflow-state boundaries render while
preserving existing request context and no-mutation behavior.
Filtered-empty queue tests should prove the active reviewer-status filter, same
facility/date request context, clear-filter action, reviewer-created-state basis,
manual feedback guidance, and no-missing-record/no-public-absence wording render
without mutating source-derived, reviewer-created, audit, import, or operational rows.
Queue source-check wording tests should prove queue summaries identify their
values as source-derived display summaries and direct testers to reviewer
detail, Help, or the public source link before relying on missing, confusing, or
proxy-related fields without requiring source-confidence tables on detail.
Terminology consistency tests should prove the app uses the selected plain-
language terms for CCLD request context, facility/date request, loaded local/test
CCLD records, source-derived records, reviewer-created notes/status, reviewer-
status filter, suggested next record, and manual feedback checklist on the
changed pages without changing behavior.
Hosted facility-priorities tests must prove `/reviewer/facilities/priorities`
aggregates deduplicated complaint records by stable source-derived facility
identity, orders rows by visible deterministic factors with stable tie-breaking,
filters by facility type, geography, activity date window, minimum complaint
count, minimum substantiated/equivalent count, and supported indicators, renders
missing values, low-data rows, empty results, bounded pagination, complaint
queue/detail links, and original-source link availability accessibly, preserves
authorization and import-batch scope, excludes fixture/demo fallback data in
production mode, and does not mutate source-derived, reviewer-created, audit,
import, feedback, retrieval-job, or operational rows.
Hosted cross-facility intelligence tests must prove
`/ccld/facilities/intelligence` reads the authorized loaded complaint corpus,
deduplicates by stable complaint identity, reuses governed facility priority,
substantiated/equivalent, serious-topic, trend/anomaly, and aggregate coverage
logic, and reconciles visible totals and per-facility counts to exact complaint
detail links. Combined filters must cover facility type, geography, date
dimension/range, finding, serious-review category, and available/partial/
unavailable source coverage; ordering and recommended-next selection must be
deterministic and explainable. Tests must cover missing values, missing dates,
partial and unavailable coverage, negative and no-result cases, invalid ranges,
duplicates, authorization/import-batch isolation, GET no-mutation, safe
PostgreSQL setup failure without fixture/synthetic fallback, semantic headings
and labeled controls, descriptive links, badge text meaning, MM/DD/YYYY display,
filter context preservation, no raw traceability internals or secrets, and
source-derived versus reviewer-created state separation. Exact-route hosted UI
evidence must assert the decision heading and recommended-next action.
Hosted facility review hub tests must prove `/ccld/facilities/detail` reuses
those governed cross-facility calculations for one Facility ID; preserves
useful intelligence origin/filter context; reconciles deduplicated complaint,
date-range, finding, serious-review, anomaly, source-coverage, reviewer-status,
and reviewer-note aggregates to exact stable complaint links; and uses the same
deterministic recommended-next and tie order. Tests must also cover loaded,
filtered-empty, no-record, invalid Facility ID, partial/unavailable source,
reviewer-state-unavailable, and PostgreSQL setup states; facility facts shown
once; compact timelines; `MM/DD/YYYY` dates; accessible copy controls and inline
definitions; badge-only review-flag expression; active Facilities navigation;
safe narrow-width/zoom CSS; no mutation; no fixture/synthetic PostgreSQL
fallback; and no raw traceability internals, note text, private values, or
secrets.
Hosted facility-trends tests must prove `/reviewer/facilities/trends` groups
authorized loaded complaints by month and quarter using stable complaint
identity, honors inclusive date boundaries and combined facility, facility type,
geography, finding/status, and governed serious-topic filters, reconciles total,
substantiated/equivalent, serious-topic, and unavailable-date counts, and orders
periods and complaint links deterministically. Tests must cover complete,
incomplete-current, zero-qualifying, unavailable-coverage, and unavailable-date
states; increased, new, decreased, and no-cue rules with both contributing
counts; semantic tables and labeled controls; reviewer-detail/source access;
authorization and import-batch separation; no raw narrative or private output;
and no mutation. Focused hosted evidence for this slice uses `-Issue418`.
Hosted serious-topic worklist tests must prove `/reviewer/records/serious-topics`
uses only governed deterministic source categories and governed keyword cues,
labels official allegation categories as source-derived, allows keyword-assisted
cues only when the source category is missing or unknown, excludes complaint
control numbers from keyword matching, keeps category and cue filters separate,
combines those filters with finding, facility, geography, and complaint date,
deduplicates by stable complaint identity, reconciles counts, renders bounded
pagination, MM/DD/YYYY dates, cautious wording, accessible controls,
descriptive complaint and original-report links, empty states, and no raw
allegation narrative in the primary worklist, preserves authorization and
import-batch scope, and does not mutate source-derived, reviewer-created, audit,
import, feedback, retrieval-job, or operational rows. Hosted route evidence for
this slice should use the focused `-Issue417` capture mode.
Hosted CCLD record request UI tests must prove the browser-accessible local/test
request page accepts only CCLD digit facility/license numbers plus optional
valid date ranges, returns accessible validation guidance for missing or invalid
requests, reads matching rows only from the seeded source-derived route seam,
can load or refresh matching CCLD rows from local validated hosted seeded-corpus
output through the existing source-derived import path, links matching seeded
complaint records into the hosted reviewer UI, shows a clear no-match and
external pipeline plan when local validated records do not match, distinguishes
currently loaded local/test data from public-source absence, renders a
guided facility/date-scoped request result queue with first-time workflow help,
contextual field/action help, source traceability summaries, reviewer-state
indicators, queue triage summaries, reviewer note/status cues,
source-traceability availability cues, suggested next-record links,
filtered-empty guidance, skip-to-main links, visible next-step guidance,
specific form/action text, request-context confirmation for lookup-selected and
manual facility/license entry requests, progress counts, reviewer-status filtering,
meaningful reviewer links, read-after-write queue updates after reviewer
note/status actions, and
deterministic copyable feedback checklist guidance without persistence, does not
run live crawling, execute connectors, mutate reviewer-created state from the
request page, create audit rows, mutate operational metadata rows, or persist
feedback, and does not expose secrets, private URLs, provider claims, credentials,
or unnecessary sensitive narrative content.
Hosted CCLD facility lookup tests should cover committed tiny fixture fallback,
configured full local/test CCLD facility reference CSV loading, required column
mapping, malformed or missing full CSV guidance, active reference-source
messages, safe scalar display fields, partial and case-insensitive matching by
facility/license number, facility name, city, county, ZIP code, facility type,
and status when present, bounded result lists, empty-search guidance, no-match
guidance, selected facility carry-forward into `/ccld/records/request`, manual
facility/license entry preservation, no live browser retrieval, no connector
execution, no persistence, no source-derived, reviewer-created, audit, import,
or operational metadata mutation, accessible headings/labels/captions/link text,
and no-secret HTML output.
PostgreSQL-backed page data tests must prove production-style page mode does not
silently use fixture data, shows setup-required guidance when PostgreSQL context
is unavailable, reads source-derived facility rows from the hosted source-derived
table group when a database-backed context is supplied, keeps request queue and
reviewer detail on source-derived plus reviewer-created route seams, and keeps
fixture-demo behavior isolated behind explicit local/demo configuration.
Hosted CCLD import/reload tests must prove local validated artifacts are
validated before load, source URL/raw SHA-256/raw path/connector traceability is
preserved, existing source-derived keys are refreshed without duplicates,
facility/date no-match requests defer without writes, and browser request paths
do not invoke live public web requests. Default and PostgreSQL contexts must
also prove they neither import nor render the committed tiny seeded corpus; that
artifact is available only through explicit local fixture-demo/test opt-in.
Hosted CCLD artifact builder tests must prove fixture-backed validated SQLite
output converts into deterministic hosted seeded-corpus JSON, validates through
the existing hosted seeded parser, preserves source-derived bundles and source
traceability, rejects missing or unsafe traceability fields, remains no-secret,
and is compatible with the existing hosted seeded import and CCLD import/reload
path without running live crawling or browser-triggered connector execution.

Hosted CCLD refresh/backfill tests must prove complaint-report facility type,
structured visit-based first activity, approved-reference ownership and
conflict provenance, blank-preserving updates, dry-run rollback, apply/repeat
idempotency, bounded batch and checkpoint/resume behavior, failure isolation,
preserved raw URL/hash/path/retrieval metadata, stable source-derived identities
and import scope, unchanged reviewer-created state/audit history, reviewer UI
visibility, and ordinary retrieval parity. Tests must use source-shaped fixtures
and doubles only; they must not make live CCLD requests.

Issue #447 canonical-allocation evidence tests must cover the exact 12-field
registry, canonical importer population, null versus verified zero, date-list
ordering/deduplication, raw composite provenance, additive migration behavior,
idempotent initialization/reimport, no synthetic production fallback, and
separate runtime capability versus population reporting. Evidence is aggregate-
safe and writes only `manifest.json`, `allocation-results.csv`,
`import-results.csv`, `null-semantics-results.csv`, `migration-results.csv`,
`gap-status.csv`, and `summary.md` under an ignored output directory.

Issue #448 store-parity evidence tests must compare equivalent governed
canonical inputs through actual temporary SQLite execution and the hosted
SQLAlchemy mapping path, compile the exercised hosted table and statement shapes
with the PostgreSQL dialect, and clearly state that this is not a live
PostgreSQL service test. Coverage must include entity counts, canonical field
presence/population/null counts, explicit numeric zero, present-but-blank and
source-unavailable audit states, source-document/raw-hash linkage, event and
date-array ordering, duplicate suppression, idempotent reimport, additive
migration, facility-reference preload, reviewer-created-state preservation,
production fixture-fallback guards, schema-version mismatch, local/runtime
inspection status, refresh readiness, and forced mismatch failure. Evidence is
aggregate-safe and writes only `manifest.json`, `store-results.csv`,
`field-parity-results.csv`, `null-semantics-results.csv`,
`idempotency-results.csv`, `refresh-readiness-results.csv`, `gap-status.csv`,
and `summary.md` under an ignored output directory.

QNAP-first Docker runtime tests must statically validate `Dockerfile`,
`docker-compose.qnap.yml`, and `.env.example` for the production-like
PostgreSQL runtime envelope. They must prove the examples use placeholder-only
environment values, PostgreSQL in Docker, named volumes, health checks, Alembic
startup migration wiring, portable paths, and no committed secrets. When Docker
is available, run a bounded Compose configuration validation; Docker availability
is not required for the standard local non-Docker scaffold workflow.
QNAP pilot workflow tests must also prove any setup or verification script keeps
secrets out of the repo, checks required env values, preserves configurable raw
artifact storage, keeps mock-success demo mode disabled by default, rejects or
clearly scopes mock-success outside QNAP/pilot-like runtime, validates Compose
configuration, and avoids hard-coded QNAP-only application paths.

### Fixture hash and line-ending tests

Raw fixtures with expected SHA-256 hashes must use the line endings required by `.gitattributes`. Expected fixture hashes must match Git-normalized bytes, not platform-specific working-tree bytes. When adding or changing raw fixtures that appear in expected JSON, verify line endings and hashes before committing.

### Public-source planning fixtures

Tiny public-source planning fixtures may be committed only when they are small,
documented, safe to publish, and clearly separated from ignored raw source files
and generated profiling outputs. Tests for those fixtures should verify that the
files are present, tiny, traceability-shaped, synthetic or minimized, and not
usable as full raw-source dumps or production imports.

### Accessibility tests

Validate documentation structure and run manual or automated checks for user-facing pages before release.

## Minimum pull request requirements

- Existing tests pass.
- New or changed extraction behavior includes fixture tests.
- Bug fixes include regression tests.
- Bug and CI-failure fixes include a root-cause governance review and update the relevant governance rule when a missing rule contributed to the failure.
- Data contract changes include schema and documentation updates.
- User-visible behavior changes include user documentation updates.
- Implementation work uses focused local validation first, then required remote
  validation before merge.
- PR bodies include focused validation, why those focused checks matched the
  change, required remote check results, any intentionally unrun tests with the
  reason, and full local validation results only when full local validation was
  required or run.
- Readiness, hardening, planning, and checklist PRs must also state the
	user-facing CCLD MVP capability, tester productivity improvement, or concrete
	MVP-blocking risk that justifies doing the work now. If that product-benefit
	case is weak, keep the item tracked as deferred readiness instead of making it
	the next branch.

## Validation tiers

### Capability-specific validation and evidence ownership

- **II** owns the focused local validation authorized for the implementation.
  It runs full validation only when the task assigns it; unrun validation must
  never be reported as passed.
- **HV-READ** owns authorized read-only route, responsive, keyboard,
  accessibility, print, screenshot, and visual evidence.
- **HV-WORKFLOW** owns evidence for the exact authorized ordinary-user
  mutations and proof of required cleanup or state disposition.
- **RL-PREPARE** verifies that required evidence is available for the assigned
  commit and monitors the required CI checks. It does not recreate evidence by
  exceeding the granted browser or workflow authority.
- **RL-MERGE** re-verifies successful required checks, evidence and review gates,
  and the absence of merge blockers before an authorized merge and cleanup.
- **RO** may review validation and evidence sufficiency but may not claim it
  executed validation or evidence capture that another capability performed.

Evidence must identify the commit SHA, route or target, scenario, viewport when
applicable, capability used, and whether the evidence was local or hosted.
Phase handoffs must distinguish evidence availability from evidence execution
and must identify any intentionally unrun validation.

### Local implementation validation

For a focused bug fix or similarly narrow change, run the new regression
independently, then the smallest affected test set. Run targeted Ruff and mypy
checks appropriate to the changed files, documentation validation when
documentation or governed behavior changes, and `git diff --check`. Explain why
the selected checks prove the changed behavior in the PR body or task handoff.

Do not run the complete local test suite by default for an ordinary focused
change. Focused tests must genuinely prove the changed behavior, and unrun
validation must never be reported as passed.

Use focused validation such as:

- Extraction changes: targeted extractor tests and related fixture regression tests.
- Connector changes: targeted connector discovery, fetch, and raw storage tests using fixtures or mocks.
- Data contract or schema changes: schema validation, init or migration SQL tests, persistence tests, and affected data dictionary checks.
- Datasette, view, or export changes: affected SQL, view, export, metadata, and documentation checks.
- Documentation-only changes: documentation validation and link or reference checks.
- Production-discovery requirements changes: documentation validation and affected documentation-check tests.
- Security or privacy changes: security checks and any affected tests.
- Accessibility-facing changes: documentation, export, view, or presentation accessibility checks.

### Required GitHub PR validation

Before merge, verify the required GitHub status-check contexts pass:

- `validate`
- `docs-check`
- `fixtures`
- `security`

These required checks provide broader pre-merge validation for ordinary focused
changes. Focused local validation does not weaken, replace, or bypass them.

### Full local or release validation

Run or verify the full test suite when explicitly requested; for releases,
production-readiness milestones, schema changes, connector expansion,
export-contract changes, production architecture transitions, or broad
cross-cutting changes; or when focused or CI failures require broader
investigation.

## Commands

Select commands according to the validation tier above. `scripts\test.ps1` runs
the complete local suite and is not a default requirement for a focused bug fix.
Use `scripts\docs.ps1` for documentation changes and changes to governed
behavior, and always run `git diff --check` for edited files.

For CI failures, also run the exact failing workflow command locally when it can
be run without secrets or live external requests. If local and CI results differ,
check cross-platform behavior such as line endings, path separators, filesystem
glob ordering, locale-sensitive output, and Git-normalized fixture bytes. For
fixture hash failures, verify Git-normalized bytes with commands such as:

```powershell
git ls-files --eol tests\fixtures\ccld\raw\<fixture-name>.html
```

```powershell
git show HEAD:tests/fixtures/ccld/raw/<fixture-name>.html
```

## Reviewer UI design-conformance and source-to-screen tests

Reviewer-facing facility hub and complaint-detail coverage must prove:

- only one canonical complaint inventory appears for the current page context;
- each stable complaint identity appears once in that inventory;
- aggregate metrics, topics, findings, trends, source availability, and reviewer-state summaries filter, highlight, or link to that inventory instead of duplicating records;
- meaningful source-backed complaint subject summaries are rendered when governed source terms are available;
- generic `contributing complaint` wording is not used as the primary complaint label;
- primary records, allegations, findings, deficiencies, and plans of correction remain visible without opening `<details>` or another disclosure control;
- disclosure elements contain only secondary content;
- active filters are keyboard operable, visibly identified, and announce result counts;
- the inventory works at approved desktop, narrow-desktop, mobile, and 200% zoom conditions;
- approved design tokens and traffic-light protocol semantics are used consistently and never rely on color alone;
- exact-route screenshots are compared with the named approved Figma or design-package frame, and material variance fails acceptance;
- fields visibly present in governed sample reports cannot silently render as `Not provided` without an explicit availability or failure state;
- a source-to-screen inventory reconciles source presence, extraction, normalization, canonical allocation, PostgreSQL population, read-model exposure, and required UI display;
- the shared facility identity projection produces consistent facility name, type, address, county, capacity, and status behavior across queue, complaint detail, facility hub, packet, and export surfaces.
