# Reviewer UI regression contracts

Issue #608 records bounded, outcome-based reviewer UI regression contracts. It
implements Issue #504 anti-fossilization governance: durable outcomes and
protected invariants remain governed, while approved presentation changes may
supersede layout, control type, and optional wording.

Status vocabulary:

- **Documented**: the outcome is governed here, but no dedicated executable
  contract currently proves it.
- **Partially enforced**: existing focused checks prove a bounded portion of
  the outcome; the remaining planned coverage is still required before final
  acceptance of dependent UI work.
- **Enforced**: the listed current executable checks cover the stated bounded
  outcome at the current base.

| Contract ID | Status | Durable outcome and protected invariant | Supersedable presentation details | Owning issue | Representative routes or states | Current executable checks | Planned checks not yet implemented | Update and retirement rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `RT-RC-001` | Partially enforced | A reviewer action reaches a usable authorized destination with supported context; destination and authorization integrity remain protected. | Link label, placement, icon, and action-group layout. | #608; extended by #610 and #503; adopt in #419, #420, #502 | Complaint detail, retained-search worklist return, source action, combined reviewer-update states, and Help task destinations. | `tests/unit/reviewer_ui_contracts.py::assert_destinations`; `tests/unit/test_reviewer_ui_contract_routes.py`; Issue #610 combined-update tests; Issue #503 Help route, fragment, and browser evidence checks. | Additional dependent-route adoption. | Update with an approved route replacement; supersede/retire only with replacement redirect/context evidence. |
| `RT-RC-002` | Partially enforced | Reviewer routes exclude operator controls, runtime commands, and raw diagnostics from the attorney tier. | Page grouping, wording, and control styling. | #608; extended by #503; adopt in #502 and #610 | Representative safe reviewer fixture and attorney Help. | `assert_information_tier`; foundation test; Issue #503 prohibited-content route and evidence assertions. | Additional dependent-route browser evidence. | Update only with a governed information-tier decision; never retire the tier boundary. |
| `RT-RC-003` | Enforced | One help treatment is active per dense reviewer context; pointer, keyboard, and touch access do not create duplicate native or ARIA descriptions; dismissal, focus restoration, adjacent triggers, and viewport containment remain predictable. | Trigger wording, icon, above/below placement, and help panel layout. | #608; consumed and extended by #606; consumed by #503 | Shared glossary component, Compare Facilities, Complaint Overview repeated missing-value states, and attorney Help official terms. | `assert_help_surface`; foundation and shared-shell component checks; representative route tests; Issue #503 glossary structure and keyboard evidence. | No gap in the bounded component/route contract; a future approved visual redesign supplies its own replacement visual evidence. | Retire obsolete presentation assertions only through #504 classification and an approved replacement. |
| `RT-RC-004` | Partially enforced | Facility identity remains consistent within a current tested state; explicit historical, conflict, and unavailable states remain distinguishable. | Identity wording and card/table arrangement. | #608; extended by #610; adopt in #419, #420 | Complaint Overview complete, partial, unavailable, and current-reference-conflict identity states; representative cross-surface identity state. | `assert_facility_identity`; fixture-integrity test; `test_hosted_reviewer_ui.py` identity-state and cross-surface tests. | Additional dependent-route browser evidence. | Update with governed identity change; supersede only with explicit state mapping; retain source/data protections. |
| `RT-RC-005` | Partially enforced | GET state changes preserve selection, focus, and meaningful context; required actions remain visible, ordered, keyboard-operable, and non-overlapping. | Control type, visual order, and responsive layout. | #608; extended by #610 and #503; adopt in #419 and #502 | Retained worklist search and selected-record focus, combined mutation feedback, responsive worklist, and Help fragments/history. | `assert_continuity`; `assert_actions`; foundation and real-route tests; Issue #610 retained-context tests; Issue #503 direct-fragment, keyboard, viewport, invalid-fragment, and Back/Forward evidence. | Additional dependent-route adoption. | Update with approved interaction change; supersede with replacement browser evidence; retire only after equivalent continuity protection. |
| `RT-RC-006` | Partially enforced | Fixture isolation, valid facility/complaint/document/source-index/reviewer-state/route relationships, non-duplicated results, and consolidated empty states remain protected. | Fixture naming, test-data arrangement, and presentation layout. | #608; extended by #610 and #503; adopt in #420, #502, #607 | Seeded complaint, source document, facility, reviewer-state, route, populated, and empty states; one canonical worklist; omitted empty Complaint Overview sections; visible Help sections with one bounded secondary disclosure. | `assert_fixture_integrity`; `assert_result_structure`; foundation tests; source-evidence fixture-isolation test; Issue #610 structure tests; Issue #503 unique-target, visible-primary, and disclosure-boundary checks. | Additional dependent-route adoption. | Update builders and relationship checks together; registry exceptions must be explicit; retire only with approved equivalent separation. |

PR preparation identifies each applicable contract as affected, added, updated,
superseded, or not applicable with a specific reason. During development, run
focused applicable checks; broader regression occurs at the final stable point
or when a failure or scope change requires it. A documented or partially
enforced status must not be presented as completed executable coverage.

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

## Bounded historical sample

| Issue | Durable outcome | Prior executable protection | Gap classification | Phase 1 treatment |
| --- | --- | --- | --- | --- |
| #568 | The available facility-overview action stays visible, ordered, and operable without implementation-stage wording. | Route tests protected labels and markup. | Shallow and presentation-bound. | `RT-RC-001` and `RT-RC-005` provide destination/action contracts; exact responsive adoption remains deferred. |
| #419 | Reviewers retain filters and context while moving from cross-facility results to usable complaint and facility destinations. | Focused route tests existed for individual surfaces. | Route-limited. | Representative real-route and continuity coverage addresses the shared category; full #419 adoption remains deferred. |
| #522 | The same governed Facility ID resolves consistently across reviewer and facility surfaces. | A cross-surface identity test already exercises actual responses. | Durable executable protection existed. | Reused unchanged under `RT-RC-004`; fixture relationship checks strengthen its inputs. |
| #605 | Complaint, source, facility, and reviewer-status actions never expose broken fixture targets or unusable destinations. | Earlier checks did not jointly prove fixture relationships and actual outcomes. | Fixture-incomplete and shallow. | `assert_fixture_integrity` plus representative real requests/mutation feedback addresses the failure category without reimplementing #605. |
| #606 | One understandable help treatment remains active without collision, duplicate announcement, or focus loss. | Existing checks covered isolated markup and behavior fragments. | Route-limited and presentation-bound. | `RT-RC-003` now supplies the shared behavior contract, shared-shell component coverage, and representative Compare Facilities and Complaint Overview route adoption. |

## Deferred Issue #608 phases

Phase 1 does not complete remaining dependent-route adoption, governed browser
focus and viewport evidence, or the substantive UI fixes in #502, #419, #420,
#503, or #607. Issues #605, #606, and #610 consume this registry and helper
layer without creating separate contract systems; their bounded adoption is
recorded above.
