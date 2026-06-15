# Testing Strategy

## Test categories

### Unit tests

Validate small deterministic functions such as date parsing, URL parsing, hash generation, and field extraction.

### Fixture-based extraction tests

Validate complete extraction from known raw source files into expected JSON.

### Regression tests

Every extraction bug fix must add a failing fixture or test before the fix is accepted.

Every bug fix, CI failure fix, or repeated review correction must include a root-cause review. If the root cause reveals a missing, unclear, or too-weak project rule, add or update the relevant governance, testing, fixture, connector, or workflow documentation in the same change. If no governance change is needed, state why in the PR or handoff.

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
timestamp are visible, plain-language detail record summaries are visible, safe
source traceability fields and safe related seeded bundle context are visible,
sensitive narrative fields remain hidden, note/status forms delegate to the
existing workflow actions, read-after-write reviewer-created state appears in
the page, CCLD return navigation and record-specific feedback guidance are
visible, unauthenticated, disabled or revoked, role-denied, and out-of-scope
contexts are blocked with visible next steps, no-match search, missing-record,
and invalid note/status form states show clear accessible guidance,
source-derived rows are not mutated by UI actions,
reviewer-created state and audit rows are created only through the existing
services, and HTML does not expose secrets, tokens, cookies, private headers,
raw provider claims, private URLs, hosted URLs, credentials, or unnecessary
sensitive narrative content.
Hosted CCLD record request UI tests must prove the browser-accessible local/test
request page accepts only CCLD digit facility/license numbers plus optional
valid date ranges, returns accessible validation guidance for missing or invalid
requests, reads matching rows only from the seeded source-derived route seam,
can load or refresh matching CCLD rows from local validated hosted seeded-corpus
output through the existing source-derived import path, links matching seeded
complaint records into the hosted reviewer UI, shows a clear no-match and
external pipeline plan when local validated records do not match, renders a
guided facility/date-scoped request result queue with first-time workflow help,
contextual field/action help, source traceability summaries, reviewer-state
indicators, queue triage summaries, reviewer note/status cues,
source-traceability availability cues, suggested next-record links,
filtered-empty guidance, progress counts, reviewer-status filtering, meaningful reviewer
links, read-after-write queue updates after reviewer note/status actions, and
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
Hosted CCLD import/reload tests must prove local validated artifacts are
validated before load, source URL/raw SHA-256/raw path/connector traceability is
preserved, existing source-derived keys are refreshed without duplicates,
facility/date no-match requests defer without writes, and browser request paths
do not invoke live public web requests.
Hosted CCLD artifact builder tests must prove fixture-backed validated SQLite
output converts into deterministic hosted seeded-corpus JSON, validates through
the existing hosted seeded parser, preserves source-derived bundles and source
traceability, rejects missing or unsafe traceability fields, remains no-secret,
and is compatible with the existing hosted seeded import and CCLD import/reload
path without running live crawling or browser-triggered connector execution.

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
- Implementation work uses focused validation first, then standard PR validation before opening a PR.
- PR bodies include focused validation, why those focused checks matched the change, full local validation results, required remote check results, and any tests intentionally not run with the reason.
- Readiness, hardening, planning, and checklist PRs must also state the
	user-facing CCLD MVP capability, tester productivity improvement, or concrete
	MVP-blocking risk that justifies doing the work now. If that product-benefit
	case is weak, keep the item tracked as deferred readiness instead of making it
	the next branch.

## Validation tiers

### Focused validation

Run the smallest relevant tests for the changed area before broader validation.
Focused validation should catch likely failures quickly and should be explained in
the PR body or task handoff.

Use focused validation such as:

- Extraction changes: targeted extractor tests and related fixture regression tests.
- Connector changes: targeted connector discovery, fetch, and raw storage tests using fixtures or mocks.
- Data contract or schema changes: schema validation, init or migration SQL tests, persistence tests, and affected data dictionary checks.
- Datasette, view, or export changes: affected SQL, view, export, metadata, and documentation checks.
- Documentation-only changes: documentation validation and link or reference checks.
- Production-discovery requirements changes: documentation validation and affected documentation-check tests.
- Security or privacy changes: security checks and any affected tests.
- Accessibility-facing changes: documentation, export, view, or presentation accessibility checks.

### Standard PR validation

Run standard PR validation before every PR unless the change is analysis-only and
no files were edited:

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

### Required remote validation

Before merge, verify the required GitHub status-check contexts pass:

- `validate`
- `docs-check`
- `fixtures`
- `security`

### Full release validation

Run or verify the full test suite before any release, production-readiness
milestone, schema change, connector expansion, export-contract change, or
production architecture transition.

## Commands

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
git diff --check
```

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
