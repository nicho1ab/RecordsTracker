
# RecordsTracker UI, UX, Design, and Data Completeness Remediation Plan

## Purpose

This is the controlling shared working reference for ChatGPT, Codex, GitHub Copilot, Figma, GitHub, and operator workflows. Its purpose is to prevent design drift, preserve newly discovered gaps, and keep implementation tied to approved evidence and issue tracking.

Repository path:

`docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md`

Approved design requirement register:

`docs/product/records-tracker-approved-design-decisions.md`

This register preserves the stable requirement IDs associated with the authoritative approved Figma design. Reviewer-facing design prompts, implementation packages, and visual evidence reviews must cite the applicable requirement IDs and report unexplained variance or regression as an acceptance blocker.

Upload the current version to the ChatGPT Project Sources section. When Codex changes a repository file represented in ChatGPT Project Sources, I must tell you to upload the replacement version prior to it becoming material to a future response.

## Standing operating rules

1. ChatGPT reviews this file before every response concerning RecordsTracker design, UI, UX, data completeness, source extraction, Figma, evidence, or related GitHub issues.
2. ChatGPT evaluates every supplied screenshot, source report, evidence ZIP, HTML snapshot, route assertion, accessibility summary, Codex handoff, PR diff, and runtime result for defects, regressions, missing requirements, and untracked gaps.
3. When Codex changes a repository file represented in ChatGPT Project Sources, I must tell you to upload the replacement version prior to it becoming material to a future response, and I must name the exact file that needs replacement.
4. Newly discovered work is either mapped to an existing GitHub issue or added as a new issue before it is allowed to disappear into conversation history.
5. Codex and GitHub Copilot implement approved designs; coding agents do not invent the important reviewer-facing design.
6. No reviewer-facing implementation begins without an approved design package and numbered page-change inventory.
7. Tests are necessary but do not establish visual acceptance.
8. Source-field work is not complete until source-to-screen delivery and production-style evidence are verified.

## Current issue map

- #419 — Cross-facility intelligence dashboard; current Codex work.
- #420 — Facility review hub; must be updated to require one complaint inventory, meaningful labels, no primary-content accordions, approved design implementation, and complete facility identity.
- #421 — Final stakeholder acceptance.
- #447 — Canonical extracted-field allocation; must reference the complaint-report field inventory and source-to-screen audit.
- #450 — Prevent unexplained blanks; must distinguish source omission from extraction, import, read-model, and rendering failures.
- #453 — Automated source-to-screen coverage reporting; must consume the approved field inventory and report layer-level coverage.
- #474 — Privacy-governed Google Analytics 4.
- #475 — Corpus-wide preserved-artifact backfill idempotence.
- #476 — Twenty-seven preserved-artifact failures.
- #477 — Operator coverage and refresh dashboard.
- #478 — Scheduled governed refresh automation.
- #479 — Strengthen reviewer UI design governance and visual acceptance gates.
- #480 — Create the approved RecordsTracker design system and implementation package.
- #481 — Create complaint-report field inventory and source-to-screen completeness audit.
- #482 — Unify governed facility identity projection across reviewer surfaces.
- #483 — Extract and surface complaint deficiencies and plans of correction.
- #484 — Add approved-design variance review to hosted UI evidence.

The issue-management script accompanying this plan creates additional issues and adds comments to affected existing issues.

## Design outcome strategy

### Design responsibility

- ChatGPT/Product UX Lead defines the page task, content hierarchy, design constraints, data states, accessibility behavior, and acceptance criteria.
- Figma is the authoritative visual design environment for important reviewer-facing pages.
- Codex or GitHub Copilot receives an implementation package and implements it without redesigning it.
- ChatGPT compares route evidence to the approved design before merge recommendation.

### Required approved design package

Each important page must have:

- approved desktop frame;
- approved narrow-desktop frame;
- approved mobile or compact frame when applicable;
- component states for populated, empty, partial, unavailable, error, selected, hover, focus, and disabled conditions;
- typography, spacing, border, radius, icon, elevation, and color tokens;
- approved traffic-light protocol semantic colors;
- page annotations defining visible-by-default content and permitted progressive disclosure;
- component names that map to implementation components;
- explicit prohibited-pattern annotations;
- exported screenshots and, where practical, Figma Dev Mode measurements or design-token export.

### Efficient design workflow

1. ChatGPT produces a page brief and wire-content inventory from governance, source data, and screenshots.
2. Build the page in Figma using the final approved RecordsTracker design system, not a generic AI-generated dashboard theme.
3. Use Figma AI or another visual design tool only to generate alternatives; the user selects and approves the final frame.
4. Create a small pattern library before further page implementation: shell, typography, buttons, chips, TLP status indicators, facility identity banner, complaint row, filter bar, reviewer action rail, missing-data states, table/card responsive pattern, and permitted secondary disclosure.
5. Export a design implementation packet containing screenshots, annotations, tokens, component inventory, responsive rules, and acceptance checklist.
6. Codex or GitHub Copilot implements only from that packet.
7. Run exact-route evidence capture.
8. ChatGPT performs side-by-side design variance review.
9. Reject and return implementation when hierarchy, palette, spacing, density, responsive behavior, or interaction differs materially.

### Color governance

- No automatic teal-primary theme.
- TLP and other semantic colors are used for approved status meanings, with text and accessible labels.
- Brand and semantic palettes are separate.
- Neutral surfaces, typography, borders, and emphasis levels must be tokenized.
- Color tokens must be named by purpose, not raw color name alone.

## Approved information architecture principles

- One canonical complaint inventory per page context.
- Do not duplicate complaints under multiple aggregate headings.
- Core complaint evidence is visible by default.
- Accordions and disclosures are allowed only for secondary material.
- Use meaningful source-backed complaint subjects, not generic lineage labels.
- Primary pages answer the user decision and next action above the fold.
- Reviewer, help, operator, developer, and data-enrichment tiers remain distinct.

## Required Figma frames

1. Facility review hub — populated.
2. Facility review hub — partial and failed data states.
3. Complaint overview — complete complaint report.
4. RecordsTracker design-system and pattern-library frame.
5. Cross-facility dashboard frame for #419, if the current implementation does not already have an approved final design.

Each frame must be labeled `Approved implementation reference — variance requires approval`.

## Approved Issue #419 large-corpus pagination variance

Issue #419 has an approved narrow variance for large-corpus pagination and
persistent inventory orientation on `/ccld/facilities/intelligence`. The
authoritative pagination addendum is Figma node `59:463`. Its approved state
frames are:

- desktop first page `59:469`;
- desktop middle page `59:505`;
- desktop last page `59:541`;
- approximately 500 px `59:577`;
- mobile 390 px `59:613`;
- 200% zoom `59:649`;
- Previous disabled `59:685`;
- Next disabled `59:721`;
- keyboard focus Previous `59:757`;
- keyboard focus Next `59:793`;
- applied filters `59:829`;
- print `59:868`;
- empty filtered result `59:904`.

The implementation must conform to `RT-PAG-001` and use exactly 25 facilities
per page. Pagination uses Previous and Next only, with no numbered pages,
arbitrary page jumps, or `Page N of M`. The exact result-position wording is
`Showing X–Y of Z facilities`. Previous is semantically disabled on the first
page and Next is semantically disabled on the last page. Navigation preserves
active filters and deterministic ordering, while changing a filter returns to
the first page.

The facility page must use database-level seek/keyset pagination. Authorization,
corpus/import scope, all active filters, complaint deduplication, governed
priority calculations, the complete visible ordering tuple, normalized facility
name, and stable facility identity must apply before pagination. The current
page query is bounded and returns one page plus a separate total matching-
facility count. Facility-page OFFSET, progressive or deep OFFSET, equivalent
scan-and-discard behavior, and full-corpus application-memory slicing or
aggregation are prohibited.

Complaint and supporting rows are fetched only for facilities represented on
the current page. Reviewer-created state is fetched only for those visible
facilities or source records. The governed Review next result for the complete
filtered corpus uses a separate bounded, ordered `LIMIT 1` database query and
must not hydrate or aggregate the full matching corpus in application memory.

Desktop may use restrained sticky inventory orientation only while controls and
focused content remain unobscured. Approximately 500 px, mobile 390 px, 200%
zoom, and print use normal document flow; print disables sticky positioning.
Pagination must not introduce horizontal page overflow. Previous and Next must
have descriptive accessible names, semantic disabled states, logical focus
order, and the approved visible Civic Ledger focus treatment. Result-position
text must remain available to assistive technology without excessive result
announcements.

Acceptance requires controlled exact-route evidence for every cited Figma state,
including keyboard focus, responsive widths, 200% zoom, print, disabled states,
applied filters, and the empty filtered result. Query evidence must prove bounded
seek/keyset pagination, no facility-page OFFSET, bounded current-page complaint,
supporting-row, and reviewer-state hydration, and the bounded ordered `LIMIT 1`
Review next query. Adjacent controlled pages must reconcile without facility
duplicates or omissions. Controlled fixture evidence must not be represented as
real-corpus hosted acceptance evidence.

## Source-report field inventory

The complaint-report audit must cover document identity, agency/office, facility identity, complaint timing, investigation participants, disposition, allegations, investigation findings, deficiencies, plans of correction, signatures, source traceability, extraction status, canonical allocation, PostgreSQL coverage, read models, and UI components.

Required audit statuses:

- present_and_populated
- present_but_not_extracted
- extracted_but_not_allocated
- allocated_but_not_imported
- stored_but_not_read
- read_but_not_rendered
- rendered_incorrectly
- present_blank
- source_label_absent
- source_artifact_unavailable
- unsupported_layout
- conflicting_sources
- intentionally_internal
- not_applicable

## Priority data gaps currently visible

- Complaint detail can show missing facility name, type, status, county, and address despite the source report containing ordinary facility identity fields.
- Facility hub and complaint detail appear to use inconsistent facility identity resolution.
- Deficiency, regulation, Type A/Type B, plan-of-correction, due-date, and correction-action content shown on source reports is not adequately represented in the reviewer UI.
- Investigation findings are under-structured.
- Missing data states collapse source omission and application failure into generic `Not provided` language.
- Backfill idempotence and hard failures remain open under #475 and #476.

## Evidence review checklist

For every supplied evidence packet or screenshot set, inspect:

- page hierarchy and decision clarity;
- exact conformance to approved Figma;
- palette and token conformance;
- TLP semantic-color use;
- primary versus secondary action hierarchy;
- duplicate content and repeated records;
- inappropriate accordions or disclosures;
- generic labels;
- missing source-backed fields;
- cross-page data inconsistency;
- empty, partial, unavailable, and error-state truthfulness;
- keyboard flow, focus, semantics, contrast, zoom, and responsive behavior;
- private or operator details exposed to reviewers;
- source-derived versus reviewer-created separation;
- untracked requirements or issue gaps.

## Implementation order

1. Preserve and complete current #419 work only against an approved design.
2. Merge the focused governance clarification package.
3. Establish the approved design system and implementation packet.
4. Create the complaint-report field inventory and source-to-screen audit.
5. Unify facility identity projection and missing-state semantics.
6. Add deficiency and plan-of-correction extraction, allocation, import, and reviewer presentation.
7. Redesign #420 facility hub from the approved Figma frame.
8. Bring complaint detail to complete-report design and data coverage.
9. Resolve #475 and #476 and complete controlled backfills.
10. Complete automated source-to-screen coverage under #453.
11. Perform final stakeholder acceptance under #421.

## Change-control procedure for this file

Before each response, ChatGPT should determine whether new facts require an update. When an update is required, ChatGPT will provide a one-line PowerShell command that modifies this absolute file:

`C:\Users\andre\OneDrive\Desktop\RecordsTracker-UI-UX-Data-Completeness-Remediation-Plan.md`

After updating it, replace the version in ChatGPT Project Sources.

## Additional material to provide when available

- Current approved Figma file or share link and exact frame names.
- Exported design tokens or Figma variables.
- Current evidence ZIPs after each UI branch.
- Screenshot set for desktop, narrow desktop, mobile, 200% zoom, keyboard focus, empty/partial/error states.
- Current database field-coverage report when available.
- Current complaint report fixtures covering multiple layouts and deficiency/POC pages.
- Codex handoff, changed-file list, and PR diff for each affected branch.

## ChatGPT Project Sources synchronization

When Codex or GitHub Copilot changes a repository file represented in ChatGPT Project Sources, ChatGPT must tell the user to upload the replacement version prior to that changed file becoming material to a future response. ChatGPT must name each exact file requiring replacement.
