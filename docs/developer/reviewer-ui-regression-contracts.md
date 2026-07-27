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
| `RT-RC-001` | Partially enforced | A reviewer action reaches a usable authorized destination with supported context; destination and authorization integrity remain protected. | Link label, placement, icon, and action-group layout. | #608; extended by #610; adopt in #419, #420, #502, #503 | Complaint detail, retained-search worklist return, source action, and combined reviewer-update states. | `tests/unit/reviewer_ui_contracts.py::assert_destinations`; `tests/unit/test_reviewer_ui_contract_routes.py`; Issue #610 combined-update tests in `tests/unit/test_hosted_reviewer_ui.py`. | Additional dependent-route and browser adoption. | Update with an approved route replacement; supersede/retire only with replacement redirect/context evidence. |
| `RT-RC-002` | Partially enforced | Reviewer routes exclude operator controls, runtime commands, and raw diagnostics from the attorney tier. | Page grouping, wording, and control styling. | #608; adopt in #502, #503, #610 | Representative safe reviewer fixture. | `assert_information_tier` and foundation test. | Route-specific browser evidence. | Update only with a governed information-tier decision; never retire the tier boundary. |
| `RT-RC-003` | Enforced | One help treatment is active per dense reviewer context; pointer, keyboard, and touch access do not create duplicate native or ARIA descriptions; dismissal, focus restoration, adjacent triggers, and viewport containment remain predictable. | Trigger wording, icon, above/below placement, and help panel layout. | #608; consumed and extended by #606 | Shared glossary component, Compare Facilities, and Complaint Overview repeated missing-value states. | `assert_help_surface`; foundation, shared-shell component, and representative real-route tests. | No gap in the bounded component/route contract; a future approved visual redesign supplies its own replacement visual evidence. | Retire obsolete presentation assertions only through #504 classification and an approved replacement. |
| `RT-RC-004` | Partially enforced | Facility identity remains consistent within a current tested state; explicit historical, conflict, and unavailable states remain distinguishable. | Identity wording and card/table arrangement. | #608; extended by #610; adopt in #419, #420 | Complaint Overview complete, partial, unavailable, and current-reference-conflict identity states; representative cross-surface identity state. | `assert_facility_identity`; fixture-integrity test; `test_hosted_reviewer_ui.py` identity-state and cross-surface tests. | Additional dependent-route browser evidence. | Update with governed identity change; supersede only with explicit state mapping; retain source/data protections. |
| `RT-RC-005` | Partially enforced | GET state changes preserve selection, focus, and meaningful context; required actions remain visible, ordered, keyboard-operable, and non-overlapping. | Control type, visual order, and responsive layout. | #608; extended by #610; adopt in #419, #502, #503 | Retained worklist search and selected-record focus, combined mutation feedback, responsive worklist, and representative action-group state. | `assert_continuity`; `assert_actions`; foundation and real-route tests; Issue #610 combined-update and retained-context tests. | Additional dependent-route browser adoption. | Update with approved interaction change; supersede with replacement browser evidence; retire only after equivalent continuity protection. |
| `RT-RC-006` | Partially enforced | Fixture isolation, valid facility/complaint/document/source-index/reviewer-state/route relationships, non-duplicated results, and consolidated empty states remain protected. | Fixture naming, test-data arrangement, and presentation layout. | #608; extended by #610; adopt in #420, #502, #503, #607 | Seeded complaint, source document, facility, reviewer-state, route, populated, and empty states; one canonical worklist and omitted empty Complaint Overview sections. | `assert_fixture_integrity`; `assert_result_structure`; foundation tests; source-evidence fixture-isolation test; Issue #610 worklist and empty-section tests. | Additional dependent-route browser adoption. | Update builders and relationship checks together; registry exceptions must be explicit; retire only with approved equivalent separation. |

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
