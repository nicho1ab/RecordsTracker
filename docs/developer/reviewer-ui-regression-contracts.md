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
| `RT-RC-001` | Partially enforced | A reviewer action reaches a usable authorized destination with supported context; destination and authorization integrity remain protected. | Link label, placement, icon, and action-group layout. | #608; #419 | Compare Facilities complaint and source actions. | `tests/unit/test_hosted_facility_priorities.py` covers bounded cross-facility action behavior. | Exercise every visible reviewer action with response or mutation assertions. | Update with an approved route replacement; retire only after replacement redirect/context evidence. |
| `RT-RC-002` | Documented | Reviewer routes exclude operator controls, runtime commands, and raw diagnostics from the attorney tier. | Page grouping, wording, and control styling. | #608 | Reviewer success and no-result pages. | No contract-specific executable check is recorded. | Add focused reviewer-route assertions and browser-observable evidence. | Update only with a governed information-tier decision; never retire the tier boundary. |
| `RT-RC-003` | Documented | One help treatment is active per dense reviewer context without overlapping announcements or focus traps. | Trigger wording, icon, placement, and help panel layout. | #608; #606 | Glossary trigger focus, touch, and narrow viewport states. | No contract-specific executable check is recorded. | Add #606 shared-component and interaction evidence coverage. | Retire obsolete presentation assertions only through #504 classification and an approved replacement. |
| `RT-RC-004` | Partially enforced | Facility identity remains public, consistent, and usable across comparison, detail, and return routes; source and identity protections remain required. | Identity label wording, card/table presentation, and route layout. | #608; #419; #420 | Compare Facilities to complaint detail. | `tests/unit/test_hosted_facility_priorities.py` covers bounded facility workflow behavior. | Add cross-route identity conflict and return-context assertions. | Update only with a governed identity-contract change; preserve source and data protections. |
| `RT-RC-005` | Documented | Route changes and state submissions preserve useful focus, fragment, viewport, and filter continuity; accessibility continuity remains protected. | Control type, visual order, and responsive layout. | #608 | Status save success/error and responsive route states. | No contract-specific executable check is recorded. | Add focused browser-observable continuity tests and local UI-evidence packet coverage. | Update with approved interaction changes and replacement browser-observable evidence. |
| `RT-RC-006` | Enforced | Fixture-only or synthetic records cannot appear as production-style reviewer results; fixture and source-integrity separation remains protected. | Fixture naming, test-data arrangement, and presentation layout. | #608 | Local fixture and production-style isolation. | `tests/unit/test_hosted_reviewer_source_evidence.py::test_local_visual_fixture_records_are_absent_from_production_style_context`. | Expand only if a new fixture path can reach a production-style context. | Update fixture builders and tests together; never retire production-versus-fixture separation without an approved replacement. |

PR preparation identifies each applicable contract as affected, added, updated,
superseded, or not applicable with a specific reason. During development, run
focused applicable checks; broader regression occurs at the final stable point
or when a failure or scope change requires it. A documented or partially
enforced status must not be presented as completed executable coverage.
