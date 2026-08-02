# Issue #642 Compare Facilities interaction evidence

This bounded record applies `RT-NAV-001`, `RT-RC-001`, `RT-RC-003`, and
`RT-RC-005` to ordinary local navigation, six-link mobile navigation, staged
public-Facility-ID typeahead, checkbox multi-value filtering, one Apply action,
repeated-key URLs, safe return context, responsive/zoom, keyboard,
no-JavaScript, and print evidence.

Issue #648 requires structural, functional, visual, and owner-acceptance gates.
Automation may record only structural and functional outcomes; independent visual
review and owner acceptance remain pending human decisions.

Issue #642 does not change Complaint Patterns card information architecture.
Card density, hierarchy, action ownership, contributor presentation, total page
height, and print-page-count redesign remain reserved for #643; facility
location/address remains with #647, and dependent #644 remains outside this
scope.

For the bounded local visual evidence, every enhanced checkbox option keeps its
native checkbox and associated label in one wrapping row. The Trends listbox is
an immediate child sibling of its input within the combobox wrapper; narrow and
200% reflow keeps it in flow. The print-only active-filter scope is outside the
print-hidden filter controls and precedes the result or empty-state explanation.
Licensing typeahead searches the governed facility directory, including a
public Facility ID visible in Complaint Patterns even when that facility has no
loaded Licensing observation. The evidence runtime uses the tracked tiny
public-source Licensing CSV for populated and filtered-empty states, plus a
separate fixture launch for source-unavailable state. Capture rejects a missing
option-row, detached listbox, horizontal overflow, or focus artifact without a
visible keyboard indicator.

## 2026-08-01 Issue-boundary isolation inventory

The external preservation snapshot recorded in the Issue #642 handoff retains
every pre-isolation file. The following already-intermixed Issue #643 hunks
were removed from this Issue #642 candidate and remain recoverable there for
later authorized Issue #643 work:

- `reviewer_ui.py`: structured card ordering facts, contributor fact lists, the
  selected-card glossary relocation, and the card-specific badge markup.
- `ui_shell.py`: bounded card surfaces, grid areas, responsive action-region
  placement, ordering/contributor-fact styling, and card-geometry styling.
- `capture-hosted-ui-evidence.ps1` and its unit test: card-geometry assertion,
  scenario flags, diagnostics, and artifact expectation.
- `test_hosted_facility_priorities.py`: card-bounds and action-ownership test.
- reviewer regression and evidence-review documentation: card-geometry claims.

The Issue #642 candidate retains only filter/navigation evidence. The
`Suggested review order` wording remains unchanged because the current approved
candidate treats it as existing visible text rather than card-architecture work.
