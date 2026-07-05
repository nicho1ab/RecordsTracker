# Accessibility Requirements

## Standard

The project must meet ADA digital accessibility expectations by aligning user-facing output with WCAG 2.1 AA or newer equivalent requirements where practical.

## Scope

Accessibility requirements apply to:

- Documentation
- Datasette presentation pages
- Exports intended for end users
- The local/test hosted reviewer UI shell
- The local/test hosted CCLD record request page
- Future dashboards
- Future review interfaces
- Generated reports

## Requirements

### Structure

- Use semantic headings in order.
- Do not skip heading levels for visual effect.
- Use descriptive link text.
- Provide skip-to-main or equivalent page-navigation aids on hosted local/test
	review pages where repeated navigation appears before primary content.
- Avoid instructions that rely only on color, position, or shape.

### Keyboard access

- All interactive user-facing views must be operable by keyboard.
- Focus order must be logical.
- Visible focus indicators must be preserved.

### Screen reader support

- Tables must have clear column headings.
- Charts must have text alternatives or data tables.
- Form fields must have accessible names.
- The local/test hosted reviewer UI shell must use semantic headings, labeled
	search, note, and status controls, list-level reviewer-created state
	indicators, reviewer-created state, and visible error or blocked-request
	messages with useful next-step links. Reviewer detail pages must include
	accessible reviewer-facing content for complaint identity, facility identity,
	source narrative, compact timeline, finding/allegation summary, review-flag
	badges, reviewer-created state/actions, saved confirmations, and focused
	navigation with meaningful link/button text.
	Reviewer-facing pages are not required to expose technical/source/debug/help
	sections in the primary page to satisfy accessibility. Help, support,
	operator, source traceability internals, source-derived value-check tables,
	full field dumps, related source-bundle rows, connector metadata, hashes,
	facility-context cues, first-run guidance, field-note guidance, feedback
	checklist bridges, and issue-report instructions must be accessible where they
	are exposed in Help, support/operator, developer/debug, packet, or feedback
	surfaces, but they should not be forced onto reviewer detail solely for
	accessibility coverage.
	Reviewer note/status saved confirmations must expose concise visible return,
	next-record, and unchanged-source-derived-record guidance with descriptive
	links. Any copy-to-clipboard affordance must have an accessible name and must
	not be the only way to read the copied value.
- The local/test hosted CCLD record request page must use semantic headings,
	labeled facility/license number and date controls, accessible validation
	messages, labeled local validated load controls, table captions/headings for
	matched seeded records, descriptive reviewer links, and visible no-match or
	load-result guidance that does not rely on color or position alone. Outside-
	browser live-fetch and artifact-builder handoff guidance must remain visible
	plain text or code text with surrounding explanation. Guided result queues and
	help pages must use semantic headings, table captions or clear section
	headings, meaningful action link text, and plain-language definitions for
	facility/license number, date range, loaded records, source records, review
	queue, reviewer notes, and reviewer status.
	No-match and local validated load guidance must expose searched criteria,
	loaded local/test row counts, local validated load state, criteria-correction
	next steps, outside-browser preparation steps, and feedback checklist guidance
	as visible text.
	Queue progress summaries and status
	filters must use text labels, form labels, and visible counts rather than
	color-only indicators. Feedback checklists must have an associated label and
	help text and must be presented in a copyable control or equivalent plain text.
	Queue triage summaries must expose counts, reviewer note/status cues, source-
	traceability availability cues, suggested next-record links, filtered-empty
	guidance, and meaningful reviewer-detail link text as visible text, not color
	or layout alone.
	Queue pages must use visible wording that source-derived summary values should
	be checked on reviewer detail when fields look missing, confusing, or proxy-
	related.
	Next-record navigation guidance must be visible text and must not rely on
	automatic refresh, JavaScript, assignment state, or record-claiming behavior.
	Filtered-empty queue recovery guidance must expose the active filter, same
	facility/date request context, all-records recovery action, and reviewer-
	created-state basis for status filters as visible text.
	Hosted local/test reviewer status-filter summaries must expose the active
	reviewer-created status filter, records shown under that filter, total records
	in the same facility/date queue, available status values, and filtered-empty
	recovery actions as visible text. These cues must not rely on color, layout,
	icons, or implicit context, and must state that status filters are reviewer-
	created queue views rather than source-derived facts, assignment, record
	claiming, persisted queue state, or source-completeness proof.
	Hosted local/test packet preview and packet draft pages must expose packet
	readiness as visible text, including active facility/date context, included
	record counts, source-traceability checks, reviewer-created note/status cues,
	possible correction-readiness concerns, feedback recovery for confusing or
	risky packet/export-readiness content, and boundaries that the pages are not
	legal reports, final exports, certified reports, product-generated exports,
	packet lifecycle state, or source-completeness proof. These cues must not rely
	on icons, color, layout, print styling, or implicit context alone.
	Request-context confirmation must expose lookup versus manual-entry origin,
	facility/license number, date range, active facility reference source, and
	change-facility/date navigation as visible text with descriptive links.
	First-run CCLD pages must expose visible start-here or next-step guidance,
	specific form button text, and manual feedback-copy instructions without
	requiring JavaScript.
	Facility lookup controls must have associated labels and help text, lookup
	results must use table captions or equivalent result headings, selection links
	must have meaningful text such as "Use this facility", and empty, no-match,
	too-many-results, active-reference-source, fallback, and malformed-CSV states
	must be visible without relying on color.
- The tester feedback page must provide accessible labels for feedback type and
	description, expose validation errors as visible text, provide safe
	unconfigured, success, and failure states, and keep submit controls keyboard
	operable without requiring JavaScript.
- Future controlled CCLD retrieval job pages or status panels must expose job
	state, validation blocks, rate-limit messages, safe warnings, result counts,
	and queue links as visible text with semantic headings, labeled controls,
	keyboard-operable refresh/navigation actions, and non-color-only status. They
	must not require JavaScript to understand whether a job is queued, running,
	completed, completed with warnings, failed, blocked by validation, or
	rate-limited.
- CCLD local/test pages must use consistent plain-language terms for repeated
	concepts so screen reader users and first-time testers do not have to infer
	that different phrases refer to the same request, queue, reviewer-created
	note/status, source traceability, or manual feedback checklist behavior.
- Shared workflow indicators should expose each visible step's purpose as
	screen-reader-readable text, not only as visual position, color, or compact
	labels. Visually hidden helper text is acceptable when the same information
	would otherwise crowd the compact workflow rail.
- Hosted local/test workflow pages with repeated navigation should include
	visible keyboard-flow guidance near the workflow indicator or primary form
	controls so testers can move from Home, Facility Lookup, Record Request,
	Review Queue, Reviewer Detail, Note/Status actions, Packet Preview/Draft,
	Feedback, and Help without relying on color, layout, or pointer-only cues.

### Color and contrast

- Text and meaningful UI elements must meet contrast requirements.
- Do not use color alone to communicate findings, warnings, or status.
- Traffic-light review signals may be used where helpful: green for ready,
  complete, or no action needed; yellow for review recommended or missing
  context; and red for blocked, failed, or action required. Each status must be
  paired with visible text and accessible labels.
- Reviewer-facing status, warning, and review-flag language must remain concise
  enough to support the workflow without dominating the page.

### Actions and navigation

- Navigation may be styled as tabs or buttons when semantic structure and
  keyboard operation remain clear.
- In-page action groups must not mix links and buttons as visually equivalent
  controls.
- Ordered lists must not be used to structure buttons, form controls, dropdowns,
  or other non-text interactive elements.
- Primary, secondary, and "More actions" controls must have accessible names
  that explain the action without relying on icon, color, or position alone.
- Print/export controls must identify whether they open a printable page,
  trigger browser print, download a file, or open another workflow step.

### Plain language

- End-user documentation must use clear language.
- Define data fields and limitations.
- Avoid unexplained acronyms.

### Exports

- CSV exports must include clear headers.
- Reports must include explanation of fields and limitations.
- PDF generation is out of scope unless accessibility can be validated.

## Testing

Use a combination of:

- Keyboard-only review
- Browser accessibility tools
- Screen reader spot checks
- Automated checks where available
- Manual checklist in `docs/developer/accessibility.md`

## Release gate

A release cannot be marked stable if known accessibility blockers exist without being documented in `KNOWN_LIMITATIONS.md`.
