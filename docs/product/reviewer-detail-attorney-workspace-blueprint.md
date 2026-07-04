# Reviewer Detail Attorney Workspace Blueprint

## Source Basis

This planning document is for the existing reviewer detail route:

`/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448`

It starts from the approved reviewer-surface direction in
`DESIGN_AND_USABILITY.md`, especially `UI-18` through `UI-22`: reviewer detail
should lead with complaint review, summarize source traceability while
preserving diagnostics, make note/status actions a guided review loop, reduce
repeated warning copy, and keep navigation task-based. It also follows the
accessibility, data-contract, security, privacy, and testing boundaries in
`ACCESSIBILITY_REQUIREMENTS.md`, `DATA_CONTRACT.md`,
`SECURITY_AND_PRIVACY.md`, and `TESTING_STRATEGY.md`.

The requested standalone source file
`CCLD RecordsTracker Product UX Lead Charter.md` was not present in this
checkout when this blueprint was drafted. This document therefore uses the same
attorney-facing reviewer detail direction already incorporated into
`DESIGN_AND_USABILITY.md` and should be reconciled with that charter if the file
is added or restored later.

## Page Purpose

Reviewer detail should become an attorney-facing complaint review workspace, not
a prettier raw-source dump. Its job is to help an attorney or advocate quickly
understand the selected public CCLD complaint record, identify why it may need
closer review, inspect source-backed facts, record cautious reviewer-created
status or notes, and continue the same facility/date review workflow.

The page must support public-record review and prioritization without implying:

- legal conclusions;
- source completeness;
- facility-wide conclusions;
- harm, abuse, neglect, liability, or rights-deprivation;
- official findings beyond source-derived public record values;
- automated verification, scoring, or record correction.

## Primary User Question

"What complaint record am I looking at, why might it matter for review, what
source facts are available, what review status exists, and what should I do
next?"

Every default-visible section should help answer that question. Anything that
does not help answer it belongs in a collapsed support area, an operator
diagnostic surface, or a developer-only debug surface.

## Above-The-Fold Content

The first screen should answer five things before an attorney reaches detailed
tables or raw fields:

1. What this is: complaint identifier/control number when available, record
   type, source label, and facility name/license number.
2. Why it may matter: cautious review cues based only on existing source-derived
   fields, such as finding/status, key date gaps, missing local/test values,
   existing proxy flags, related activity counts when already available, and
   whether the record is the suggested next item in the queue.
3. What source facts are available: compact source-derived fact chips or rows
   for complaint dates, visit/report/signed dates, allegation categories,
   finding/status, source URL availability, and traceability availability.
4. What reviewer-created state exists: current reviewer status, note presence or
   latest safe note summary, latest non-secret timestamp/actor label when
   available, visibly separate from source-derived facts.
5. What happens next: a focused action panel for updating status/notes,
   returning to the same queue, opening the suggested next record, opening packet
   preview/draft, or reporting an issue with safe context.

The default first screen must not show a giant raw table of extracted fields.
Raw field tables, import metadata, machine-readable keys, and diagnostics should
not dominate the attorney's initial review.

## Information Architecture

### Default Visible Sections

1. **Complaint review header**
   - Complaint/control number or fallback source record label.
   - Record type and source label.
   - Facility name and facility/license number.
   - Same facility/date queue context when available.
   - Brief local/test boundary and source-record limitation language.

2. **Review action panel**
   - Current reviewer-created status and note state.
   - Existing status control and note form.
   - Cautious field-note guidance near the controls.
   - Save confirmation and same-queue refresh guidance after changes.
   - Primary navigation to return to queue or continue to next record.

3. **Why this record may need review**
   - Cautious review signals derived only from existing fields.
   - Examples: substantiated/equivalent source finding when present, missing
     expected local/test values, proxy date flags, long date gaps already
     represented by current fields, or related facility activity counts already
     exposed through existing read seams.
   - Language must say "may need closer review" or "review cue"; it must not say
     "violation proved", "abuse", "neglect", "rights violation", "liable",
     "unsafe facility", or similar conclusions.

4. **Complaint and event facts**
   - Source-derived complaint received date, first investigation activity date,
     visit date, report date, signed date, finding/status, allegation category
     summary, and complaint/event identifiers when available.
   - Missing local/test values should be labeled as not available in the loaded
     record, not as absent from the public source.
   - Source-derived values must be visually and textually labeled separately
     from reviewer-created notes/status.

5. **Facility identity**
   - Facility name, facility/license number, facility type/program type, city,
     county, status, and capacity when already available.
   - These are context fields only. The page must not turn facility identity
     into a facility-wide judgment.

6. **Narrative and source text**
   - A concise source narrative excerpt may be visible when current security
     rules permit it.
   - Longer source narrative text should remain behind a disclosure.
   - Narrative text should be framed as public source text or extracted source
     text, not as verified fact.

7. **Review guidance and signals**
   - Plain-language guidance for interpreting missing values, proxy flags, date
     gaps, and source traceability.
   - Guidance should help attorneys decide whether to add a cautious
     reviewer-created note/status or use feedback when wording/context is
     confusing.
   - Guidance must not generate notes, store templates, edit source records, or
     imply a correction workflow exists.

8. **Related facility activity**
   - Related complaint/report/visit activity for the same facility and request
     context when already available through existing read seams.
   - Show counts, date ranges, or links as screening context only.
   - Avoid facility-wide conclusions, completeness claims, or risk scores.

9. **Source traceability summary**
   - Compact default summary naming available source URL, raw hash availability,
     raw path/artifact reference availability, connector/capture availability,
     and source document/report markers when present.
   - Include a reminder to check source traceability before relying on
     source-derived values.
   - Missing local/test traceability values must not be described as proof of
     public-source absence or source completeness.

### Collapsed Sections

1. **Source fields**
   - Full extracted source-derived field list.
   - Original labels/values when safe to display.
   - Machine-readable source record key, complaint IDs, document IDs, and stable
     identities.
   - This section may use a table, but it must start collapsed and must not be
     the default page experience.

2. **Full source traceability**
   - Source URL, raw SHA-256 hash, raw path or artifact reference, connector
     name/version, retrieval timestamp, report index, source document metadata,
     extraction audit context, and raw-artifact-preserved indicators when
     available and safe.
   - This preserves traceability for review and support without making hashes
     and connector mechanics the first thing attorneys read.

3. **Technical/operator diagnostics**
   - Import batch metadata, local/test corpus details, job/import counts,
     retrieval status references, validation warnings, safe operational
     timestamps, and diagnostic summaries.
   - Must remain safe: no secrets, tokens, cookies, provider claims, private
     URLs, server-local absolute paths, raw stack traces, connection strings,
     raw artifact contents, or unnecessary raw narrative content.

4. **Developer debug detail**
   - Local/dev-only details should stay outside the normal reviewer page unless
     a future approved task creates a safe diagnostic surface.
   - The reviewer default should link or disclose only safe support information.

## Primary Actions

Primary actions should be few, task-based, and available near the top:

- Save reviewer-created status.
- Save reviewer-created note.
- Return to the same facility/date queue.
- Continue to suggested next record when current queue context supports it.

These actions must use existing note/status behavior and audit paths only. They
must not add assignment, claiming, workflow-engine state, new reviewer state
kinds, annotations, corrections, or source-derived mutations.

## Secondary Actions

Secondary actions should be grouped under a clearly labeled secondary area or
"More actions":

- Open packet preview.
- Open printable packet draft.
- Report an issue through the existing feedback route with bounded safe context.
- Open help for source traceability, review cues, or reviewer-created status.
- Copy safe record context for manual feedback if existing flow requires it.
- Expand full source fields.
- Expand full source traceability.
- Expand diagnostics.

Secondary actions must not look visually equivalent to the primary review loop.
They must use descriptive link/button text and remain keyboard operable.

## Source And Raw Data Handling

Source traceability must be preserved, visible, and reviewable, but source
metadata must not dominate the default attorney view.

Default source handling:

- Show a compact source traceability summary by default.
- Name which traceability values are available and which are not available in
  the loaded local/test record.
- Keep source-derived values visibly separate from reviewer-created notes/status.
- Label source-derived values as source-derived.
- Use cautious language around missing values and proxy flags.

Collapsed source handling:

- Put the raw extracted field table behind disclosure.
- Put full hashes, connector details, import context, artifact references, and
  machine-readable keys behind disclosure or in a safe operator/developer
  surface.
- Do not expose raw artifact contents, unsafe raw narrative, server-local paths,
  private URLs, provider claims, secrets, or stack traces.

The page must never treat the loaded local/test record as the complete public
source record. The public CCLD portal remains the source of record.

## Diagnostics And Operator Detail Handling

Current diagnostics, operator details, raw field tables, import metadata, and
machine-readable keys should be handled as follows:

- **Raw field tables:** collapse by default under "Source fields" and keep them
  out of the above-the-fold experience.
- **Import metadata:** collapse under "Technical/operator diagnostics" or move
  to a safe operator diagnostic surface when such a surface exists.
- **Retrieval/job metadata:** show only safe state, counts, timestamps, warnings,
  and links needed for support. Do not show raw stack traces or private runtime
  values.
- **Machine-readable keys:** show only in collapsed technical/source sections
  unless a key is necessary to identify the selected record in a feedback or
  support handoff.
- **Connector/capture details:** summarize availability by default; disclose full
  safe details only on demand.
- **Developer-only internals:** keep local/dev-only unless a separately approved
  implementation creates a safe support view.

Diagnostics should help support the record review workflow; they should not make
attorneys parse implementation mechanics before understanding the complaint.

## Glossary And Acronym Support

The page should define high-impact CCLD terms without cluttering the review
flow. Glossary support should be lightweight and placed near first use, in help
disclosures, or in compact helper text.

Terms needing plain-language support include:

- CCLD: California Community Care Licensing Division.
- Facility/license number: the public licensing identifier used to find the
  facility in CCLD records.
- Complaint/control number: the source complaint identifier when available.
- Source-derived value: a value extracted from public source records.
- Reviewer-created status/note: local review state added by a tester or
  reviewer; not a source fact.
- Source traceability: the source URL, raw hash, retrieval/capture context, and
  related metadata used to check where a source-derived value came from.
- Raw hash: a checksum used to identify preserved raw source content.
- Connector: code that retrieves or processes source records.
- Proxy date/flag: an existing cue that a field may be standing in for a more
  specific source date or value.

Glossary UI should not require JavaScript to understand the page. If tooltips
are used later, the same definitions must also be available as visible or
screen-reader-readable text.

## Accessibility Expectations

The redesigned page should meet WCAG 2.1 AA-aligned project expectations:

- Use semantic headings in order.
- Include skip-to-main or equivalent navigation support when repeated navigation
  appears before primary content.
- Keep all forms, disclosures, links, and buttons keyboard operable.
- Preserve visible focus indicators.
- Give note/status controls accessible names and visible labels.
- Use meaningful link text such as "Return to this facility/date queue" rather
  than generic "Back" or "Click here".
- Use text labels for review cues, statuses, warnings, and traceability states;
  color and icons may support but must not carry meaning alone.
- Use accessible table captions/headings when tables appear, especially in
  collapsed source or diagnostics sections.
- Keep reviewer-created state, source-derived facts, traceability, actions,
  saved confirmations, navigation, and feedback guidance as identifiable
  sections.
- Provide visible missing-value and non-conclusion boundary language.
- Avoid unexplained acronyms in default-visible text.
- Ensure expanded/collapsed controls expose state to assistive technology.

## Visual Acceptance Criteria

For the exact target route, screenshot review should confirm:

- The first viewport identifies the complaint record, facility, source label,
  review status, source fact availability, and next action.
- The first viewport does not begin with or visually center a giant raw table of
  extracted fields.
- Primary actions are visually grouped as the review loop: status, note, save,
  return to queue, and suggested next record when available.
- Source-derived facts and reviewer-created state are visibly separate.
- "Why this record may need review" uses cautious review-cue language and does
  not imply legal, facility-wide, harm, abuse, neglect, liability, rights-
  deprivation, source-completeness, or automated-verification conclusions.
- Complaint/event facts are scannable without requiring the user to parse
  machine-readable keys.
- Source traceability is visible as a compact summary, with a route to full safe
  traceability details.
- Raw fields, import metadata, connector details, and diagnostics are collapsed
  or moved out of the default view.
- Narrative/source text is bounded and labeled as source text, with longer text
  behind disclosure when present.
- Related facility activity is framed as context for closer review, not as a
  risk score or facility-wide finding.
- High-impact CCLD terms are defined near first use or through accessible help.
- No secrets, private URLs, server-local absolute paths, raw stack traces,
  provider claims, cookies, tokens, credentials, raw artifact contents, or
  unnecessary sensitive narrative content are visible.
- Text fits within cards, panels, buttons, and tables at desktop and mobile
  widths.
- Keyboard focus order follows the review flow from summary, to actions, to
  complaint facts, to source traceability, to secondary/collapsed sections.
- Color is not the only carrier of status, traceability, warning, or action
  meaning.

## Implementation Boundaries

This blueprint authorizes planning only. A future implementation branch must
remain presentation-oriented unless separately approved.

Do not add or change:

- schemas or migrations;
- canonical source-derived fields;
- source-derived record contents;
- reviewer-created state model or bounded status values;
- audit behavior;
- feedback persistence or feedback workflow behavior;
- retrieval behavior, live crawling, connector execution, or source expansion;
- route behavior or new routes;
- exports, final reports, packet lifecycle state, or generated legal packets;
- annotations, corrections, correction decisions, assignments, claiming, or
  workflow-engine state;
- authentication, production OIDC, sessions, cookies, role models, or hosted
  access behavior;
- QNAP, Docker, Cloudflare, deployment, or production runtime files;
- raw artifact storage or raw source preservation behavior;
- tests, except focused documentation index/link updates if docs validation
  requires them.

Stop and request separate approval if implementation would require any of those
changes. The initial implementation should use existing safe fields and existing
read/write seams only, preserve source traceability, keep source-derived values
separate from reviewer-created notes/status, and remain cautious in all review
language.
