# Issue #502 Home and facility discovery evidence

This record preserves the pre-code controlled-variance inventory for Issue #502.
It applies the approved attorney information architecture and the Issue #501
controlled variance; it does not claim visual acceptance.

## Scope and authority

- Home is the distinct review-task launch page with the approved heading
  `Review CCLD Facility Records`.
- Find a Facility is the distinct discovery route at `/ccld/facilities` with
  the approved heading `Find a Facility`.
- The shared global navigation is limited to Home, Find a Facility, Compare
  Facilities, Complaint Worklist, Feedback, and Help.
- Existing retrieval, reviewer-worklist, comparison, feedback, help, and
  operator-diagnostic routes remain separate. In particular,
  `/operator/source-coverage` is not a reviewer-facing discovery surface and
  is unchanged.

## Affected artifact inventory

| Artifact or assertion | Classification | Treatment |
| --- | --- | --- |
| Shared Home/facility lookup renderer | Class 5 — structurally rewritten | Separate Home task launch from facility discovery. |
| Facility intake, manual-ID disclosure, optional planning disclosure, and reference-details disclosure | Class 6 — removed/superseded | Remove from the primary reviewer flow; retain the valid-ID continuation outcome. |
| Reference-data mechanics, fallback counts, and operator details on the primary route | Class 6 — removed/superseded | Keep the operator route separate; use concise reviewer-facing availability states. |
| Global navigation labels | Class 4 — renamed/repositioned | Render the six approved labels in their approved order. |
| Valid unmatched nine-digit Facility ID continuation | Class 1/2/3 — preserved and extended | Preserve the Facility ID and offer a truthful continuation action. |
| Search matching and facility identity projection | Class 3 — preserved | Keep existing search and identity behavior while simplifying presentation. |
| Focus, landmarks, skip links, keyboard, and responsive assertions | Class 2/4 — preserved and extended | Keep semantic structure and add route-specific focus/reflow evidence. |
| Older Home/facility tests tied to combined intake/disclosures | Class 5/6 — rewritten or removed | Replace only presentation assertions that describe superseded content. |
| Older changelog entries | Class 7 — historical only | Do not rewrite historical records. |

## Exact review states and evidence

The focused fixture packet captures: Home desktop/mobile/skip-link focus; Find a
Facility default, populated results, valid unmatched Facility ID, malformed ID,
directory unavailable, mobile, and 720-pixel reflow states. Route assertions
also verify that selected results state complaint-context availability and use a
matching next action: Get Records, Choose Date Range, Get Additional Records,
Update Records, or Review Facility.

The change is evaluated against RT-IA-004, RT-NAV-001, RT-LANG-001, and the
applicable RT-UI-GATE-001 through RT-UI-GATE-009 controls. Passing route and
test automation is evidence for product-owner review, not visual acceptance.

## Explicit exclusions

Issue #502 does not change canonical schemas, source connectors, ingestion,
retrieval authorization, reviewer-created state, exports, operator diagnostics,
deployment, or remote infrastructure.
