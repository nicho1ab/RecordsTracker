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
| `RT-RC-001` | Enforced | A reviewer action reaches a usable authorized destination with supported context; destination and authorization integrity remain protected. | Link label, placement, icon, and action-group layout. | #608; adopt in #419, #420, #502, #503, #610 | Representative action-state fixture. | `tests/unit/reviewer_ui_contracts.py::assert_destinations`; `tests/unit/test_reviewer_ui_contract_foundation.py`. | Route-specific adoption and browser evidence. | Update with an approved route replacement; supersede/retire only with replacement redirect/context evidence. |
| `RT-RC-002` | Enforced | Reviewer routes exclude operator controls, runtime commands, and raw diagnostics from the attorney tier. | Page grouping, wording, and control styling. | #608; adopt in #502, #503, #610 | Representative safe reviewer fixture. | `assert_information_tier` and foundation test. | Route-specific browser evidence. | Update only with a governed information-tier decision; never retire the tier boundary. |
| `RT-RC-003` | Enforced | One help treatment is active per dense reviewer context without overlapping announcements or focus traps. | Trigger wording, icon, placement, and help panel layout. | #608; adopt in #606 | Representative help-surface state. | `assert_help_surface` and foundation test. | #606 component/browser adoption. | Retire obsolete presentation assertions only through #504 classification and an approved replacement. |
| `RT-RC-004` | Enforced | Facility identity remains consistent within a current tested state; explicit historical, conflict, and unavailable states remain distinguishable. | Identity wording and card/table arrangement. | #608; adopt in #419, #420 | Representative populated identity fixture. | `tests/unit/reviewer_ui_contracts.py::assert_facility_identity`; `tests/unit/test_reviewer_ui_contract_foundation.py`. | Cross-route browser adoption and return-context evidence. | Update with governed identity change; supersede only with explicit state mapping; retain source/data protections. |
| `RT-RC-005` | Enforced | GET state changes preserve selection, focus, and meaningful context; required actions remain visible, ordered, keyboard-operable, and non-overlapping. | Control type, visual order, and responsive layout. | #608; adopt in #419, #502, #503, #610 | Representative continuity/action-group state. | `assert_continuity`, `assert_actions`, and foundation test. | Browser viewport/zoom adoption. | Update with approved interaction change; supersede with replacement browser evidence; retire only after equivalent continuity protection. |
| `RT-RC-006` | Enforced | Fixture isolation, non-duplicated result sets, and consolidated empty decision states remain protected. | Fixture naming, test-data arrangement, and presentation layout. | #608; adopt in #420, #502, #503, #607, #610 | Representative populated and empty fixture states. | `assert_result_structure`; foundation test; `test_hosted_reviewer_source_evidence.py::test_local_visual_fixture_records_are_absent_from_production_style_context`. | Route-specific browser adoption. | Update builders/tests together; registry exceptions must be explicit; retire only with approved equivalent separation. |

PR preparation identifies each applicable contract as affected, added, updated,
superseded, or not applicable with a specific reason. During development, run
focused applicable checks; broader regression occurs at the final stable point
or when a failure or scope change requires it. A documented or partially
enforced status must not be presented as completed executable coverage.

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
