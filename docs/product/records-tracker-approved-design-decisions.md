# RecordsTracker Approved Design Decisions

## Purpose and authority

This document is the repository-readable governance companion to the approved
RecordsTracker Figma design system and regression register.

It preserves the stable design decisions approved under GitHub issue #480 and
provides requirement identifiers that must be cited by implementation prompts,
code reviews, evidence reviews, and visual acceptance decisions.

The authoritative visual reference remains the Figma file:

https://www.figma.com/design/SYszaxbcMK8Ce2ywrUiu4q

Approved direction:

**Direction A — Civic Ledger**

The Civic Ledger direction uses a warm neutral canvas, deep navy shell and
primary actions, restrained gold navigation and focus cues, compact editorial
density, modest radii, and minimal elevation.

This document does not replace Figma as the authoritative visual reference.
Where prose and the approved Figma artifact appear to differ, implementation
must stop and the variance must be resolved before work continues.

## Relationship to project governance

This document implements the design-governance and visual-acceptance
requirements established by:

- `docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md`
- `docs/product/records-tracker-product-ux-lead-charter.md`
- `DESIGN_AND_USABILITY.md`
- `ACCESSIBILITY_REQUIREMENTS.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`

The remediation plan remains the controlling shared working reference for the
RecordsTracker design and implementation workflow. The Product UX Lead Charter
defines the attorney-facing product direction and requires design before code.
This file preserves the approved visual and interaction decisions as stable,
citable requirement IDs.

## Required use

### ChatGPT and product-design work

ChatGPT must:

1. Read this file before preparing a reviewer-facing design or implementation
   prompt.
2. Identify every requirement ID applicable to the proposed page or component.
3. Cite those IDs in the numbered page-change inventory and implementation
   package.
4. Stop when a requested design materially conflicts with an approved
   requirement unless the user explicitly approves a controlled variance.
5. Compare exact-route evidence with the applicable approved Figma frames and
   this register before recommending merge or acceptance.

### Codex and GitHub Copilot

Implementation agents must:

1. Read this file and the applicable authoritative Figma frames before changing
   reviewer-facing UI.
2. Cite the applicable requirement IDs in the task handoff and pull request.
3. Implement the approved design without substituting a generic component
   library, generic dashboard theme, or agent-invented redesign.
4. Preserve existing approved behavior unless the current task explicitly
   authorizes a variance.
5. Stop and report a blocker when implementation cannot conform to an applicable
   requirement ID.

### Implementation reviewers

Reviewers must:

1. Compare the implemented route with the approved Figma reference at the
   required viewports.
2. Classify every applicable requirement ID as:
   - `PASS`
   - `VARIANCE`
   - `REGRESSION`
   - `NOT APPLICABLE`
3. Explain every `NOT APPLICABLE` classification.
4. Treat an unexplained `VARIANCE` or any `REGRESSION` as a merge blocker.
5. Require corrected exact-route evidence before accepting a repaired result.

Tests alone do not establish visual acceptance. Passing automated tests,
markup assertions, snapshots, or accessibility scans do not prove that the
implemented hierarchy, palette, density, interaction, reflow, or content
treatment conforms to the approved design.

## Variance-control procedure

A change that intentionally differs from an applicable approved requirement
must follow this procedure:

1. Identify the affected requirement ID.
2. Describe the proposed difference and why the approved pattern does not meet
   the current user task.
3. Identify every page, component, viewport, state, and acceptance criterion
   affected.
4. Update the Figma design and regression register first.
5. Obtain explicit user approval.
6. Update this repository file in the same governed change.
7. Only then prepare or revise the implementation prompt.

An implementation must not silently redefine an approved decision.

## Approved design requirements

### RT-DS-001 — Warm neutral canvas

- **Approved decision:** Warm neutral canvas.
- **Scope:** Sitewide.
- **Figma proof:** `03 — Civic Ledger Foundations / color/page`; responsive
  stress proofs.
- **Responsive requirement:** All supported widths retain the warm neutral page
  background.
- **Accessibility requirement:** Verified contrast must remain readable at
  supported widths and 200% zoom.
- **Prohibited regression:** Generic white or gray application shell.
- **Required evidence before acceptance:** Exact-route screenshots and design
  token comparison.

### RT-DS-002 — Deep navy shell and primary actions

- **Approved decision:** Deep navy shell and primary actions.
- **Scope:** Sitewide.
- **Figma proof:** Responsive stress proofs, `Product header and navigation`,
  and the `Action` component.
- **Responsive requirement:** The header and primary-action hierarchy persist
  across supported widths.
- **Accessibility requirement:** Text and visible focus maintain approved
  contrast.
- **Prohibited regression:** Teal or low-contrast primary action.
- **Required evidence before acceptance:** Token comparison and exact-route
  screenshots.

### RT-DS-003 — Restrained gold navigation and focus cue

- **Approved decision:** Restrained gold navigation and focus cue.
- **Scope:** Sitewide.
- **Figma proof:** Foundations focus system and responsive navigation.
- **Responsive requirement:** Gold remains an accent and never becomes the
  dominant page color.
- **Accessibility requirement:** Focus remains visible and includes non-color
  cues.
- **Prohibited regression:** Gold used as ordinary body text or as a
  status-only cue.
- **Required evidence before acceptance:** Keyboard-focus screenshots and
  verified contrast evidence.

### RT-DS-004 — Compact editorial density

- **Approved decision:** Compact editorial density.
- **Scope:** Sitewide.
- **Figma proof:** Responsive stress proofs.
- **Responsive requirement:** Density reflows at narrower widths rather than
  becoming a sparse collection of cards.
- **Accessibility requirement:** Reading order remains logical after reflow.
- **Prohibited regression:** Oversized dashboard spacing.
- **Required evidence before acceptance:** Viewport comparison.

### RT-DS-005 — Modest radii and minimal elevation

- **Approved decision:** Modest radii and minimal elevation.
- **Scope:** Sitewide.
- **Figma proof:** Foundations and reusable components.
- **Responsive requirement:** Four-pixel surface radii remain the normal
  treatment; elevation is reserved for temporary floating UI.
- **Accessibility requirement:** Meaningful boundaries remain perceivable.
- **Prohibited regression:** Rounded-card-everywhere treatment.
- **Required evidence before acceptance:** Component inspection.

### RT-DS-006 — No generic teal or AI-dashboard theme

- **Approved decision:** No generic teal or AI-dashboard theme.
- **Scope:** Sitewide.
- **Figma proof:** Foundations and all responsive proofs.
- **Responsive requirement:** The palette remains Civic Ledger at every width.
- **Accessibility requirement:** Semantic colors include visible text and do
  not rely on color alone.
- **Prohibited regression:** Theme drift.
- **Required evidence before acceptance:** Design-token diff and route
  screenshots.

### RT-DS-007 — No automatic stacked-card treatment

- **Approved decision:** No automatic stacked-card treatment.
- **Scope:** Sitewide.
- **Figma proof:** Desktop table and narrow stacked-row proofs.
- **Responsive requirement:** Tables convert to labeled stacked rows only when
  required by the available width.
- **Accessibility requirement:** Field labels remain visible after conversion.
- **Prohibited regression:** Every section converted into a card.
- **Required evidence before acceptance:** Responsive evidence.

### RT-IA-001 — One canonical complaint inventory per page context

- **Approved decision:** One canonical complaint inventory per page context.
- **Scope:** Sitewide.
- **Figma proof:** Complaint inventory row and responsive proofs.
- **Responsive requirement:** The single inventory reflows without creating
  duplicate lists.
- **Accessibility requirement:** Each complaint has a descriptive
  record-specific action.
- **Prohibited regression:** Duplicate complaint lists or the same complaints
  repeated under multiple aggregates.
- **Required evidence before acceptance:** DOM inspection and exact-route
  screenshots.

### RT-IA-002 — Core complaint evidence visible by default

- **Approved decision:** Core complaint evidence remains visible by default.
- **Scope:** Sitewide.
- **Figma proof:** Complaint inventory row and detail-oriented complaint proof.
- **Responsive requirement:** The complaint summary remains visible and wraps.
- **Accessibility requirement:** Evidence must not require hover or pointer
  interaction to be read.
- **Prohibited regression:** Core evidence hidden by interaction.
- **Required evidence before acceptance:** Exact-route screenshot.

### RT-IA-003 — Primary complaint evidence not hidden in disclosures

- **Approved decision:** Primary complaint evidence is not hidden in accordions,
  tabs, or collapsed cards.
- **Scope:** Sitewide.
- **Figma proof:** Complaint inventory row and `Permitted secondary disclosure`
  component.
- **Responsive requirement:** Only secondary content may use the permitted
  disclosure pattern.
- **Accessibility requirement:** Any permitted secondary disclosure remains
  keyboard operable.
- **Prohibited regression:** Primary complaint evidence placed in a disclosure,
  accordion, tab, or collapsed card.
- **Required evidence before acceptance:** Markup and screenshot review.

### RT-ID-001 — Facility identity displayed once per page context

- **Approved decision:** Facility identity is displayed once per page context.
- **Scope:** Page-specific pattern.
- **Figma proof:** Facility identity banner in responsive proofs.
- **Responsive requirement:** A single facility identity banner reflows.
- **Accessibility requirement:** The facility heading and Facility ID remain
  readable.
- **Prohibited regression:** Repeated facility identity cards.
- **Required evidence before acceptance:** Exact-route screenshot.

### RT-CP-001 — Recognizable copy controls for priority values

- **Approved decision:** Recognizable copy controls appear beside approved
  priority values.
- **Scope:** Sitewide.
- **Figma proof:** `Checkpoint 3 — Copy and in-context patterns`; responsive
  stress proofs.
- **Responsive requirement:** A copy control wraps with, and remains associated
  with, the value it copies.
- **Accessibility requirement:** Each copy control has a descriptive accessible
  name and supports keyboard activation.
- **Prohibited regression:** Generic detached copy action or copy affordances on
  every field.
- **Required evidence before acceptance:** Default, focus, and copied-state
  screenshots plus interaction evidence.

Priority copy values are:

- Facility ID.
- Complaint or control number.
- Key date when reuse is likely.
- Finding or status when reuse is useful.
- Public source URL.
- Complaint summary or source narrative in an appropriate detail-oriented
  context.

The readable value must remain visible. `Open original source` and
`Copy source URL` remain separate actions.

### RT-DT-001 — MM/DD/YYYY date display

- **Approved decision:** Reviewer-facing dates use `MM/DD/YYYY`.
- **Scope:** Sitewide.
- **Figma proof:** Complaint row and compact timeline proofs.
- **Responsive requirement:** The date remains readable at every supported
  width.
- **Accessibility requirement:** The readable date remains visible beside any
  copy affordance.
- **Prohibited regression:** ISO-formatted dates shown to reviewers.
- **Required evidence before acceptance:** Exact-route screenshots.

### RT-TL-001 — Compact linear timeline for ordered events

- **Approved decision:** Ordered record events use a compact linear timeline.
- **Scope:** Page-specific pattern.
- **Figma proof:** Compact linear timeline and responsive stress proofs.
- **Responsive requirement:** The timeline is horizontal on desktop and
  vertical at narrow widths or 200% zoom.
- **Accessibility requirement:** Event order is conveyed through text and
  reading order, not visual position alone.
- **Prohibited regression:** Decorative chart or hidden timeline events.
- **Required evidence before acceptance:** Responsive screenshots.

### RT-GL-001 — Inline glossary hover and focus treatment

- **Approved decision:** CCLD terminology uses an inline glossary treatment.
- **Scope:** Sitewide.
- **Figma proof:** Inline glossary examples for `Group Home`,
  `Substantiated`, and `Type A`.
- **Responsive requirement:** Terms remain inline; the definition window may
  reposition to fit the viewport.
- **Accessibility requirement:** Terms use a dotted underline, keyboard focus,
  and a hover/focus definition window.
- **Prohibited regression:** Ordinary-link styling or repeated definition
  paragraphs.
- **Required evidence before acceptance:** Hover and focus screenshots.

### RT-ST-001 — Review flags represented primarily as badges

- **Approved decision:** Review flags are represented primarily as badges.
- **Scope:** Sitewide.
- **Figma proof:** Finding and badge examples and facility-result proof.
- **Responsive requirement:** Badges wrap without clipping.
- **Accessibility requirement:** Badges include visible text and do not rely on
  color alone.
- **Prohibited regression:** Review flags rendered only as warning panels.
- **Required evidence before acceptance:** Screenshot and semantic review.

### RT-ST-002 — No duplicated review-flag expression

- **Approved decision:** A review flag appears once in the current page context.
- **Scope:** Sitewide.
- **Figma proof:** Finding and badge examples and facility-result proof.
- **Responsive requirement:** Each flag retains one badge instance after
  reflow.
- **Accessibility requirement:** Badge text remains accessible.
- **Prohibited regression:** The same review flag repeated as both a badge and a
  separate panel.
- **Required evidence before acceptance:** Route-content review.

### RT-ACT-001 — Clear primary and recommended-next action

- **Approved decision:** Pages have a clear primary action and a clear
  recommended-next action where applicable.
- **Scope:** Sitewide.
- **Figma proof:** `Recommended-next action` and `Reviewer action rail`.
- **Responsive requirement:** Action priority remains intact after reflow.
- **Accessibility requirement:** Actions have descriptive names and visible
  focus.
- **Prohibited regression:** Competing primary actions.
- **Required evidence before acceptance:** Route screenshot and keyboard review.

### RT-DOM-001 — Source-derived and reviewer-created state separation

- **Approved decision:** Source-derived information and reviewer-created state
  remain visibly and semantically separate.
- **Scope:** Sitewide.
- **Figma proof:** Detail-oriented complaint proof and reviewer action rail.
- **Responsive requirement:** The source-derived and reviewer-created sections
  remain distinct across widths.
- **Accessibility requirement:** Visible labels and programmatic grouping
  identify the two domains.
- **Prohibited regression:** Reviewer-created state styled or described as a
  source fact.
- **Required evidence before acceptance:** Screenshot and semantic review.

### RT-TIER-001 — Reviewer, help, operator, and developer tier separation

- **Approved decision:** Reviewer, help, operator, and developer information
  remain in their proper product tiers.
- **Scope:** Sitewide.
- **Figma proof:** Reviewer-facing proofs exclude internals; permitted secondary
  disclosure demonstrates the boundary.
- **Responsive requirement:** Reflow must not introduce diagnostic content into
  the reviewer tier.
- **Accessibility requirement:** Content remains accessible where it is
  appropriately exposed in its own tier.
- **Prohibited regression:** Hashes, connector metadata, raw paths, or other
  technical internals displayed on a reviewer page.
- **Required evidence before acceptance:** Route-content and privacy review.

### RT-SRC-001 — Compact source availability and original-source action

- **Approved decision:** Reviewer pages show compact source availability and an
  original-source action without exposing traceability internals.
- **Scope:** Sitewide.
- **Figma proof:** Source actions in detail-oriented and responsive proofs.
- **Responsive requirement:** Source URL actions wrap independently while
  remaining clearly related.
- **Accessibility requirement:** `Open original source` and `Copy source URL`
  have distinct accessible names.
- **Prohibited regression:** Raw hash, raw path, connector, or traceability
  detail shown in the reviewer tier.
- **Required evidence before acceptance:** Screenshot and DOM review.

### RT-STATE-001 — Explicit component states

- **Approved decision:** Components explicitly implement applicable empty,
  partial, unavailable, error, loading, selected, hover, focus, and disabled
  states.
- **Scope:** Sitewide.
- **Figma proof:** Component State Matrix and actual component sets.
- **Responsive requirement:** States remain defined at the component level
  after reflow.
- **Accessibility requirement:** States have visible and programmatic
  distinctions.
- **Prohibited regression:** Claiming a state is designed without an actual
  component variant or concrete visual example.
- **Required evidence before acceptance:** Figma component inspection and
  implementation-state evidence.

### RT-PAG-001 — Large-corpus pagination and orientation

- **Approved decision:** `/ccld/facilities/intelligence` uses database-level
  seek/keyset pagination with exactly 25 facilities per page and a compact
  inventory orientation treatment.
- **Scope:** Cross-facility intelligence inventory for Issue #419.
- **Figma proof:** Pagination addendum node `59:463`; desktop first, middle, and
  last pages `59:469`, `59:505`, and `59:541`; approximately 500 px, mobile
  390 px, and 200% zoom `59:577`, `59:613`, and `59:649`; Previous and Next
  disabled states `59:685` and `59:721`; keyboard focus for Previous and Next
  `59:757` and `59:793`; applied filters `59:829`; print `59:868`; and empty
  filtered result `59:904`.
- **Responsive requirement:** Desktop may use restrained sticky orientation
  only while controls and focused content remain unobscured. Approximately
  500 px, mobile 390 px, 200% zoom, and print use normal document flow, and
  print disables sticky positioning. Pagination must not introduce horizontal
  page overflow.
- **Accessibility requirement:** Previous and Next are descriptive real links
  or buttons with semantic disabled states, logical focus order, and visible
  Civic Ledger focus treatment. `Showing X–Y of Z facilities` remains available
  to assistive technology without excessive result announcements.
- **Prohibited regression:** Numbered pages, arbitrary page jumps, `Page N of
  M`, facility-page OFFSET, progressive or deep OFFSET, full-corpus
  application-memory slicing or aggregation, obscured focused controls,
  duplicate facility inventories, or pagination that loses active filters or
  deterministic ordering.
- **Required evidence before acceptance:** Exact-route controlled evidence for
  every cited state node; adjacent-page reconciliation proving no duplicates or
  omissions; query evidence proving bounded database-level seek/keyset
  pagination with no facility-page OFFSET; a bounded ordered `LIMIT 1` query for
  the full-filtered-corpus Review next result; bounded current-page complaint,
  supporting-row, and reviewer-created-state hydration; keyboard-focus,
  responsive, print, disabled-state, applied-filter, empty-result, and
  horizontal-overflow evidence.

The inventory uses Previous and Next only. It does not render numbered pages,
arbitrary page jumps, or `Page N of M`. Its exact result-position wording is
`Showing X–Y of Z facilities`. Previous is semantically disabled on the first
page, Next is semantically disabled on the last page, and both navigation links
preserve the active filters and deterministic ordering. Changing a filter
returns to the first page.

Authorization, corpus/import scope, active filters, deduplication, governed
priority ordering, normalized facility name, and stable facility identity are
applied before seek pagination. The page query returns one bounded current page
and a separate total matching-facility count. Complaint and supporting rows and
reviewer-created state are hydrated only for facilities on the current page.
The governed full-filtered-corpus Review next result uses a separate bounded,
ordered `LIMIT 1` database query and must not require full-corpus hydration or
application-memory aggregation.

### RT-RWD-001 — Desktop, narrow, compact/mobile, and 200% zoom behavior

- **Approved decision:** The system has distinct desktop, narrow,
  compact/mobile, and 200%-zoom behavior.
- **Scope:** Sitewide.
- **Figma proof:** Responsive stress-proof frames.
- **Responsive requirement:** Navigation, controls, tables, and stacked rows
  visibly reflow rather than using the same layout at a narrower width.
- **Accessibility requirement:** Reading and keyboard order remain logical, and
  the primary workflow does not require horizontal page scrolling.
- **Prohibited regression:** The desktop layout merely narrowed without
  structural reflow.
- **Required evidence before acceptance:** Viewport screenshots.

### RT-A11Y-001 — Visible keyboard focus

- **Approved decision:** All interactive controls retain visible keyboard focus.
- **Scope:** Sitewide.
- **Figma proof:** Foundations focus system and copy-control Focus variant.
- **Responsive requirement:** Focus remains visible on light and dark
  backgrounds.
- **Accessibility requirement:** The approved composite focus treatment retains
  verified contrast.
- **Prohibited regression:** Focus removed, obscured, or communicated only by a
  subtle color shift.
- **Required evidence before acceptance:** Keyboard-focus screenshots.

### RT-A11Y-002 — Non-color-only semantic status

- **Approved decision:** Semantic statuses do not rely on color alone.
- **Scope:** Sitewide.
- **Figma proof:** Status badges and finding/badge examples.
- **Responsive requirement:** Status labels remain visible after wrapping.
- **Accessibility requirement:** Visible text and an appropriate icon accompany
  semantic color.
- **Prohibited regression:** Color-only status dots.
- **Required evidence before acceptance:** Screenshot and accessible-name
  review.

### RT-CP-002 — Copy success feedback and accessible announcement

- **Approved decision:** Successful copy provides visible feedback and an
  accessible announcement.
- **Scope:** Sitewide.
- **Figma proof:** Copy-affordance `Copied` state.
- **Responsive requirement:** Visible `Copied` feedback clears after 2000
  milliseconds.
- **Accessibility requirement:** Success is announced through
  `aria-live="polite"` or an equivalent accessible mechanism.
- **Prohibited regression:** Silent copy or persistent success state.
- **Required evidence before acceptance:** Interaction recording or focused
  interaction evidence.

### RT-STRESS-001 — Long-content and missing-value resilience

- **Approved decision:** Components withstand long content and missing or
  unavailable values.
- **Scope:** Sitewide.
- **Figma proof:** Stress-content example and four responsive stress proofs.
- **Responsive requirement:** Long names, summaries, badges, and unavailable
  values reflow without losing associated controls.
- **Accessibility requirement:** Value/control association and reading order are
  preserved.
- **Prohibited regression:** Clipping, inaccessible ellipsis, or detached copy
  controls.
- **Required evidence before acceptance:** Stress-content screenshots.

### RT-PRINT-001 — Print-safe behavior

- **Approved decision:** Reviewer-facing components have a print-safe treatment.
- **Scope:** Sitewide.
- **Figma proof:** Foundations print guidance and copy-component behavior note.
- **Responsive requirement:** Navigation and copy controls disappear in print;
  readable values remain.
- **Accessibility requirement:** Printed output uses black text and meaningful
  visible borders.
- **Prohibited regression:** Color-only printed meaning or hidden source values.
- **Required evidence before acceptance:** Print-preview evidence.

### RT-SAFE-001 — No invented scores, conclusions, or decorative KPI tiles

- **Approved decision:** The design does not invent risk scores, legal
  conclusions, or decorative KPI tiles.
- **Scope:** Sitewide.
- **Figma proof:** All pattern and responsive-proof frames.
- **Responsive requirement:** No new measures are introduced at any width.
- **Accessibility requirement:** Visible content uses plain factual language.
- **Prohibited regression:** Risk score, unsupported conclusion, or decorative
  KPI card introduced.
- **Required evidence before acceptance:** Content-inventory review.

## Evidence-report format

Every implementation evidence review must list each applicable requirement ID
using this format:

| Requirement ID | Result | Evidence | Notes |
|---|---|---|---|
| `RT-...` | `PASS`, `VARIANCE`, `REGRESSION`, or `NOT APPLICABLE` | Screenshot, DOM, interaction, token, print, or component evidence | Explanation and corrective action where required |

A result of `VARIANCE` requires explicit approval or repair.

A result of `REGRESSION` requires repair before acceptance.

A result of `NOT APPLICABLE` requires a page- or component-specific
justification.

## Implementation-prompt requirement

Every future reviewer-facing implementation prompt must:

1. Cite the applicable IDs from this document.
2. Identify the exact approved Figma frames.
3. State the applicable prohibited regressions.
4. Require exact-route screenshots at the relevant viewports.
5. Require the evidence handoff to classify every cited ID.
6. Stop implementation when the approved Figma artifact and this file cannot be
   reconciled.

## Visual authority

Figma remains the authoritative visual design environment.

This file provides shared, searchable, repository-readable governance and stable
requirement IDs. It does not authorize an implementation to substitute prose for
the actual approved visual reference.

The approved Checkpoint 3 reference frames carry this label:

> Approved implementation reference — variance requires approval
