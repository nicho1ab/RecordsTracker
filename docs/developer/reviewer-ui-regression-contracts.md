# Reviewer UI regression contracts

Issue #608 records bounded, outcome-based reviewer UI regression contracts. It
implements Issue #504 anti-fossilization governance: durable outcomes and
protected invariants remain governed, while approved presentation changes may
supersede layout, control type, and optional wording.

Status vocabulary:

- **Documented**: the outcome is governed here, but no dedicated executable
  contract currently proves it.
- **Partially enforced**: existing focused checks prove a bounded portion of
  the outcome, while a named adoption is still materially missing.
- **Enforced**: the listed current executable checks cover the stated bounded
  outcome at the current base.

| Contract ID | Status | Durable outcome and protected invariant | Supersedable presentation details | Owning issue | Representative routes or states | Current executable checks | Planned checks not yet implemented | Update and retirement rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `RT-RC-001` | Enforced | A reviewer action reaches a usable authorized destination with supported context; destination and authorization integrity remain protected. | Link label, placement, icon, and action-group layout. | #608; consumed or extended by #419, #420, #502, #503, and #610. | Complaint detail, retained-search worklist return, source action, combined reviewer-update states, Help task destinations, Compare Facilities drill-down, and Facility Overview Review next. | `tests/unit/reviewer_ui_contracts.py::assert_destinations`; `tests/unit/test_reviewer_ui_contract_routes.py`; `tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_binds_source_and_reviewer_actions_to_next_complaint`; `tests/unit/test_hosted_ccld_facility_lookup.py::test_ccld_facility_review_hub_has_one_deterministic_primary_next_action`; Issue #610 and #503 route checks. | No material adoption gap in the listed representative routes; exact hosted evidence remains owned by the applicable issue. | Update with an approved route replacement; supersede/retire only with replacement redirect/context evidence. |
| `RT-RC-002` | Enforced | Reviewer routes exclude operator controls, runtime commands, and raw diagnostics from the attorney tier. | Page grouping, wording, and control styling. | #608; consumed or extended by #420, #502, #503, and #610. | Representative safe reviewer fixture, Facility Overview, and attorney Help. | `assert_information_tier`; foundation test; `tests/unit/test_hosted_ccld_facility_lookup.py::test_ccld_facility_review_hub_keeps_source_dataset_filename_outside_primary_page`; Issue #503 prohibited-content route and evidence assertions. | No material adoption gap in the listed representative routes. | Update only with a governed information-tier decision; never retire the tier boundary. |
| `RT-RC-003` | Enforced | One help treatment is active per dense reviewer context; pointer, keyboard, and touch access do not create duplicate native or ARIA descriptions; dismissal, focus restoration, adjacent triggers, and viewport containment remain predictable. | Trigger wording, icon, above/below placement, and help panel layout. | #608; consumed and extended by #606; consumed by #503 | Shared glossary component, Compare Facilities, Complaint Overview repeated missing-value states, and attorney Help official terms. | `assert_help_surface`; foundation and shared-shell component checks; representative route tests; Issue #503 glossary structure and keyboard evidence. | No gap in the bounded component/route contract; a future approved visual redesign supplies its own replacement visual evidence. | Retire obsolete presentation assertions only through #504 classification and an approved replacement. |
| `RT-RC-004` | Enforced | Facility identity remains consistent within a current tested state; explicit historical, conflict, and unavailable states remain distinguishable. | Identity wording and card/table arrangement. | #608; consumed or extended by #419, #420, and #610. | Complaint Overview complete, partial, unavailable, and current-reference-conflict identity states; Compare Facilities public-identity fallback; Facility Overview missing identity; representative cross-surface identity state. | `assert_facility_identity`; fixture-integrity test; `tests/unit/test_hosted_reviewer_ui.py::test_core_facility_surfaces_share_projected_identity_without_mutation`; `tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_uses_public_identity_fallback_for_missing_name`; `tests/unit/test_hosted_ccld_facility_lookup.py::test_fixture_facility_overview_missing_identity_projection_preserves_only_identity`. | No material adoption gap in the listed representative routes; source and data protections remain independent. | Update with governed identity change; supersede only with explicit state mapping; retain source/data protections. |
| `RT-RC-005` | Enforced | GET state changes preserve selection, focus, and meaningful context; required actions remain visible, ordered, keyboard-operable, and non-overlapping. | Control type, visual order, and responsive layout. | #608; consumed or extended by #419, #420, #502, #503, and #610. | Retained worklist search and selected-record focus, Compare Facilities filter and drill-down continuity, Facility Overview Review next, responsive worklist, and Help fragments/history. | `assert_continuity`; `assert_actions`; foundation and real-route tests; `tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_continuations_preserve_filters_and_reject_bad_state`; `tests/unit/test_hosted_ccld_facility_lookup.py::test_ccld_facility_review_hub_has_one_deterministic_primary_next_action`; Issue #610 and #503 continuity checks. | No material adoption gap in the listed representative routes; exact browser and hosted evidence remain issue-specific. | Update with approved interaction change; supersede with replacement browser evidence; retire only after equivalent continuity protection. |
| `RT-RC-006` | Enforced | Fixture isolation, valid facility/complaint/document/source-index/reviewer-state/route relationships, non-duplicated results, and consolidated empty states remain protected. | Fixture naming, test-data arrangement, and presentation layout. | #608; consumed or extended by #420, #502, #503, #607, and #610. | Seeded complaint, source document, facility, reviewer-state, route, populated, and empty states; one canonical worklist; Facility Overview canonical inventory and zero-complaint state; visible Help sections with one bounded secondary disclosure. | `assert_fixture_integrity`; `assert_result_structure`; foundation tests; `tests/unit/test_hosted_ccld_facility_lookup.py::test_ccld_facility_overview_zero_complaint_state_keeps_one_action`; Issue #610 structure tests; Issue #503 unique-target, visible-primary, and disclosure-boundary checks. | No material adoption gap in the listed representative routes. | Update builders and relationship checks together; registry exceptions must be explicit; retire only with approved equivalent separation. |

PR preparation identifies each applicable contract as affected, added, updated,
superseded, or not applicable with a specific reason. During development, run
focused applicable checks; broader regression occurs at the final stable point
or when a failure or scope change requires it. A documented or partially
enforced status must not be presented as completed executable coverage. Enforced
coverage is bounded to the stated outcomes, routes, and tests; it is neither
universal enforcement nor pixel-perfect presentation enforcement.

## Registration and change lifecycle

This table is the contract registry. A reviewer-facing change names each
affected contract in its governed PR body and points to the smallest executable
test that proves the durable outcome. When an approved redesign changes
presentation, update the supersedable-details and representative-state columns
with the replacement test. Retire or supersede a contract only through Issue
#504 classification, with the durable invariant either preserved by a named
replacement contract or explicitly shown to be obsolete.

`RT-RC-006-distinct-purpose` is the only reusable duplication-exception ID.
It requires a non-empty reason plus matching representation, duplicate-of, and
section IDs; a boolean or unmatched exception does not bypass duplication or
empty-section protection. Route adoption must record any additional governed
exception before its test can pass.

`RT-RC-002-sqlite` is the only reusable information-tier exception ID. It may
authorize only the exact `sqlite` term with a non-empty, route-specific reason;
unknown IDs, wildcard terms, and terms outside that declaration fail closed.
Unavailable actions must still declare a supported action kind and a non-empty
unavailability reason, and may not expose a usable destination or mutation
path.

## Issue #502 adoption

Issue #502 consumes `RT-RC-001`, `RT-RC-002`, `RT-RC-005`, and `RT-RC-006`.
`tests/unit/test_hosted_ccld_facility_lookup.py` now proves the contextual
facility destination, valid-unmatched Facility ID continuation, malformed-ID
recovery, one result region, and no reviewer-facing reference diagnostics.
`tests/unit/test_hosted_app_scaffold.py` proves the distinct Home launch,
approved six-item navigation, active-route behavior, and contextual absence of
record retrieval from the global navigation. These are bounded route and
fixture-mode checks; browser evidence remains the required final proof of
focus, viewport, back/forward, keyboard, and reflow behavior.

The superseded Home/Facilities shared renderer, manual-entry disclosure,
reference-details disclosure, optional-planning disclosure, universal
`Continue to Request Records` action, and former global navigation labels are
Class 5 or Class 6 presentation artifacts under #504. Facility discovery,
valid-ID continuation, facility identity, truthful data states, accessible
focus, and the operator/reviewer tier boundary remain protected outcomes.

## Issue #503 adoption

Issue #503 extends `RT-RC-001`, `RT-RC-002`, `RT-RC-005`, and `RT-RC-006`
and consumes `RT-RC-003`. `/ccld/help` keeps authorized current task
destinations, excludes operator/developer mechanics, presents ordinary guidance
without disclosure, and retains exactly one secondary-example disclosure.
`tests/unit/test_hosted_ccld_record_request_ui.py` protects current tasks,
official terms, source/reviewer boundaries, destinations, and prohibited
content. `tests/unit/test_hosted_app_scaffold.py` protects one H1, unique
visible fragment targets, logical headings, one bounded disclosure, and the
browser fragment/focus/history contract. The focused evidence path proves
actual direct loads, keyboard activation, focus and viewport destinations,
Back/Forward continuity, invalid-fragment recovery, responsive reflow,
glossary behavior, and print.

The six legacy topic disclosures, exact old heading order, matching-only
fragment checks, and implementation-stage route labels are Class 5 or Class 6
artifacts under #504. Current task meaning, source-state truthfulness,
reviewer-created-state separation, usable destinations, responsive integrity,
and shared glossary behavior remain durable.

## RT-RC-003 shared help behavior

`render_inline_glossary_term` is the shared glossary and missing-value help
component. Reviewer missing-value presentations consume it through
`_presentation_markup`; they do not create a second missing-value component.
Current representative consumers are Compare Facilities and Complaint Overview
facility-identity coverage.

The component opens on non-touch pointer entry or keyboard focus and supports
click or tap without requiring hover. Only one definition window may be active.
Pointer leave, blur, outside pointer interaction, and Escape dismiss it; Escape
keeps or restores focus on the term. Activating an adjacent term closes the
prior definition first. The window is attached to the document body, repositions
above or below the term, stays within viewport edges, and scrolls internally
when available height is constrained.

Each term has one custom `role="tooltip"` description connected by one unique
`aria-describedby` relationship. A term must not also emit a native `title` or
`aria-description`; the tooltip is not an `aria-live` region. Trigger copy,
dotted-underline styling, precise above/below choice, dimensions, and panel
layout remain supersedable when an approved presentation preserves the contract.

Future reviewer changes using glossary or missing-value help declare
`RT-RC-003` affected in the governed PR body and add the smallest shared
component plus representative-route coverage. Issue #610 consumes the #606
component unchanged for consolidated Complaint Overview identity coverage while
changing the broader worklist and overview hierarchy, duplication, terminology,
source-state, reviewer-state, and complaint-action behavior.

## Issue #610 adoption

Issue #610 extends `RT-RC-001` with the combined review-update destination,
direct public-source action, and search-aware Complaint Worklist return. It
consumes `RT-RC-002` and `RT-RC-003` without weakening the attorney-tier or
shared-help boundaries. It extends `RT-RC-004` across complete, partial,
unavailable, and current-reference-conflict identity states; `RT-RC-005` across
retained search, selected-record focus, mutation feedback, narrow/mobile, zoom,
and print states; and `RT-RC-006` across one canonical worklist plus omitted
empty or date-only optional sections. Exact-route browser evidence remains part
of Issue #610 acceptance rather than a substitute for these executable checks.

## Issue #627 return-label regression

Issue #627 corrects the reviewer-detail fallback literal to the canonical
`Return to Complaint Worklist` label without changing the return-destination
helper or its retained search, selected-record, facility, date, lookup, and
origin context. It consumes `RT-RC-001`, `RT-RC-005`, and `RT-ACT-001` through
the populated detail route and retained-context checks, and strengthens
`RT-RC-006` by rejecting the deprecated visible `Return to review queue` label
there. Internal route/context identifiers and historical references remain
unchanged when they are not reviewer-visible.

## Issue #419 adoption reconciliation

Issue #419 consumes `RT-RC-001`, `RT-RC-004`, and `RT-RC-005` with existing
executable coverage. Its representative Compare Facilities checks protect valid
complaint/source/reviewer destinations and drill-down context, public-identity
fallback without unsupported conclusions, and filter/continuation integrity.
The independently owned #419 hosted, real-data, duplicate/fallback, deployment,
and stakeholder gates are not #608 blockers.

## Issue #420 adoption reconciliation

Issue #420 consumes or extends `RT-RC-001` through `RT-RC-006`. Facility
Overview checks protect Review next destinations, reviewer/operator tier
separation, the shared missing-value help contract, governed and missing
identity states, action integrity, and one canonical populated or empty
inventory. This is a bounded adoption record for accepted implementation, not a
claim of universal route or pixel-perfect enforcement.

## Bounded historical sample

| Issue | Durable outcome | Prior executable protection | Gap classification | Phase 1 treatment |
| --- | --- | --- | --- | --- |
| #568 | The available facility-overview action stays visible, ordered, and operable without implementation-stage wording. | Route tests protected labels and markup. | Shallow and presentation-bound. | `RT-RC-001` and `RT-RC-005` provide destination/action contracts; exact responsive adoption remains deferred. |
| #419 | Reviewers retain filters and context while moving from cross-facility results to usable complaint and facility destinations. | Focused route tests existed for individual surfaces. | Route-limited. | Representative real-route and continuity coverage now records bounded adoption; independent #419 hosted, data, deployment, and stakeholder gates remain outside #608. |
| #522 | The same governed Facility ID resolves consistently across reviewer and facility surfaces. | A cross-surface identity test already exercises actual responses. | Durable executable protection existed. | Reused unchanged under `RT-RC-004`; fixture relationship checks strengthen its inputs. |
| #605 | Complaint, source, facility, and reviewer-status actions never expose broken fixture targets or unusable destinations. | Earlier checks did not jointly prove fixture relationships and actual outcomes. | Fixture-incomplete and shallow. | `assert_fixture_integrity` plus representative real requests/mutation feedback addresses the failure category without reimplementing #605. |
| #606 | One understandable help treatment remains active without collision, duplicate announcement, or focus loss. | Existing checks covered isolated markup and behavior fragments. | Route-limited and presentation-bound. | `RT-RC-003` now supplies the shared behavior contract, shared-shell component coverage, and representative Compare Facilities and Complaint Overview route adoption. |

## Completed Issue #608 adoption reconciliation

The foundation, #502, #503, #605, #606, #610, #607 routing, and applicable #419
and #420 adoption are complete at the bounded level recorded here. Issues #605,
#606, and #610 consume this registry and helper layer without creating separate
contract systems. Presentation details remain supersedable under #504, and
independent #419 acceptance gates remain outside this issue.

## Issue #642 controlled interaction adoption

Issue #642 applies `RT-RC-001` and `RT-RC-005` to Compare Facilities local
navigation, repeated-key filters, keyset continuity, and allowlisted Facility
Overview/complaint-detail return context. It applies `RT-RC-003` to progressive
native-checkbox disclosure, no-JavaScript fallback, Escape, focus restoration,
and outside dismissal. It does not supersede result-inventory, source, identity,
authorization, or print-content protections; #643 owns density and print length,
#647 owns location, and #644 is not started.

The Issue #642 evidence contract additionally rejects detached checkbox labels,
detached Trends listboxes, page overflow, and keyboard-focus metadata without a
visible in-viewport focus indicator. Print keeps the active canonical filter
scope outside print-hidden interactive controls; this preserves print context
without changing print-density or page-count authority.

Licensing uses the governed directory for staged public-ID selection and tests
populated, filtered-empty, and separately launched source-unavailable states
without a production-visible simulation query. Card hierarchy and geometry
remain Issue #643 concerns.
