# Issue #643: Compare Facilities results-card implementation plan

## Planning boundary

- **Issue:** #643 — Simplify Compare Facilities results and canonical drill-down
  inventories.
- **Planning base:** `624c5f8a2932cab432270e255d8eeb6a2008996d`
  (`origin/main` and this worktree's `HEAD` at planning start).
- **Dependency state:** Issue #642 is complete and its accepted pull request #658
  was squash-merged. Its navigation, return-context, filter, pagination, and
  evidence work remains the controlling baseline. This issue owns only the
  Complaint Patterns result-card density, hierarchy, actions, and print/reflow
  correction.
- **This document is planning only.** It authorizes no application change, data
  projection, evidence recapture, commit, pull request, merge, deployment, or
  issue transition.

## Contract and baseline audit

The approved #643 contract applies only to the Complaint Patterns result list:

1. Replace the current five-column facility row with one responsive facility
   card.
2. Expose a selected facility as the sole **Review next** card; make its
   facility name a direct Facility Overview link, with a nearby copy control.
3. Keep the public Facility ID copy control, facility type, and geography in
   the card identity. Do not show source coverage in that identity.
4. Show a concise complaints summary, one recommended complaint, unique
   review-topic chips, source availability once, and a left-aligned wrapping
   action footer.
5. Preserve the complete exact-contributor inventory in the existing canonical
   Facility Overview inventory, not in every comparison card.

The prior accepted #642 fixture packet is a navigation/filter baseline, not a
card acceptance packet. Its populated desktop Complaint Patterns screenshot
shows the current five horizontal regions: identity, contributing-complaint
dump, source-record panel, reviewer-state form, and right-side actions. The
owner's #643 review recorded the resulting historical extent as 25 results at
16,180 px desktop, 41,000 px mobile, and 33 printed pages. Those measurements
are historical observations; they are not newly reproduced acceptance results.

The following areas remain explicitly out of scope:

- Licensing/Visit Activity and Complaint Activity Over Time;
- the in-place Review next carousel in #655;
- cross-site taxonomy and chip styling decisions in #656;
- bottom pagination in #657;
- filter, continuation, route-query, facility-overview return, source-derived
  ordering, reviewer-state persistence, or data-extraction changes except when
  a separately approved data prerequisite is necessary.

## Current contract inventory and disposition

| Current artifact | Current role | #643 disposition |
| --- | --- | --- |
| `reviewer_ui._render_facility_intelligence_results` | Owns the ordered result list. | Keep the list, result count, ordering, and continuation behavior; replace only each result's interior hierarchy. |
| `reviewer_ui._render_facility_intelligence_result` | Renders the five-column row and its selected-state label. | Rewrite as the single semantic facility card described below. Preserve selected-state determination and both current destination builders. |
| `reviewer_ui._render_facility_intelligence_orientation` | Renders the top result position and pagination controls. | Preserve unchanged. #657 exclusively owns bottom pagination. |
| `reviewer_ui._render_facility_intelligence_badges` and `_facility_intelligence_ordering_explanation` | Mix finding, delay, missing-date, anomaly, topic, and repeated aggregate wording. | Replace their card use with the approved concise summary. Do not add a 120+-day chip or rename/expand taxonomy. Remove “exact contributing complaint(s)” wording. |
| `reviewer_ui._render_facility_intelligence_source_region` | Per-card Source Record panel and raw-source action. | Remove from cards. Retain one source-availability fact in the recommended-complaint section; canonical source links remain in Facility Overview/detail. |
| `reviewer_ui._render_facility_intelligence_status_control` | Per-card mutable reviewer-status form. | Remove from cards. Preserve reviewer-created state in its canonical overview/detail workflow; never present it as source status. |
| `reviewer_ui._render_facility_intelligence_facility_contributors` and `_facility_intelligence_contributor_item` | Repeats every contributing complaint under each facility. | Remove from cards. Preserve the full exact list through the canonical Facility Overview inventory. |
| `reviewer_ui._facility_intelligence_hub_href` and `_facility_intelligence_detail_href` | Build Facility Overview and complaint-detail destinations while preserving Compare Facilities filters and return context. | Preserve. Reuse for all card actions and aggregate drill-down links. |
| `source_derived_reads._facility_intelligence_complaint_facts` | Supplies source-derived, deduplicated complaint/facility facts for the page. | Preserve its deterministic deduplication and source-derived semantics. Do not invent fields in rendering. |
| `ccld_facility_lookup._render_facility_complaint_inventory` | Existing canonical, filterable facility complaint inventory. | Keep as the only full contributor inventory and the destination for exact-supporting aggregate links. |
| `ui_shell.py` facility-intelligence and print rules | Defines the current five-column and print grid. | Replace only the Complaint Patterns row/card rules with single-card, reflow-safe and print-bounded rules. |

## Source-field provenance and data boundary

The implementation must continue to use only the current source-derived model:

| Card value | Current provenance | Required treatment |
| --- | --- | --- |
| Facility name, public Facility ID, type, geography | Facility values in `_facility_intelligence_complaint_facts`, with governed complaint fallbacks; carried in `FacilityPrioritySummary`. | Render the public identity only. Never expose internal `ccld:facility:*` values. |
| Complaint count | Stable complaint ID deduplication in `_facility_intelligence_complaint_facts` and summary rebuild. | Link the count to the Facility Overview's exact `all` canonical inventory. |
| Finding and finding counts | Source complaint `original_values.finding`, then current summary aggregation. | Keep source-derived finding semantics. Show the recommended complaint's finding once and do not repeat it in the summary finding-count list. |
| Latest relevant activity | Governed source activity-date dimension in `_facility_intelligence_complaint_facts`. | Display as a concise source-derived fact, never as an invented risk score. |
| Review topics | Existing `_facility_trend_serious_topics` output. | Deduplicate visible values only. Do not rename, broaden, recolor, or add delay chips; #656 owns taxonomy/styling decisions. |
| Recommended complaint number, activity date, finding, source availability | `FacilityPriorityComplaint`, selected deterministically by the existing priority ordering. | Show exactly one. Keep complaint and investigation status separate from findings when a governed source projection exists. |
| Reviewer status/note | Reviewer-created workflow state, not a source complaint/investigation status. | Do not use it as a source-status substitute and do not retain its editable form on the card. |

### Owner decision: status omission

The current `FacilityPriorityComplaint` and source-read projection contain a
finding but **no separately governed source-derived complaint or
investigation-status field**. The existing `Pending` fixture value is passed as
a finding and is not evidence of a governed status projection.

The owner resolved this planning gate: when that separate source-derived status
does not exist, the Complaint Patterns card **omits the status line**. #643 must
not infer, synthesize, calculate, or repurpose a status from a finding,
reviewer-created status, activity date, source availability, complaint age,
review topic, or missing data. In particular, `Substantiated` and
`Unsubstantiated` remain findings and must never be rendered as
complaint/investigation status.

#643 will not add a source-derived status projection. Issue #656 remains
responsible for inventorying and governing any real
complaint/investigation-status values and their cross-site presentation. If a
later governed field exists, it must remain visually and semantically separate
from findings.

## Recommended canonical drill-down

Use the existing Facility Overview route produced by
`_facility_intelligence_hub_href` as the sole full-contributor destination.
It carries the public facility number, `origin=facility_intelligence`, active
Compare Facilities query values, return semantics, and the canonical
`#facility-complaint-inventory` anchor. The facility overview's
`_render_facility_complaint_inventory` already renders one canonical record
inventory from `review_context.complaints`, with source/reviewer separation and
inventory filters.

Card aggregate links must therefore use that existing route and exact filter:

- total complaint count → `inventory_filter=all`;
- an additional finding count → `inventory_filter=finding:<value>`;
- a review-topic chip/count → its existing `inventory_filter=serious:<value>`.

The latest activity fact is not an aggregate drill-down control in this scope;
it remains plain source-derived text. A new date-specific inventory filter is
not warranted for #643 without a separate contract.

The card's **Open Facility Overview** action uses the same hub URL. **Review
complaint** uses the current deterministic detail URL and retains its return
context. This preserves the currently tested selected facility behavior without
creating a second complaint inventory or a new route.

## Approved card contract

Each result will be one `li > article` facility card, with no positional
right-side panel:

1. **Identity header** — show **Review next** only on the selected facility;
   an `h3` facility-name link to Facility Overview; adjacent full-name copy
   control; existing public Facility ID copy control; readable facility type;
   and geography. Source coverage is excluded here.
2. **Concise complaints summary** — label it **Complaints**. Show the exact
   linked total, non-duplicative additional finding counts, and latest relevant
   activity. Do not repeat a recommended finding in this summary. Do not use
   “exact” or “stable facility identity” copy.
3. **Review topics** — unique visible current topic values only, in a compact
   chip list. The implementation may deduplicate but may not introduce the
   deferred 120+-day chip, new taxonomy, or #656 color decisions.
4. **Recommended complaint** — one deterministic complaint with public number,
   relevant activity date, and one finding. Omit complaint/investigation status
   unless a later separately governed source-derived field is available; never
   derive it from the finding or reviewer state. Show source availability once
   here, with unavailable wording distinct from a filtered-empty result.
5. **Action footer** — left-aligned **Open Facility Overview** and **Review
   complaint** links. It wraps and stacks naturally at narrow widths; it is not
   absolutely positioned and does not become a sidebar.

The complete contributor list, raw source destination panel, and editable
reviewer-state form are deliberately absent from the comparison card. Their
removal changes presentation only: source links and reviewer workflow remain in
the canonical Facility Overview/detail destinations.

## Removal and de-duplication matrix

| Current repeated/competing content | Card disposition | Preserved authoritative location |
| --- | --- | --- |
| Every contributing complaint and its repeated facts | Remove. | Facility Overview canonical complaint inventory. |
| `N contributing complaints` explanation, repeated count/date/finding text | Replace with the single **Complaints** summary and one recommended complaint. | Exact count membership via canonical inventory filters. |
| Recommended finding repeated as summary/badge/contributor text | Show once in the recommended complaint; omit that finding from additional summary counts. | Canonical inventory retains all source facts. |
| Source Record panel and raw-source action | Remove from card. | Facility Overview/detail source region; one card source-availability fact only. |
| Per-card reviewer state form | Remove from card. | Existing canonical reviewer detail/overview workflow. |
| Delay, missing-date, anomaly, and broad badge mixture | Do not make them card chips in #643. | Existing data/order semantics remain untouched; #656 governs chip taxonomy/styling. |
| Plain facility-name heading | Replace with accessible Facility Overview link plus separate copy control. | Existing hub route/query and return context. |

## Responsive, print, accessibility, and evidence plan

The CSS implementation must use a one-column card flow with `min-width: 0`,
wrapping text/actions, and no fixed five-column grid. It must meet the existing
reviewer requirements at desktop, 390 px narrow mobile, native 200% zoom, and
print:

- no horizontal overflow, clipped controls, overlapping action footer, or
  reliance on color alone;
- keyboard-reachable facility, aggregate, overview, detail, and copy controls,
  with visible focus and meaningful labels;
- heading/list semantics that expose one facility result and one recommended
  complaint without repeating the full inventory;
- print retains the facility identity and concise source-derived facts while
  suppressing controls that cannot operate on paper; it must not preserve a
  multi-column row or create a page-count target.

A later, separately authorized HV-READ evidence phase must capture a populated
fixture packet with route/assertion output, console/network summary, desktop,
narrow, native-200%, keyboard/focus, and print screenshots. It must inspect a
populated card; #642's filtered-empty responsive screenshots cannot establish
#643's card reflow. It must also record the canonical Facility Overview
destination and filtered exact-contributor inventory for a count, finding, and
topic. No independent visual review or owner acceptance is created by that
packet.

## Implementation and regression plan

After the status prerequisite is resolved, implementation is limited to these
phases:

1. **Contract tests first.** Add/update focused unit and request-level tests
   for one card hierarchy, selected-only Review next, accessible Facility
   Overview name link/copy controls, public IDs only, exact hub/filter URLs,
   one recommended complaint, absence of contributor/source-panel/reviewer-form
   duplication, unique current topics, source-unavailable distinction, and
   preserved deterministic continuation/return behavior.
2. **Renderer and CSS.** Make the minimal changes in `reviewer_ui.py` and
   `ui_shell.py`; do not change source reads, filters, pagination placement, or
   other Compare Facilities views.
3. **Focused validation.** Run new independent tests; affected hosted facility
   priority/Facility Overview tests; targeted Ruff and mypy; documentation
   validation when governed documentation changes; and `git diff --check`.
4. **Evidence only under separate authorization.** Start a fixture runtime,
   produce new timestamped packets without overwriting prior packets, reconcile
   all artifact counts, and inspect the populated screenshots.
5. **Lifecycle only under separate authorization.** Commit, push, PR, review,
   merge, and any issue transition are separate phases and remain prohibited.

## Planning-gate validation record (2026-08-01)

The documented secondary-worktree convention was verified: use the primary
repository virtual-environment interpreter with this worktree as the current
directory. The verified executable is
`<primary-repository-path>\.venv\Scripts\python.exe`. It imported `pytest
9.1.1` and `jsonschema 4.26.0`.

The primary `pytest.exe` launcher is present but a OneDrive reparse point. In
the Codex sandbox it fails before test collection with `Access is denied` while
attempting to launch its configured `python.exe`. That is an execution-context
restriction, not a test result, malformed command, missing file, or a request
to create a worktree-local environment. The verified direct interpreter command
below avoids the wrapper and passed all eight focused current-behavior tests:

```powershell
$primaryRepository = '<primary-repository-path>'
& "$primaryRepository\.venv\Scripts\python.exe" -m pytest `
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_filters_reconciles_and_preserves_drilldown_context' `
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_accessible_structure_and_safe_language' `
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_binds_source_and_reviewer_actions_to_next_complaint' `
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_distinguishes_verified_zero_and_unavailable_values' `
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_uses_public_identity_fallback_for_missing_name' `
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_continuations_preserve_filters_and_reject_bad_state' `
  'tests/unit/test_hosted_facility_priorities.py::test_facility_hub_reuses_intelligence_aggregates_state_and_tie_order' `
  'tests/unit/test_hosted_ccld_facility_lookup.py::test_ccld_facility_review_hub_has_one_deterministic_primary_next_action' -q
```

Result: `8 passed in 5.17s`. Together these establish the present facility-row
rendering, Facility Overview and complaint-detail destinations, canonical
inventory and aggregate reconciliation, deterministic recommended selection,
source-derived/reviewer-created separation, finding/topic behavior, return
context, and the existing print/responsive CSS contract. They are a baseline,
not acceptance of the superseded card hierarchy.

The documented documentation command is `.\scripts\docs.ps1`. In a secondary
worktree it first looks for a worktree-local `.venv\Scripts\python.exe` and
otherwise invokes `python` from `PATH`; this worktree deliberately has no local
environment and the clean PowerShell process has no `python` command. The
command therefore exits 1 instead of validating. The underlying documented
validator was run through the verified primary interpreter:

```powershell
$primaryRepository = '<primary-repository-path>'
& "$primaryRepository\.venv\Scripts\python.exe" scripts\check_docs.py
```

Result: `Documentation check passed.` with exit code 0. The validator correctly
returns nonzero for evidence-policy violations, so no exit-code masking defect
was established. No validation-tooling file changed: the direct primary-runtime
command resolves the documented dependency without changing #643 scope.

## Remaining owner decisions

No Issue #643 owner decision remains unresolved for this planning gate. The
status decision is resolved above. The card will reuse the current
`serious_topics` text only with visible-value deduplication and will make no
taxonomy, color, or cross-site status presentation decision; those boundaries
remain with #656. The existing Facility Overview route is the approved
canonical-inventory destination described by the #643 contract, so no new route
decision is required.

## Planning stop point

This plan stops before behavior changes. The #643 worktree remains an
uncommitted planning worktree on
`codex/issue-643-compare-facilities-result-cards`; no lifecycle, deployment,
evidence-generation, cleanup, or other issue work is authorized by this plan.

## Implementation and evidence update (2026-08-01)

The approved card renderer, responsive/print CSS, focused route contracts, and
user documentation are implemented in the uncommitted #643 worktree. The
focused hosted facility-priority and Facility Overview collections passed
`132` tests before the final ordering-copy correction; the focused card route
test and targeted Ruff passed after that correction. The primary interpreter
was used throughout.

A timestamped generic local fixture packet was retained at
`data/processed/ui-evidence/20260802-024021Z-fixture`. It confirms the default
Complaint Patterns route renders the new card hierarchy, but it is not a #643
acceptance packet: generic capture reported unrelated legacy route assertions
and did not provide the required dedicated populated/source-unavailable,
keyboard, native-200%, print, or canonical-drill-down scenarios. A dedicated
#643 evidence mode remains required before owner review. No independent visual
review or owner acceptance has been created.
