# Hosted Reviewer Acceptance

## Purpose

Use this checklist to validate the hosted local/test CCLD review loop as one
tester-readiness acceptance path. The path is intended for early local operators
and reviewers who need repeatable evidence that the current route set is
reachable, exposes expected workflow markers, preserves packet preview/draft
checks, and can produce a local review evidence packet without relying on ad hoc
manual inspection.

The acceptance verifier is non-mutating by default. It performs GET checks and
optionally runs GET-only evidence capture. Write checks require explicit
`-RunWriteChecks` and should be used only against a safe local test or staging instance where transient reviewer-created state is acceptable.

## Ports

Use these local ports unless a task handoff says otherwise:

- Fixture/mock: `http://127.0.0.1:8010`
- Live: `http://127.0.0.1:8003`

Fixture/mock mode uses committed fixtures and does not make live CCLD calls.
Live mode can make public CCLD HTTP requests only when a browser user submits a
controlled retrieval form; the verifier and evidence capture commands are
GET-only and do not submit retrieval jobs.

## Sample Context

The verifier uses this stable local/test context by default:

- Manual complaint request value: `157806098`
- Known loaded preloaded facility-directory example: `434417302`
- Date range: `2026-01-01` to `2026-01-31`
- Request context origin: `manual_entry`
- Sample source record key: `complaint:ccld:complaint:32-CR-20220407124448`

## Commands

Before starting a local server, clear stale hosted processes when appropriate:

```powershell
foreach ($p in 8000,8003,8010) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } }
```

Start fixture/mock mode in one terminal:

```powershell
.\scripts\run-hosted-complaint-retrieval-demo.ps1 -Port 8010
```

Run the non-mutating tester-readiness acceptance check from another terminal:

```powershell
.\scripts\verify-hosted-reviewer-acceptance.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -IncludeCapture
```

For live GET-only validation, start live mode in one terminal:

```powershell
.\scripts\run-hosted-complaint-retrieval-live.ps1 -Port 8003
```

Then run:

```powershell
.\scripts\verify-hosted-reviewer-acceptance.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live -IncludeCapture
```

## Route Set Checked

The acceptance verifier checks the primary hosted workflow routes with GET
requests and stable tester-readiness markers:

- `home-start`: `/`
- `ccld-start`: `/ccld/`
- `facility-lookup`: `/ccld/facilities`
- `facility-priority`: `/ccld/facilities/review-priority`
- `facility-intelligence`: `/ccld/facilities/intelligence`
- `facility-hub`: `/ccld/facilities/detail?facility_number=434417302`
- `record-request`: `/ccld/records/request`
- `record-request-context`: `/ccld/records/request?facility_number=157806098&start_date=2026-01-01&end_date=2026-01-31&request_context_origin=manual_entry`
- `reviewer`: `/reviewer`
- `reviewer-records`: `/reviewer/records`
- `matrix-export`: `/reviewer/records/matrix.csv` with the sample request context
- `reviewer-detail`: `/reviewer/records/detail` with the sample source record key and request context
- `packet-preview-empty`: `/reviewer/packet/preview`
- `packet-preview-context`: `/reviewer/packet/preview` with the sample request context
- `packet-draft-empty`: `/reviewer/packet/draft`
- `packet-draft-context`: `/reviewer/packet/draft` with the sample request context
- `feedback`: `/feedback`
- `help`: `/ccld/help`

The packet empty/context checks remain part of acceptance. Empty packet routes
must show explicit missing-context guidance and must not show the passive label
`Date range: not provided`. Context packet routes must keep browser copy or
print preparation guidance, review-readiness wording, feedback handoff, and the
source/legal/export review routing.

When `-IncludeCapture` is supplied, the verifier runs
`capture-hosted-ui-evidence.ps1`, confirms packet preview/draft route assertion
rows are present, confirms packet draft workflow-step assertions pass with the
intentional print/copy layout skip, and prints both:

- Evidence folder path
- Evidence ZIP path

The ZIP is a local UI review artifact under ignored `data/processed/ui-evidence/`
for route, screenshot, text, and accessibility review.

## What This Proves

A passing acceptance run proves that the hosted local/test workflow exposes a
repeatable tester-readiness path across Home, Facility Lookup, Facility Hub,
Facility Review Priority, Facility Review Intelligence, Request, Queue, Matrix
CSV Export, Detail, Packet Preview, Packet Draft, Feedback, Help, and evidence capture. It also
proves that the checked pages expose key visible markers for route reachability,
review queue continuity, complaint review workspace access, packet preparation,
feedback, help, local/test context, and source traceability availability.

The run also proves that default checks avoid persistent writes: no forms are
submitted, no retrieval job is submitted, no import/reload is run, no feedback is
submitted, and no reviewer-created state write is attempted unless a separate
safe test/staging run explicitly chooses write checks.

The route marker checks also look for visible page-level orientation on the
main hosted workflow pages, including route headings, shared skip links, active
navigation, and the existing control or link that moves the review forward.

## Review Routing

Use dedicated source, legal, production monitoring, production authentication,
export persistence, audit export, and final packet lifecycle paths for those
reviews.

The public CCLD portal remains the source of record. Source-derived values are
review aids. Reviewer-created status/note cues remain separate from
source-derived records.

## Optional Write Checks

Default acceptance should not run write checks. If exploratory reviewer-created
state checks are explicitly requested, run them only on a safe local test or staging instance:

```powershell
.\scripts\verify-hosted-reviewer-acceptance.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -RunWriteChecks
```

The current verifier reports when `-RunWriteChecks` is requested but keeps the
default route and capture checks GET-based. Do not use write checks against a
shared, production-like, or reviewer-facing instance unless the operator has
explicitly approved transient reviewer-created state.
