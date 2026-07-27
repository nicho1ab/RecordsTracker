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
| `RT-RC-001` | Partially enforced | A reviewer action reaches a usable authorized destination with supported context; destination and authorization integrity remain protected. | Link label, placement, icon, and action-group layout. | #608; adopt in #419, #420, #502, #503, #610 | Complaint detail, facility-priority review, retained-search return, source action, and reviewer-status states. | `tests/unit/reviewer_ui_contracts.py::assert_destinations`; `tests/unit/test_reviewer_ui_contract_routes.py`. | Additional dependent-route and browser adoption. | Update with an approved route replacement; supersede/retire only with replacement redirect/context evidence. |
| `RT-RC-002` | Partially enforced | Reviewer routes exclude operator controls, runtime commands, and raw diagnostics from the attorney tier. | Page grouping, wording, and control styling. | #608; adopt in #502, #503, #610 | Representative safe reviewer fixture. | `assert_information_tier` and foundation test. | Route-specific browser evidence. | Update only with a governed information-tier decision; never retire the tier boundary. |
| `RT-RC-003` | Partially enforced | One help treatment is active per dense reviewer context without overlapping announcements or focus traps. | Trigger wording, icon, placement, and help panel layout. | #608; adopt in #606 | Representative help-surface state. | `assert_help_surface` and foundation test. | #606 component/browser adoption. | Retire obsolete presentation assertions only through #504 classification and an approved replacement. |
| `RT-RC-004` | Partially enforced | Facility identity remains consistent within a current tested state; explicit historical, conflict, and unavailable states remain distinguishable. | Identity wording and card/table arrangement. | #608; adopt in #419, #420 | Seeded fixture and representative cross-surface identity state. | `assert_facility_identity`; fixture-integrity test; `test_hosted_reviewer_ui.py::test_core_facility_surfaces_share_projected_identity_without_mutation`. | Browser return-context evidence. | Update with governed identity change; supersede only with explicit state mapping; retain source/data protections. |
| `RT-RC-005` | Partially enforced | GET state changes preserve selection, focus, and meaningful context; required actions remain visible, ordered, keyboard-operable, and non-overlapping. | Control type, visual order, and responsive layout. | #608; adopt in #419, #502, #503, #610 | Retained search, complaint return context, mutation feedback, and representative action-group state. | `assert_continuity`; `assert_actions`; foundation and real-route tests. | Governed browser viewport/zoom adoption. | Update with approved interaction change; supersede with replacement browser evidence; retire only after equivalent continuity protection. |
| `RT-RC-006` | Partially enforced | Fixture isolation, valid facility/complaint/document/source-index/reviewer-state/route relationships, non-duplicated results, and consolidated empty states remain protected. | Fixture naming, test-data arrangement, and presentation layout. | #608; adopt in #420, #502, #503, #607, #610 | Seeded complaint, source document, facility, reviewer-state, route, populated, and empty states. | `assert_fixture_integrity`; `assert_result_structure`; foundation tests; source-evidence fixture-isolation test. | Additional dependent-route and browser adoption. | Update builders and relationship checks together; registry exceptions must be explicit; retire only with approved equivalent separation. |

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

## Bounded historical sample

| Issue | Durable outcome | Prior executable protection | Gap classification | Phase 1 treatment |
| --- | --- | --- | --- | --- |
| #568 | The available facility-overview action stays visible, ordered, and operable without implementation-stage wording. | Route tests protected labels and markup. | Shallow and presentation-bound. | `RT-RC-001` and `RT-RC-005` provide destination/action contracts; exact responsive adoption remains deferred. |
| #419 | Reviewers retain filters and context while moving from cross-facility results to usable complaint and facility destinations. | Focused route tests existed for individual surfaces. | Route-limited. | Representative real-route and continuity coverage addresses the shared category; full #419 adoption remains deferred. |
| #522 | The same governed Facility ID resolves consistently across reviewer and facility surfaces. | A cross-surface identity test already exercises actual responses. | Durable executable protection existed. | Reused unchanged under `RT-RC-004`; fixture relationship checks strengthen its inputs. |
| #605 | Complaint, source, facility, and reviewer-status actions never expose broken fixture targets or unusable destinations. | Earlier checks did not jointly prove fixture relationships and actual outcomes. | Fixture-incomplete and shallow. | `assert_fixture_integrity` plus representative real requests/mutation feedback addresses the failure category without reimplementing #605. |
| #606 | One understandable help treatment remains active without collision, duplicate announcement, or focus loss. | Existing checks covered isolated markup and behavior fragments. | Route-limited and presentation-bound. | `RT-RC-003` supplies the shared behavior contract; component/browser adoption remains deferred to #606. |

## Deferred Issue #608 phases

Phase 1 does not complete dependent-route adoption, governed browser focus and
viewport evidence, or the substantive UI fixes in #605, #606, #502, #419,
#420, #503, #607, or #610. Those phases consume this registry and helper layer
without creating separate contract systems.
