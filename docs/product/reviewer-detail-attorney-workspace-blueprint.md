# Reviewer Detail Attorney Workspace Blueprint

## Source Basis

This blueprint applies to the existing reviewer detail route:

`/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448`

It follows the current RecordsTracker product-tier direction in
`DESIGN_AND_USABILITY.md`: reviewer-facing pages should show only what helps an
attorney understand the open record, why it may matter, what source-derived facts
are available, what reviewer-created state exists, and what to do next.

## Page Purpose

Reviewer detail is an attorney-facing complaint review workspace. It is not a
source/debug/scaffold page and must not expose support, operator, raw source, or
developer details in the primary reviewer tier merely because older tests or
docs expected them.

The page must avoid legal conclusions, source-completeness claims,
facility-wide conclusions, harm/abuse/neglect/liability/rights-deprivation
claims, automated verification, scoring, or correction decisions.

## Primary User Question

"What complaint record am I looking at, why might it matter for review, what
source-derived facts are available, what reviewer-created state exists, and what
should I do next?"

## Reviewer-Facing Tier

Default-visible reviewer detail content should include:

- Complaint/control identity and record type.
- Facility identity once near the top: facility name, facility/license number,
  type/program type when available, status, and county.
- A concise source narrative or complaint summary near the top.
- A compact linear complaint/investigation timeline with ordered milestones.
- Finding/status and allegation summary.
- Review-flag badges as the primary expression of review flags.
- Reviewer-created status/note state and the existing status/note controls when
  useful to the current review task.
- Focused actions: open the public source link when available, return to the
  facility queue, open the next flagged record, save status, and save note.
- Copy affordances next to useful core values such as facility/license number,
  complaint/control number, key dates, finding/status, visible source URL, and
  complaint summary or source narrative.

Dates displayed on reviewer detail should use `MM/DD/YYYY` without times unless
the time is part of source narrative text rather than a timestamp field.

## Approved First Investigation Activity Date Evidence

The approved source-to-claim interaction is governed by `RT-SRC-002` and the
Figma file `SYszaxbcMK8Ce2ywrUiu4q`, section `RT-SRC-002 • Reviewer detail
source evidence`, node `64:2`. It applies only to the existing reviewer-detail
route and only to the `First investigation activity date` claim. Facility/license
number and complaint/control number provide context; they are not additional
field-level evidenced claims.

### Component Hierarchy And Action Placement

Within the compact investigation timeline, the `First investigation activity
date` milestone contains:

1. The visible claim label and readable `MM/DD/YYYY` date.
2. A `Copy date` control beside the date.
3. A restrained `View source evidence` trigger associated with that claim.
4. When open, a secondary evidence detail immediately following the claim and
   trigger in reading order.
5. Within that detail, a separate `Open original source` action.

The readable date stays visible when evidence is closed and when it is open.
`Copy date`, `View source evidence` or `Close source evidence`, and `Open
original source` remain separate controls; none may perform another control's
action.

The evidence detail contains only:

- the displayed `First investigation activity date`;
- one bounded source event sentence;
- the source section;
- complaint or report identity;
- a reviewer-safe preserved-source status; and
- the separate `Open original source` action.

### State Names

- `closed`: show the readable date, `Copy date`, and `View source evidence`; do
  not show the evidence detail.
- `open`: keep the readable date visible, label the trigger `Close source
  evidence`, and show all approved evidence content plus `Open original source`.
- `document-only`: state that document-level provenance is available but
  field-level support for the date is unavailable. Do not imply passage-level
  verification.
- `field-partial`: show available bounded field evidence and identify the
  unavailable evidence part without claiming that the source is complete.
- `source-unavailable`: keep the claim readable, explain that the preserved
  source document cannot currently be opened, and do not present a misleading
  active original-source action.
- `print`: show the supported claim, bounded evidence, reviewer-safe source
  status, and readable original-source URL while hiding interactive,
  navigation, copy, and reviewer-created controls.

These states correspond to the approved Figma proofs `Desktop evidence closed`,
`Desktop evidence open`, `Document-level-only provenance`, `Field provenance
incomplete`, `Source document unavailable`, and `Print state`.

### Responsive Behavior

- Desktop preserves the approved closed/open placement within the timeline.
- Narrow desktop reflows the open evidence within the timeline region without
  detaching it from the date.
- Mobile compact uses the approved compact action and touch-target treatment;
  the readable date and action names remain available without icon-only meaning.
- At 200% zoom, the timeline and evidence use normal document reflow with no
  horizontal page scrolling, clipping, or content overlap.

The responsive proofs are `Narrow desktop evidence open`, `Mobile compact
evidence open`, and `200% zoom reflow` in node `64:2`.

### Keyboard, Focus, And Accessible Names

All controls are keyboard operable and retain visible Civic Ledger focus. The
logical order within the milestone is:

1. `Copy First investigation activity date`.
2. `View source evidence for First investigation activity date` or `Close source
   evidence for First investigation activity date`.
3. The opened evidence content in document reading order.
4. `Open original source for First investigation activity date`.

Closing the evidence returns focus to its evidence trigger. Accessible names
must identify the action and target without relying on icon, color, position,
hover, or pointer input. The compact/mobile action preserves the approved touch
target. Keyboard and focus evidence must match `Keyboard focus` in node `64:2`.

### Domain Separation And Initial Scope

The claim, evidence detail, source availability, and original-source action stay
inside the source-derived timeline domain. Reviewer-created notes, status, and
actions remain in their separately labeled and programmatically grouped domain.

This approval does not authorize field-level evidence for any other dates,
findings, allegations, deficiencies, regulations, plans of correction, facility
name, or facility type. It does not authorize extraction, schema, persistence,
read-model, or application changes by itself.

## Out Of Reviewer Tier

Reviewer detail must not render these as primary page content:

- Source traceability detail sections.
- Raw SHA-256 values, connector metadata, source artifact identity, source
  document IDs, raw paths, raw artifact references, report indexes, retrieval
  timestamps, extraction audit details, field-level traceability, or raw
  traceability tables.
- Database IDs, full narratives, raw field dumps, legal conclusions, or source-
  completeness claims. `RT-SRC-002` permits only its bounded evidence detail and
  does not move these internals into the reviewer tier.
- Source-derived value-check tables.
- Full source-derived field dumps.
- Selected source-derived bundle summaries or related source-derived row tables.
- Technical/operator/runtime details.
- Facility context cues, detail navigation dumps, first-run detail steps, or
  operator setup/runtime guidance.
- Issue-report bridge copy, feedback checklist bridges, duplicate feedback
  checklists, or repeated issue/help/return action dumps.
- Cautious note-writing examples, how-to-read guidance, field definitions, or
  first-run orientation.

Those items should move to Help, support/operator diagnostics, developer/debug
surfaces, packet preparation, feedback, or future data/enrichment work as
appropriate. Moving them out of reviewer detail must not remove source
traceability, raw-source preservation, audit behavior, source-derived records,
reviewer-created persistence, retrieval, exports, or diagnostics from the
system.

## Accessibility Expectations

Reviewer-facing content must remain accessible: semantic headings, labeled
forms, meaningful links/buttons, keyboard-operable controls, visible focus,
non-color-only status/flag meaning, accessible copy controls, and readable
missing-value language.

Help/support/operator/developer content must also be accessible where exposed,
but accessibility requirements must not force technical/source/debug/help
sections onto the primary reviewer page.

## Visual Acceptance Criteria

For the target route, visual review should confirm:

- The first viewport identifies the complaint, facility, source narrative,
  timeline, finding/status, review-flag badges, reviewer-created state/action,
  and focused next actions.
- The page is materially shorter than the old scaffold/debug version.
- Facility facts appear once near the top.
- Review flags are not duplicated as both badges and cards/tables.
- Source traceability internals, value-check tables, full source fields, source
  bundle rows, technical/operator details, first-run steps, issue bridges, and
  Help-only guidance are absent from reviewer detail.
- Existing note/status write behavior and read-after-write state still work.
- The `First investigation activity date` remains visible in the closed and open
  evidence states, and the bounded interaction matches every approved node
  `64:2` state without implying support for another field.

## Implementation Boundaries

Do not add or change schemas, migrations, canonical source-derived fields,
source-derived records, reviewer-created state models, audit behavior, feedback
workflow behavior, retrieval behavior, exports, auth, QNAP/Docker/Cloudflare, or
deployment behavior. Presentation changes should use existing safe fields and
existing read/write seams only.
