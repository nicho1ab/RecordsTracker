# Issue #419 Cross-Facility Consolidation Evidence

Status: repository implementation complete; visual, hosted, representative-data,
and stakeholder acceptance pending.

Authority: Issue #501 repository-readable controlled variance and Issue #504
artifact-governance model. This record does not claim that Figma was updated.

## Approved outcome

- Navigation: `Compare Facilities`.
- Canonical route: `/ccld/facilities/intelligence`.
- H1: `Find Facilities That May Need Closer Review`.
- Purpose: compare complaint findings, activity, patterns, licensing and visit
  activity, and available public records to decide where to review first.
- Views: `Complaint Patterns`, `Licensing and Visit Activity`, and `Complaint
  Activity Over Time` as ordinary links, not tabs.
- Primary comparison evidence remains visible without an accordion, `details`,
  collapsed card, or disclosure widget.

## Pre-code route and behavior inventory

| Surface | Unique behavior before consolidation | Variance | Disposition |
|---|---|---|---|
| `/ccld/facilities/intelligence` | Authorization-before-read, governed PostgreSQL read model, stable complaint deduplication, keyset pagination, deterministic factors and ties, count reconciliation, combined filters, complaint/facility drill-downs, source/reviewer-state separation | Route was canonical but name and primary-evidence disclosure differed from #501 | Preserve behavior; rewrite presentation |
| `/ccld/facilities/review-priority` | Uploaded-summary search, deterministic cue order, 100-row bound, licensing status, capacity, visit, citation, and Plan of Correction observations, source-domain separation | Separate attorney destination, legacy heading, operator diagnostics in reviewer output | Move to `Licensing and Visit Activity`; remove reviewer diagnostics; redirect |
| `/reviewer/facilities/priorities` | Complaint-derived minimum-count and indicator filters, visible no-hidden-score rules, bounded pagination, queue/detail/source links | Duplicate facility inventory and legacy terminology | Preserve as an unpromoted compatibility view under the canonical route; redirect legacy URL |
| `/reviewer/facilities/trends` | Monthly/quarterly grouping, bounded period count, coverage and missing-date states, deterministic anomaly cues, exact contributing complaints | Separate reviewer destination and legacy heading | Move to `Complaint Activity Over Time`; redirect legacy URL |
| Complaint CSV, matrix CSV, substantiated/serious-topic outputs, and facility-scoped exports | Existing filter, filename, review-cue, and matrix-separation contracts | No approved export change | Preserve unchanged |

## Pre-code controlled-variance inventory

| Requirement | Before | Required correction |
|---|---|---|
| Canonical naming | `Cross-facility intelligence`, `Facility review priority`, and `Facility review priorities` remained visible | Use approved navigation/H1 and plain-language view names |
| One facility inventory | Three reviewer-facing facility inventories existed | Keep one canonical route and redirect old URLs after parity |
| Licensing/visit source | Useful public-summary behavior lived on a separate route | Preserve it as a clearly separated canonical view |
| Complaint trends | Trend renderer lived on a separate route | Preserve it as a contextual canonical view |
| Primary evidence | Exact contributing complaint records and licensing guidance used `details` | Render primary evidence in visible semantic sections |
| Reviewer tier | Licensing summary exposed loaded/unsupported/malformed source counts | Keep diagnostics out of reviewer output without changing the loader result |
| Navigation | No `Compare Facilities` global destination | Add the approved label and active-state boundary; leave full #502 navigation redesign untouched |
| State evidence | Existing state renderers lacked one Issue #419 evidence matrix | Add controlled fixture-only loading/not-loaded/unavailable/limited/error capture states; production contexts ignore that query |
| Visual evidence | No consolidated exact-route packet or gate report | Add governed `-Issue419` capture, comparison CSV, and gate CSV |

## Focused reviewer-language correction

The final repository pass replaces implementation-centric reviewer language
without changing data selection or route behavior:

- `facility hub` and `Facility Review Hub` become `Facility Overview`.
- `Detailed priority table` becomes `Licensing and visit activity by facility`.
- uploaded-summary field, signal, and review-cue wording becomes supported public
  licensing, visit, citation, Plan of Correction, status, capacity, or
  source-availability observations.
- Issue #419 queue actions use `Complaint Worklist`.
- a missing source-backed facility name renders as `Facility name unavailable`,
  with the public Facility ID shown separately. Internal `ccld-facility-*` and
  `ccld:facility:*` identities remain available only to backend routing,
  reconciliation, and test logic.

The licensing filters retain their existing internal query values and map them
to the following reviewer-facing conditions:

| Existing internal cue value | Reviewer-facing filter label |
|---|---|
| `all` | `All supported observations` |
| `Multiple signal types present` | `Multiple supported observations` |
| `Complaint visit activity present` | `Complaint-related visit activity` |
| `Citation indicator present` | `Citation activity` |
| `POC indicator present` | `Plan of Correction activity` |
| `Recent visit activity` | `Recent visit activity` |
| `High-capacity facility` | `Capacity of 50 or more` |
| `Closed status in uploaded summary` | `Closed licensing status` |
| `Long gap since last visit` | `Last recorded visit before 2023` |

No global-navigation or Help change is part of this correction. The previously
suspected 200% and print blank-region defects were not reproducible in the
approved local fixture review, so no responsive or print behavior was changed.

## Artifact classification

| Artifact | Class | Action | Reason |
|---|---|---|---|
| Authorization-before-read and operator/reviewer separation tests | Security/data invariant | Preserve | Not presentation scaffolding |
| PostgreSQL query, 25-row keyset pagination, stable identity, deduplication, deterministic order, and reconciliation tests | Data invariant | Preserve | Proves trustworthy large-corpus behavior |
| Reviewer-created note/status isolation | State invariant | Preserve | Source-derived and reviewer-created data remain separate |
| Existing complaint CSV and matrix export assertions | Export invariant | Preserve | Consolidation does not authorize export changes |
| Old headings, helper copy, active-nav expectations, and route-specific presentation strings | Superseded presentation | Rewrite | #501 supplies approved terminology and IA |
| `details` assertions for contributing complaint records or licensing guidance | Superseded interaction | Remove/rewrite | Primary comparison evidence must be visible |
| Separate legacy destination route contracts | Superseded route | Rewrite | Test query-preserving 302 compatibility instead |
| PR #488 implementation record and earlier changelog entries | Historical evidence | Historical only | Preserve project history; do not treat as current UI authority |
| Operator summary-source counts | Operator/support diagnostic | Remove from reviewer rendering; preserve underlying data | Reviewer tier must not expose ingestion mechanics |

## Post-code route contract

| Request | Result |
|---|---|
| `/ccld/facilities/intelligence` | Canonical `Complaint Patterns` experience |
| `/ccld/facilities/intelligence?view=licensing-visit-activity` | `Licensing and Visit Activity` |
| `/ccld/facilities/intelligence?view=complaint-activity-over-time` | `Complaint Activity Over Time` |
| `/ccld/facilities/intelligence?view=complaint-priority-compatibility` | Preserved legacy complaint-priority filter/paging semantics inside the canonical destination; not promoted as a fourth navigation view |
| `/ccld/facilities/review-priority?...` | 302 to licensing/visit view with supported query values preserved |
| `/reviewer/facilities/priorities?...` | 302 to compatibility view with supported query values preserved |
| `/reviewer/facilities/trends?...` | 302 to complaint-activity view with supported query values preserved |
| Unsupported `view` | 400 with canonical shell and recovery action |

Redirect selection occurs before route data access. The actual HTTP handler adds
the `Location` header; the pure route response retains a deterministic 302 body
for unit tests.

## Source-to-screen and state matrix

| Source or state | Governed processing | Rendered result |
|---|---|---|
| Authorized loaded complaint records | Stable identity deduplication, complaint filters, governed factors, deterministic tie order, keyset page | One facility row with visible reasons and visible exact contributing complaint links |
| Original public-report availability | Existing aggregate coverage semantics | Available, partial, or unavailable text plus record-specific action state |
| Reviewer-created note/status | Separate read model keyed to stable complaint context | Separate reviewer-state region; never used as a source-derived factor |
| Supported public licensing/visit observations | Existing safe scalar parser, cue ordering, search, and 100-row bound | Separate Licensing and Visit Activity view with meaningful condition labels; no complaint-coverage claim |
| Trend complaint records | Existing monthly/quarterly grouping and anomaly rules | Complaint Activity Over Time table with direct contributing-record links |
| Filtered empty | Authorized query returns no matching facility rows | `No facilities match these filters` and clear-filter recovery |
| Source unavailable | Controlled fixture-only visual state | `Complaint source links are unavailable`; no source-backed action claim |
| Limited data | Real loaded rows plus controlled fixture-only state marker | Warning that the subset is not statewide completeness |
| Invalid dates/view | Validation before the read or unsupported view dispatch | 400, visible alert, and canonical recovery |
| Not loaded | No authorized loaded complaint records | Explicit not-loaded wording and facility/request recovery |
| Application error | Controlled fixture-only visual state | 503, alert semantics, feedback link, and Try Again action |

The fixture-only `evidence_state` control is enabled only in the local test
context. Production-style contexts ignore it and retain the existing data-read
and failure behavior.

## Accessibility, responsive, and print contract

- One primary-navigation current-page state and one view-link current-page state.
- Labeled filters, semantic headings/tables, record-specific accessible names,
  skip link, non-color-only status text, and deterministic fragment focus.
- Exact-route captures at 1440 x 1200, 1024 x 900, 390 x 844, and 720 x 600
  (the governed 200% reflow approximation).
- Primary comparison evidence is visible at every supported width; wrapping and
  responsive grids prevent page-level horizontal scrolling.
- Print removes navigation and interactive filters while retaining evidence.
- The 720 px capture is an approximation, not a claim of true browser zoom.

## Automated evidence contract

Run from a local fixture server:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 `
  -BaseUrl http://127.0.0.1:8010 `
  -Mode fixture `
  -Issue419
```

The ignored packet contains 17 governed routes, sanitized HTML/text,
accessibility inventories, exact-route screenshots, a print PDF when the local
browser supports it, `issue-419-approved-versus-rendered.csv`, and
`issue-419-ui-gates.csv`. Route assertions prove meaningful licensing filters,
absence of reviewer-visible uploaded-summary mechanics, public facility identity
presentation, Complaint Worklist wording, and the preserved redirects. It
submits no form and performs no retrieval, import, reviewer-state, database, or
hosted mutation.

The focused correction capture produced:

- folder: `data/processed/ui-evidence/20260721-032129Z-fixture-issue-419`;
- ZIP: `data/processed/ui-evidence/20260721-032129Z-fixture-issue-419.zip`;
- ZIP SHA-256:
  `9188FC5F86840415D2F68AE543FFC94499E9CAD67837CD14F4F47C7A43B6E489`;
- 17 of 17 expected route outcomes, 314 assertions with zero failures, 17
  screenshots, 17 sanitized HTML files, 17 text summaries, 4 accessibility
  inventories, and 1 print PDF;
- 11 approved-versus-rendered comparison rows with no failure or regression;
  and
- `RT-UI-GATE-001` through `RT-UI-GATE-008` recorded as `PASS`, with
  `RT-UI-GATE-009` still `READY FOR EXPLICIT OWNER REVIEW`.

The three legacy evidence scenarios resolve to the intended canonical views.
Focused route tests separately prove each original request returns 302 before
data access and preserves its supported query parameters.

## RT-UI-GATE disposition

| Gate | Repository disposition |
|---|---|
| `RT-UI-GATE-001` design authority | Issue #501 controlled variance identified; no Figma-change claim |
| `RT-UI-GATE-002` pre-code variance | This document records the route, behavior, and artifact inventory |
| `RT-UI-GATE-003` primary content | DOM assertions require visible primary evidence and one canonical inventory |
| `RT-UI-GATE-004` source-to-screen | Source/domain/state matrix and direct stable-record actions are tested |
| `RT-UI-GATE-005` state truthfulness | Populated, filtered-empty, unavailable, limited, invalid, not-loaded, and error routes are captured |
| `RT-UI-GATE-006` token and TLP | Shared approved tokens and text-backed semantic states are retained |
| `RT-UI-GATE-007` automated route capture | Governed screenshots and manifest are required for applicable routes/states |
| `RT-UI-GATE-008` accessibility/responsive | Focus, semantic, responsive, no-disclosure, and print checks are required |
| `RT-UI-GATE-009` visual acceptance | `READY FOR EXPLICIT OWNER REVIEW`; automation is not acceptance |

## Preserved boundaries and remaining gates

No connector, field precedence, schema, ingestion, authentication, export,
reviewer-state mutation, deployment, QNAP, Cloudflare, or Hosted configuration
changes are part of this consolidation. No hidden score or legal/facility-wide
conclusion is introduced.

Issue #419 remains open after repository merge. Closure still requires:

1. automated hosted evidence on the merged/deployed build;
2. representative real-data count reconciliation;
3. duplicate and synthetic/tiny-fallback exclusion checks in production style;
4. explicit visual acceptance; and
5. stakeholder confirmation.
