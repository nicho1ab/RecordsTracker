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
	messages with useful next-step links.
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
	queue, reviewer notes, and reviewer status. Queue progress summaries and status
	filters must use text labels, form labels, and visible counts rather than
	color-only indicators.

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
