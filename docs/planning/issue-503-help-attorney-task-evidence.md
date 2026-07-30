# Issue #503 Help attorney-task evidence

Issue #503 consumes the approved Issue #501 repository-readable controlled
variance for `/ccld/help`. The implementation keeps the existing Help route and
shared shell while replacing the disclosure-heavy implementation sequence with
four attorney-facing categories:

1. Get started.
2. Understand the information.
3. Manage review work.
4. Troubleshooting.

This is an implementation and evidence record, not visual acceptance and not a
Figma update.

## Requirements consumed

The change consumes `RT-IA-004`, `RT-NAV-001`, `RT-LANG-001`, `RT-GL-001`,
`RT-ACT-001`, `RT-TIER-001`, `RT-SRC-001`, `RT-STATE-001`, `RT-RWD-001`,
`RT-A11Y-001`, `RT-A11Y-002`, `RT-STRESS-001`, `RT-PRINT-001`, and
`RT-SAFE-001`. It also consumes or extends `RT-RC-001`, `RT-RC-002`,
`RT-RC-003`, `RT-RC-005`, and `RT-RC-006`. `RT-RC-004` is not affected
because Help explains facility information but does not render a current
facility identity value.

## Pre-code artifact classification

| Artifact | Classification | Issue #503 treatment |
| --- | --- | --- |
| `/ccld/help`, `/help`, the shared six-item attorney shell, skip link, footer, and print shell | Preserved durable behavior | Keep the existing authorized destinations and common interaction behavior. |
| Shared #606 inline glossary component | Preserved and consumed | Use the existing collision-safe point-of-use definition behavior for official CCLD terms. |
| Source facts versus reviewer-created notes/status | Preserved durable boundary | Explain the distinction without introducing a new state, inference, or action. |
| Six legacy topic disclosures and their exact headings/order | Class 5 superseded presentation | Replace with four visible category sections and visible task guidance. |
| Exact old table-of-contents markup and matching-only fragment assertions | Class 5 shallow presentation | Replace with descriptive fragments plus browser-observed focus, viewport, copied-URL, Back, and Forward checks. |
| Implementation-stage labels such as Review Queue, Reviewer Detail, request context, loaded records, and preparation draft | Class 6 obsolete terminology | Replace only where the approved current task or destination is accurate. |
| Operator, environment, connector, import, server, database, artifact, and runtime mechanics | Attorney-tier prohibited | Keep them out of Help. Existing governed developer and operator documents remain their source; no duplicate runbook or new information tier is created. |
| Historical changelog entries | Historical-only | Preserve unchanged as history and add a current Unreleased entry. |

The sole retained disclosure contains a secondary example of public sources
showing different facility details. No primary instruction, destination,
recovery action, or answer needed to choose a next action is hidden.

## Executable and browser evidence

Request and structural coverage lives in
`tests/unit/test_hosted_ccld_record_request_ui.py` and
`tests/unit/test_hosted_app_scaffold.py`. Evidence-process coverage lives in
`tests/unit/test_hosted_ui_evidence_capture.py`.

The repository evidence process uses the local fixture route and captures:

- desktop, 1024-pixel narrow desktop, 390-pixel mobile, and a 720-pixel
  200-percent-reflow approximation;
- direct copied URLs for all four primary fragments;
- keyboard activation of a category and representative child guidance;
- destination focus, viewport position, and non-overlap;
- browser Back and Forward focus continuity;
- invalid-fragment recovery;
- the one permitted secondary disclosure;
- shared glossary activation; and
- print PDF plus rendered print pages.

The packet records `issue-503-route-fragment-inventory.csv`,
`issue-503-approved-versus-rendered.csv`, `issue-503-ui-gates.csv`,
`issue-503-print-validation.json`, and
`diagnostics/issue-503-responsive-fragment-focus-measurements.json`.
`RT-UI-GATE-009` must remain `PENDING_INDEPENDENT_VISUAL_REVIEW` under the
superseding Issue #648 acceptance contract.

The 720-pixel capture is a governed reflow approximation. It is not native
browser-zoom or assistive-technology verification.
