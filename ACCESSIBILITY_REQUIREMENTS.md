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
	search, note, and status controls, table captions/headings for source-derived
	context, safe related seeded context, list-level reviewer-created state
	indicators, and reviewer-created state, and visible error or blocked-request
	messages with useful next-step links. Reviewer detail pages must include
	accessible record-summary, source-traceability, related-context, reviewer-state,
	action, saved-confirmation, navigation, and feedback-guidance sections with
	meaningful link text. Reviewer detail source traceability must use visible
	labels for selected-record identifiers, source URL, raw hash, raw path or
	local artifact references, connector/capture details, source document/report
	markers, missing-value wording, and non-conclusion boundary language.
	Reviewer note/status saved confirmations must expose return-to-queue guidance,
	same facility/date request-context reminders, queue-progress refresh guidance,
	and next-record guidance as visible text with descriptive links.
	Reviewer detail feedback handoff cues must be visible text near detail feedback
	guidance and must name record-specific observations a tester can carry into the
	manual checklist without requiring JavaScript or persisted feedback.
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
	Next-record navigation guidance must be visible text and must not rely on
	automatic refresh, JavaScript, assignment state, or record-claiming behavior.
	Filtered-empty queue recovery guidance must expose the active filter, same
	facility/date request context, all-records recovery action, and reviewer-
	created-state basis for status filters as visible text.
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
- CCLD local/test pages must use consistent plain-language terms for repeated
	concepts so screen reader users and first-time testers do not have to infer
	that different phrases refer to the same request, queue, reviewer-created
	note/status, source traceability, or manual feedback checklist behavior.

### Color and contrast

- Text and meaningful UI elements must meet contrast requirements.
- Do not use color alone to communicate findings, warnings, or status.

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
