# Hosted UI Evidence Review

## Why Evidence Packets Exist

The hosted CCLD RecordsTracker UI changes quickly. Evidence packets give reviewers a repeatable way to inspect the same route set without relying on ad hoc screenshots, stale ports, or manually copied browser state.

Use an evidence packet after each hosted UI branch and before asking another reviewer or ChatGPT to evaluate the UI. The packet captures local UI route, screenshot, text, and accessibility evidence for review.

## What The Packet Captures

The capture command performs GET-only requests against an already-running local hosted app URL. It writes a timestamped folder under ignored `data/processed/ui-evidence/` with:

- `manifest.json` with mode, base URL, viewport, route status, discovered detail links, git state, screenshot status, diagnostic notices, and evidence purpose.
- `route-status.csv` with route status, title, first H1, and generated file paths.
- `route-assertions.csv` with pass/warn/fail checks for common UI review problems.
- `route-text-markers.txt` with titles, headings, buttons, and disclosure summaries.
- `html/` route HTML snapshots when routes respond.
- `text/` plain-text route summaries derived from HTML.
- `accessibility/` lightweight headings, links, forms, and landmark summaries.
- keyboard-flow marker assertions showing whether a route exposes visible
	keyboard-flow guidance for moving through the current hosted review step.
- a facility-hub route capture that exercises `/ccld/facilities/detail` as a
  GET-only per-facility review summary with Review next guidance and exact
  contributing-complaint access.
- Compare Facilities route captures that exercise
  `/ccld/facilities/intelligence` and its `Complaint Patterns`, `Licensing and
  Visit Activity`, and `Complaint Activity Over Time` views. They assert the
  approved heading, canonical complaint inventory, visible primary evidence,
  separate source domains, deterministic next actions, and legacy redirect
  compatibility.
- a matrix-export route capture that exercises `/reviewer/records/matrix.csv`
	as a GET-only CSV export over loaded local/test complaint records for the
	stable sample facility/date context.
- compatibility captures for `/ccld/facilities/review-priority`,
  `/reviewer/facilities/priorities`, and `/reviewer/facilities/trends`; each must
  resolve to the intended canonical view with supported query values preserved.
- `diagnostics/` git state, recent log, capture command, and non-secret capture settings.
- `screenshots/` route screenshots when local screenshot tooling is available.
- a sibling `.zip` packet after successful capture, suitable for local review
  or upload after the generated files have been checked for unexpected private
  values.

The packet never submits forms, triggers controlled retrieval, loads or imports data, mutates reviewer-created state, runs reset/reload, calls GitHub, performs production authentication, captures cookies, prints response headers, or records environment variable values.

## Reusable fixture capture plans

`scripts/capture-hosted-ui-evidence.ps1 -CapturePlanPath <repository JSON path>`
adds a reviewed, data-driven route plan without changing the default capture
behavior. A plan is restricted to a regular JSON file inside the repository and
must declare a purpose, `fixture-demo` data mode, explicit limitations, and one
or more named scenarios. Each scenario records its facility ID, classification,
expected location state, and applicable route assertions. A declared
`not-applicable` route requires a specific reason; it is never silently omitted.

Plans use `-Mode fixture` only. The capture command records the plan filename,
purpose, fixture mode, limitations, scenarios, route applicability, and visible
text assertions in `manifest.json`; no absolute local path is recorded. The
existing no-plan command continues to use the normal route set.

For example, the tracked Issue #647 plan is invoked with a local fixture URL:

```powershell
pwsh.exe -NoProfile -File scripts/capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -CapturePlanPath tests/fixtures/hosted_ui_evidence_capture/issue_647_location_capture_plan.json
```

## Evidence suitability, native interaction, and package integrity

Before a full evidence matrix, verify that the selected route loads, the
governed component is present, the smallest-scope fixture contains the required
term, control, state, or record, and fixture identity is recorded. No-data or
irrelevant states are not evidence for the intended component. Changing fixture
semantics or adding synthetic production-like data needs separate authorization.

Native interaction evidence requires actual browser input: pointer movement for
hover; keyboard navigation for focus; the Escape key for dismissal; and actual
navigation or movement to another legitimate control for focus loss. Mobile or
edge-placement evidence must use the intended viewport and route with the
governed component rendered. Forced CSS states, direct style changes, injected
classes, synthetic visibility toggles, and DOM-only manipulation may supplement
inspection but are not native interaction evidence.

Do not use a reduced viewport as a standing substitute for actual 200% browser
zoom. Issue #573 used a bounded human-approved reflow exception; future
exceptions require explicit human acceptance.

The capture tool creates the sibling ZIP when authorized. Before preservation or
cleanup, verify the ignored destination, manifest and file index, file list,
count and sizes, applicable zero-length and unexpected-file checks, ZIP
membership and integrity, and SHA-256. A technically complete package is not
human visual acceptance, and generated evidence remains ignored and untracked
unless a separate contract expressly requires otherwise.

`file-index.json` deterministically lists the packet files that precede it; the
subsequent ZIP validation includes the index itself, avoiding recursive index
or hash content.

## Fail-closed hosted acceptance record

Issue #648 separates evidence capture from acceptance. A packet, route summary,
or automation result must not use `PASS` as an overall hosted UI acceptance
decision until the versioned
`schemas/hosted-ui-acceptance-v1.schema.json` record passes
`scripts/validate_hosted_ui_acceptance.py`. The validator is offline,
read-only, deterministic, and computes these four independent gates:

| Gate | Passing condition |
|---|---|
| `STRUCTURAL` | The record is schema-valid, packet integrity is verified, every required artifact exists, and filesystem, ZIP, manifest, and reported artifact counts match exactly. |
| `FUNCTIONAL` | Route and functional assertion failures are zero, and every browser-console event and network failure has an explicit classification. Expected optional telemetry needs a named resource classification; it is not silently ignored. |
| `VISUAL` | Required viewport and state matrices are complete; every design requirement is classified; visual claims use screenshot, interaction, or print evidence; density and print ceilings pass; and a separate human independent-review artifact records `PASS` after reviewing every required screenshot and print artifact. |
| `OWNER_ACCEPTANCE` | A separate human owner-decision artifact records `PASS` and references the independent visual-review artifact. Automation cannot write or infer this decision. |

Overall acceptance is `PASS` only when all four computed gates are `PASS`.
`PENDING`, a missing record, a claimed/computed mismatch, or any one failed gate
produces `NOT_ACCEPTED`. Capture automation writes pending human-review
templates under `reviews/`, records `manifest.acceptance.overall` as
`NOT_ACCEPTED`, and prints `HOSTED_UI_ACCEPTANCE=NOT_ACCEPTED`. The templates
are not acceptance and automation must not populate their human identity,
conclusions, or decisions.

The only initial optional-telemetry resource classification is
`static.cloudflareinsights.com beacon.min.js`. It must be recorded with
`ALLOWLISTED_OPTIONAL_TELEMETRY`; a generic third-party, unknown-origin, or
different-resource label fails. Application and browser failures remain
separate classifications and cannot be relabeled as optional telemetry.

The state matrix contains exactly one entry for each of `DEFAULT`, `HOVER`,
`FOCUS`, `ACTIVE`, `DISABLED`, `EMPTY`, `LOADING`, `UNAVAILABLE`, `STRESS`,
and `PRINT`. A `PASS` row requires evidence. `NOT_APPLICABLE` requires a
specific rationale. `MISSING` and `REGRESSION` block the visual gate.

The viewport matrix contains desktop, narrow, mobile, and actual 200% zoom
captures. Reduced-width approximation does not satisfy the 200% entry. Each
applicable approved-design requirement is classified `PASS`, `VARIANCE`,
`REGRESSION`, or justified `NOT_APPLICABLE`. A variance passes only with a
separate human approval artifact. A regression always blocks acceptance.

DOM and text checks can prove structure or support a visual conclusion, but
cannot prove a visual requirement by themselves. At least one screenshot,
native interaction, or print artifact must support every visual assertion.
Independent review must enumerate every required viewport screenshot and print
artifact and record conclusions in a file separate from the owner decision.

Issue #648 establishes these acceptance ceilings for the Compare Facilities
stress case. They are blockers, not visual design targets and cannot be raised
inside an evidence record:

| Measurement | Maximum |
|---|---:|
| Desktop full-page height | 12 viewport heights |
| Narrow full-page height | 16 viewport heights |
| Mobile full-page height | 24 viewport heights |
| 200% zoom full-page height | 24 viewport heights |
| Inline contributing records | 25 records |
| Compare Facilities print output | 4 pages |

Print review also fails when interactive-only controls remain visible or
required reviewer content is clipped, hidden, duplicated, or reduced to an
unbounded complaint dump. These quantitative ceilings supplement the approved
compact-density, stress-content, responsive, state, accessibility, and
print-safe requirements; they do not authorize a poor layout that happens to
fit below a ceiling.

Acceptance records bind governance issue #648, parent issue #640, stakeholder
issue #419, the feature issue or issues under review, exact routes, deployed
SHA, packet SHA-256, and evidence freshness. Historical packets remain
immutable. Revalidation creates a new acceptance record with
`HISTORICAL_REVALIDATION`; it never edits the old packet or carries forward an
old `PASS`.

The sanitized negative derivative at
`tests/fixtures/hosted_ui_acceptance/issue-641-rejected-packet-v1.json` binds
the historical Issue #641 packet by SHA-256 and records its observed
71/71/68/76 artifact-count disagreement, 26 unclassified console events, 26
unclassified network failures, full-page heights of approximately 13.5, 32.5,
49.5, and 39.6 viewport heights, 75 inline contributing-record labels,
33-page print output, missing state evidence, design regressions, DOM/text-only
visual claims, and absent independent and owner decisions. The production
validator must reject that record even though it claims every gate and overall
acceptance as `PASS`.

## Issue #479 reviewer-facing visual acceptance contract

The following gate applies to every later reviewer-facing visual or interaction
implementation. General HTML-only evidence remains useful for route diagnostics,
but it cannot satisfy this gate. Every row is blocking until its required
evidence is present and reviewed.

| Gate ID | Rule family | Required evidence | Passing condition | Blocking result |
|---|---|---|---|---|
| `RT-UI-GATE-001` | `design-authority` | Exact approved Figma frame or approved artifact identifier, approval status, and applicable approved-design requirement IDs. | The implementation target and every applicable state map to an approved artifact. | `BLOCK` |
| `RT-UI-GATE-002` | `pre-code-variance` | Numbered page-change inventory plus a pre-code variance inventory identifying each intended difference and its approval. | No material variance is unexplained or unapproved before coding. | `BLOCK` |
| `RT-UI-GATE-003` | `primary-content` | Automated DOM and route assertions proving one canonical complaint inventory, unique stable complaint identities, meaningful source-backed labels, visible primary complaint content, and secondary-only disclosure use. | No accordion, `details`, collapsed card, tab, or disclosure widget hides primary allegations, findings, deficiencies, plans of correction, or supporting complaint records; no complaint inventory is duplicated. | `BLOCK` |
| `RT-UI-GATE-004` | `source-to-screen` | A field matrix covering source label, extractor, normalized field, canonical allocation, persistence, import or backfill, read model, rendered component, and production-style route evidence. | Every source-present field in scope reaches the expected screen or has an identified blocking layer. | `BLOCK` |
| `RT-UI-GATE-005` | `state-truthfulness` | Automated route evidence for populated, missing, unavailable, unsupported, invalid, and not-loaded states, plus any approved empty, partial, conflict, or error states. | Each state has distinct truthful wording and no application failure is presented as source omission. | `BLOCK` |
| `RT-UI-GATE-006` | `token-and-tlp` | Approved token mapping, rendered token evidence, contrast results, and text or accessible labels paired with every TLP semantic color. | The approved palette and token roles are used; no unapproved generic teal-primary fallback or color-only meaning appears. | `BLOCK` |
| `RT-UI-GATE-007` | `automated-route-capture` | Sanitized automated exact-route screenshots, capture manifest, route assertions, and approved-design references for every applicable desktop, narrow, compact/mobile, 200% zoom, focus, empty, partial, unavailable, error, and print state. | Screenshots exist for every applicable approved viewport and state and contain no private values or uncontrolled errors. | `BLOCK` |
| `RT-UI-GATE-008` | `accessibility-responsive` | Automated and tool-generated evidence for keyboard order, visible focus, headings, landmarks, tables, accessible names, contrast, non-color meaning, responsive reflow, and assistive-technology expectations. | No applicable accessibility or responsive requirement is failed, obscured, or left unevaluated. | `BLOCK` |
| `RT-UI-GATE-009` | `visual-acceptance` | Side-by-side approved-versus-rendered comparison and the requirement-ID report with `PASS`, `VARIANCE`, `REGRESSION`, or justified `NOT APPLICABLE` results, followed by an explicit acceptance decision. | Every regression is repaired, every variance is approved, and visual acceptance is explicitly recorded before merge. | `BLOCK` |

The later implementation handoff must include the table above with evidence
references filled in, not merely state that tests passed. Screenshot generation
and screenshot comparison must be automated; visual acceptance remains an
explicit reviewer decision based on that evidence.

Merging this governance foundation does not complete Issue #479. The issue may
close only after a later reviewer-facing implementation cites and satisfies this
contract with the required automated visual evidence and acceptance decision.

## Redesign evidence contract changes

For a material reviewer-facing redesign, apply
`../product/records-tracker-reviewer-redesign-artifact-governance.md` before
editing the active capture contract. Legacy route lists, headings, marker text,
and screenshot labels are current implementation assertions, not permanent
product requirements. Update them in the same dependent change that replaces
the route or presentation, while preserving exact-route coverage, unique useful
behavior, redirects or migrations, privacy checks, accessibility evidence,
truthful states, and every applicable visual gate.

Existing evidence packets remain historical evidence for the commit they
captured and must not be rewritten. Matching a superseded marker does not prove
the replacement design. The replacement packet must capture the canonical
route or view plus legacy redirect behavior and supported query or fragment
preservation where applicable.

## Port Convention

Use these ports for UI evidence review unless a task handoff says otherwise:

- `8003` = live public CCLD mode
- `8010` = fixture/mock demo mode
- Avoid relying on `8000` for UI review evidence unless the current branch or handoff explicitly says it is the active server.

Before starting a review server, clear stale local hosted processes when appropriate:

```powershell
foreach ($p in 8000,8003,8010) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } }
```

## Live Evidence

Start live mode in one terminal:

```powershell
.\scripts\run-hosted-complaint-retrieval-live.ps1 -Port 8003
```

Capture evidence from another terminal:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live
```

Live mode may make public CCLD HTTP requests only if a browser user submits a controlled retrieval form. The capture command itself is GET-only and does not submit retrieval.

For focused issue #416 facility-priorities evidence after the hosted app is
already running, capture only the required reviewer route states:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live -Issue416
```

For focused issue #418 complaint-trend evidence after the hosted app is already
running with the governed local records being reviewed:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live -Issue418
```

For issue #420, review the facility hub from both direct and intelligence-origin
contexts. The core packet captures the direct hub. Add these GET-only routes to
manual evidence review against the same running instance, substituting a known
loaded Facility ID when needed:

```text
/ccld/facilities/detail?facility_number=157806098
/ccld/facilities/detail?facility_number=157806098&origin=facility_intelligence&date_dimension=complaint_received_date&start_date=2022-04-01&end_date=2022-04-30
/ccld/facilities/detail?facility_number=999999999
/ccld/facilities/detail?facility_number=invalid
```

Review the loaded, filtered, filtered-empty, partial/unavailable-source,
reviewer-state-present, no-record, and invalid-ID states at 500 pixels and 200%
browser zoom. Confirm facility facts appear once, Review next stays above the
contributor disclosures, every aggregate reaches exact complaint links, focus
is visible, definitions work by keyboard, copy controls are named, and the page
has no page-level horizontal scrolling. True browser zoom and assistive-
technology behavior remain manual review items.

## Fixture/Mock Evidence

Start fixture/mock mode in one terminal:

```powershell
.\scripts\run-hosted-complaint-retrieval-demo.ps1 -Port 8010
```

When that command is run from a secondary worktree, pass the already verified
primary-repository Python executable with `-PythonExecutable`; the launcher
does not fall back to `python` from `PATH`.

Capture evidence from another terminal:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture
```

Fixture/mock mode uses committed fixtures and does not make live CCLD calls.

For the bounded Issue #610 Complaint Overview print correction, use the focused
fixture capture. It records the populated product-owner-rejected route with a
headers-off PDF and one source-unavailable comparison state; review every PDF
page for readable flow, no orphaned top content, no avoidable near-empty page,
and no clipped or visible interactive controls.

Focused issue #416 fixture evidence uses the same route set and assertions:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue416
```

## One-Command Convenience Wrapper

For local review, the wrapper can start one hosted mode and capture evidence after the root route responds:

```powershell
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -KillExistingPortProcess
```

In a secondary worktree, also pass the verified primary-repository Python
executable with `-PythonExecutable`. The wrapper records the launcher stdout
and stderr under its ignored evidence-output root if readiness fails.

The wrapper prints the URL, process ID, stop command, evidence packet path, and
evidence ZIP path. Use `-KillExistingPortProcess` only when you intentionally
want to stop the process currently listening on that port.

## Screenshot Support

The capture command tries to use local Playwright first when available, then local Microsoft Edge or Chrome headless capture. If no screenshot tool is available, the command still writes `manifest.json`, `route-status.csv`, HTML snapshots, text summaries, assertion rows, and accessibility summaries. Screenshot absence is reported in the manifest and command output. Such a packet may support nonvisual diagnostics, but it fails `RT-UI-GATE-007` for a reviewer-facing visual or interaction implementation.

For the Issue #419 controlled variance, start the local fixture server and run:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue419
```

The packet adds `issue-419-approved-versus-rendered.csv` and
`issue-419-ui-gates.csv`. Its route assertions also prove meaningful
source-backed licensing filters, removal of uploaded-summary implementation
language, public Facility ID presentation without internal stable identities as
facility names, approved Complaint Worklist wording, and preserved legacy
redirects. `RT-UI-GATE-009` remains
`PENDING_INDEPENDENT_VISUAL_REVIEW`; passing automation is not visual
acceptance, owner acceptance, or a claim that Figma was updated.

For the Issue #420 Facility Overview redesign, use:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue420
```

The focused packet captures populated desktop, original-report-unavailable and
reviewer-state filters, 1024px narrow desktop, 390px mobile, 720px reflow,
keyboard focus, filtered-empty, zero-complaint, missing-identity-value, and
print states. Partial coverage is verified on the populated desktop state, so
the packet intentionally does not create a duplicate partial-coverage image.
The print capture activates print media before producing the authoritative PDF,
then renders every PDF page for review. It adds
`issue-420-approved-versus-rendered.csv`,
`issue-420-source-reconciliation.csv`, `issue-420-ui-gates.csv`,
`issue-420-duplicate-images.json`, `issue-420-print-validation.json`, and
`diagnostics/issue-420-responsive-focus-measurements.json`. The assertions
require one default-visible complaint inventory, one primary next action,
truthful source/reviewer-state separation, preserved Facility Overview return
context, no primary disclosure stack, and compact state-specific retrieval
actions. `RT-UI-GATE-009` remains
`PENDING_INDEPENDENT_VISUAL_REVIEW`.

Do not add CI requirements for screenshot capture. Visual comparison screenshots remain outside CI because they depend on workstation browser tooling, but automated local evidence and explicit visual acceptance are still required before a reviewer-facing visual or interaction change can merge.

## Issue #502 evidence scope

Issue #502 captures Home desktop, narrow/mobile, and keyboard-focus states;
Facilities default, supported search, no-match, valid unmatched Facility ID,
malformed Facility ID, `Review Facility`, `Get Records`, limited/unavailable
reference, focus/viewport, back/forward, narrow/mobile, and 200%-reflow states;
and the shared-shell approved navigation/active states. The capture asserts
`RT-IA-004`, `RT-NAV-001`, and `RT-LANG-001`, plus `RT-UI-GATE-001` through
`RT-UI-GATE-009`. Automation records
`PENDING_INDEPENDENT_VISUAL_REVIEW`; it never records visual acceptance, owner
acceptance, or a Figma update.

For the 390px mobile, 720px reflow, and keyboard scenarios, Issue #502 uses an
interaction-aware browser capture. Responsive screenshots are full-page at the
governed viewport; the focused-results screenshot remains viewport-scoped so
the results position is visible. The packet records initial and final scroll,
viewport/client/document widths, horizontal-overflow status, landmarks,
focused-element geometry, focus-visible styling, and screenshot hashes in
`diagnostics/issue-502-responsive-measurements.json` and
`diagnostics/issue-502-focus-state-report.json`. Keyboard screenshots must
differ from their ordinary route screenshot hashes. This disclosure is required
when governed workflow boundaries change; it does not grant visual acceptance.

## Issue #503 evidence scope

Issue #503 captures `/ccld/help` at desktop, 1024-pixel narrow desktop,
390-pixel mobile, and a 720-pixel 200-percent-reflow approximation. Four direct
fragment routes prove copied category URLs. Interaction-aware routes prove
keyboard activation, representative child guidance, browser Back/Forward focus
continuity, invalid-fragment recovery, the permitted secondary disclosure, and
the shared official-term glossary. The print route produces a PDF and rendered
page images.

The packet adds `issue-503-route-fragment-inventory.csv`,
`issue-503-approved-versus-rendered.csv`, `issue-503-ui-gates.csv`,
`issue-503-print-validation.json`, and
`diagnostics/issue-503-responsive-fragment-focus-measurements.json`. Browser
capture fails if primary guidance is hidden, more than one disclosure exists,
a fragment target is missing, hidden, unfocused, or obscured, keyboard/history
state fails, or horizontal page overflow appears. Native browser zoom and
assistive-technology verification are not claimed. `RT-UI-GATE-009` remains
`PENDING_INDEPENDENT_VISUAL_REVIEW`.

## Uploading For Review

Upload or summarize the sibling ZIP created by the capture command, or the whole
timestamped folder under `data/processed/ui-evidence/`, not individual
screenshots. The point is to review the actual rendered UI, including labels,
links, buttons, screenshots, page text, and HTML, so exact tester instructions
can be written from what the site actually shows.

Evidence is not useful if no one reviews it. At minimum, include:

Upload or summarize the whole timestamped folder if you do not use the ZIP.

- `manifest.json`
- `route-status.csv`
- `route-assertions.csv`
- `route-text-markers.txt`
- `accessibility/`
- `html/` and `text/`
- `screenshots/` when available

Generated evidence is ignored locally and should be reviewed before sharing. Do not share packets that contain unexpected private values, raw source narrative, cookies, provider claims, tokens, private URLs, stack traces, connection strings, or server-specific private paths.

The capture command creates a sibling ZIP for every successful run and prints
both paths. When the hosted tester-readiness verifier is run with
`-IncludeCapture`, it also packages the generated timestamped evidence folder
into a sibling ZIP and prints both paths. The ZIP is a local UI review artifact
for route, screenshot, text, and accessibility review. After the packet is
reviewed for private values, the ZIP can be uploaded to ChatGPT or shared as a
convenience copy of the same local review artifact. Do not commit generated
evidence folders or ZIP packets unless a specific repository workflow explicitly
says to do so.

## Review Scope

The evidence packet is a lightweight UI review aid. It does not replace:

- accessibility audits or assistive-technology review;
- source traceability validation;
- extraction or schema tests;
- security review;
- production monitoring;
- audit exports;
- legal review;
- public-source completeness analysis.

It should help reviewers answer whether the current UI route surfaces are coherent, accessible enough for local review, mode-labeled correctly, and free of obvious stale-port, navigation, disclosure, and private-value problems.

## Packet preview / draft evidence route semantics

Evidence captures include explicit route labels for packet preview and draft variants to avoid ambiguity when context (facility/date) is missing:

- `packet-preview-empty`: A preview route capture made without facility/date query context. The UI must present explicit guidance (e.g., "No facility/date packet context was supplied.") and must not silently show "Date range: not provided" alongside included records.
- `packet-preview-context`: A preview route capture made with facility/date query context (stable seeded context). This route should list included records and render the date range.
- `packet-draft-empty`: A draft route capture made without facility/date query context. The UI must present explicit guidance and must not show "Date range: not provided".
- `packet-draft-context`: A draft route capture made with facility/date query context. Drafts intentionally hide the workflow rail for print/copy; evidence assertions should mark the draft workflow-step check as `PASS` with a message describing the intentional skip.

These route captures are route-level UI evidence for reviewing screen content, route behavior, and packet-preparation context. Review backend retrieval status and export persistence through the dedicated job, database, and operator evidence paths.

## Issue #642 evidence scope

Issue #642 captures the three Compare views, six-link mobile navigation, staged
typeahead and checkbox states, applied chips, pagination and return-context
round-trips, required responsive/native-zoom scenarios, keyboard focus, print,
console, network, and an approved-design variance matrix. Its packet follows the
Issue #648 four-gate contract: automation may satisfy structural and functional
evidence, while independent visual review and owner acceptance remain pending
human decisions. Do not add page-height, contributing-record-count, or
print-page-count ceilings to #642 evidence; those are #643 concerns.

Licensing evidence records populated, filtered-empty, and a separately launched
source-unavailable state, plus governed-directory searches by public ID, name,
and no-match text. Card geometry is not an Issue #642 evidence criterion.
