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

## Out Of Reviewer Tier

Reviewer detail must not render these as primary page content:

- Source traceability detail sections.
- Raw SHA-256 values, connector metadata, source artifact identity, source
  document IDs, raw paths, raw artifact references, report indexes, retrieval
  timestamps, extraction audit details, field-level traceability, or raw
  traceability tables.
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

## Implementation Boundaries

Do not add or change schemas, migrations, canonical source-derived fields,
source-derived records, reviewer-created state models, audit behavior, feedback
workflow behavior, retrieval behavior, exports, auth, QNAP/Docker/Cloudflare, or
deployment behavior. Presentation changes should use existing safe fields and
existing read/write seams only.
