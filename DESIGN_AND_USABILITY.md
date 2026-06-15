# Design and Usability Governance

## Purpose

This document defines how the local review experience should become useful,
understandable, accessible, visually organized, and pleasant to use across the
current local attorney-review aid workflows and the production-discovery phase.

The initial proof of concept improved the Datasette and SQLite review workflow
with review views, metadata, saved queries, documentation, script guidance, and
source-traceable exports. Datasette is now retained as a validation, inspection,
debugging, local exploration, and export-support layer, not as the primary future
reviewer UX.

Future primary review UX work should prioritize persistent navigation, guided
queues, saved reviewer state, annotations, correction workflows, contextual help,
source traceability, accessible exports, and fewer-click reviewer paths before
considering more Datasette metadata or saved-query UX.

The minimum hosted reviewer workflows, review states, annotation boundaries,
correction boundaries, and tester-readiness expectations are defined in
`PRODUCTION_DISCOVERY_REQUIREMENTS.md`.

## Intended users

The local review experience must support:

- Researchers and analysts reviewing public facility complaint history.
- Advocates reviewing public licensing records.
- Developers maintaining source connectors, extraction logic, schemas, and tests.
- Non-technical reviewers using local Datasette inspection views, CSV exports,
  and future primary review workflows.

The experience should assume that some reviewers are unfamiliar with database
terms, schema names, extraction confidence, or delay calculations.

## Current local review workflows

The local review experience should make these workflows easy to complete:

1. Open the local Datasette database after running a sample or live fetch script.
2. Start with review views rather than normalized implementation tables.
3. Filter complaints by facility number or facility name.
4. Review complaint dates, findings, allegation summaries, and review flags.
5. Inspect source traceability before relying on extracted fields.
6. Compare facility-level complaint counts and date ranges.
7. Export filtered review views or saved-query results as accessible CSV files.
8. Share notes using cautious language that preserves source limitations.

Reviewers should not need to understand every canonical table before completing
basic browsing, triage, source checking, or export tasks.

## Future primary review UX requirements

The future primary review experience should make these workflows easy to
complete without relying on Datasette as the main interface:

1. Resume review with persistent navigation and saved state.
2. Work through guided queues organized by reviewer task, facility, source
  traceability status, review flags, correction needs, and annotation state.
3. Add annotations without changing the preserved raw source record or
  canonical extracted fields.
4. Propose, review, import, or apply corrections with auditability and source
  traceability.
5. See contextual help at the point of use for fields, review flags, source
  traceability, limitations, and export cautions.
6. Export accessible, source-traceable review packets with clear headers and
  cautious public-source language.
7. Complete common reviewer paths with fewer clicks than the retained Datasette
  validation workflow can reasonably provide.

The future workflow must clearly distinguish source-derived values from
reviewer-created state such as review status, annotations, proposed corrections,
tester feedback, and export packet inclusion decisions. Status labels must not
imply source facts, legal conclusions, facility-wide conclusions, or verified
harm beyond what qualified reviewers establish from source records.

The first browser-accessible hosted reviewer UI shell is now a local/test,
server-rendered HTML surface at `/reviewer` and `/reviewer/records`. Its design
purpose is functional validation, not polish: local testers can list/search a
seeded source-derived record, see list-level reviewer-created note/status
indicators, open detail, inspect safe source traceability fields and safe
related seeded bundle context, add a reviewer note, set a reviewer status, and
see read-after-write reviewer-created state. Empty, invalid-form, and blocked
states should give clear next steps such as clearing search, returning to the
reviewer list, selecting a seeded record, or retrying valid note/status input.
Narrative
source fields are hidden in the browser shell. It must keep source-derived values visibly separate
from reviewer-created notes/statuses, keep local/test limitations visible, use
semantic headings, tables, labels, and accessible buttons, avoid color-only
meaning, and avoid unsupported legal, facility-wide, completeness, harm, abuse,
neglect, liability, or rights-deprivation conclusions.
Reviewer detail pages should orient first-time testers with a concise record
summary, clear source-traceability explanation, related source/facility/context
sections, visible reviewer-created state summaries, understandable note/status
actions, clear saved-state confirmations, CCLD queue/request/help navigation,
and feedback clues for reporting missing or confusing records.
Reviewer detail source traceability should help testers identify the selected
complaint record, distinguish source-derived identifiers from reviewer-created
state, understand which traceability fields are visible or missing in the
local/test record, and avoid treating missing local/test values as public-source
absence, completeness, legal, facility-wide, harm, abuse, neglect, liability, or
automated-finding conclusions.
Reviewer note/status confirmations should make the return path clear: saved
notes/statuses are reviewer-created state, queue progress and note/status cues
are derived from that state, the tester may need to resubmit the same local/test
facility/date request context to refresh the queue display, and the next record
should be chosen from the refreshed queue.

The first browser-accessible CCLD record request page is a local/test, server-
rendered HTML surface at `/ccld/records/request`. Its design purpose is to
return the MVP to the original user flow: enter a CCLD facility/license number,
optionally narrow by date range, see matching seeded CCLD records when they
already exist, load or refresh matching rows from local validated hosted seeded-
corpus output when needed, and continue into the hosted reviewer UI. Empty,
invalid, and load-result states should use plain language that distinguishes
missing local/test validated records from public-source completeness. The page
must not offer non-CCLD source selection, imply hosted live crawling, imply
generic connector execution, or hide the required outside-browser handoff when
broader retrieval requires an explicit live-fetch command and local/test
artifact build command before browser load/refresh.
The next guided version of that page can organize matching complaints as a
facility/date-scoped review queue, provide first-time workflow and key-term
help, show reviewer notes/status indicators from existing reviewer-created
state reads, and include a structured copyable feedback checklist without adding
feedback persistence.
That UI must keep source-derived records visibly separate from reviewer-created
notes/statuses and avoid implying production readiness or public-source
completeness.
The workflow-completion version can add progress counts and reviewer-status
filters derived from existing reviewer-created state so testers can distinguish
not-started, in-review, needs-follow-up, reviewed, and blocked records without
adding persisted queue state.
Queue usability should keep improving through presentation-only guidance when it
helps testers triage CCLD records: list-level triage summaries, note/status cues,
source-traceability availability cues, suggested next-record links, clear
filtered-empty states, and meaningful reviewer-detail actions are product
requirements when they reduce confusion without adding new persistence or
changing note/status behavior.
First-run accessibility polish is also MVP usability work, not cosmetic polish:
skip-to-main links, clear start-here sections, visible next-step instructions,
specific button/link text, and manual feedback-copy guidance are required when
they help a tester complete the CCLD facility lookup, request, queue, detail,
notes/status, and feedback loop without prior explanation.
The CCLD facility lookup version can add a local/test reference-data search path
before the request page so testers do not need to know the full facility/license
number. It should support a configured full local/test CSV with a committed tiny
fixture fallback, show which reference source is active, support searching safe
available CSV fields, show bounded readable results, carry the selected
facility/license number into the request form, preserve manual entry, and clearly
state that lookup rows are local/test reference assistance rather than complaint
source truth or completeness proof.
The request and queue pages should also make the active request context visible:
whether it came from facility lookup or manual entry, which facility/license
number and date range are being used, which local/test facility reference source
is active, and how to change facility/date criteria before reviewing queue
results.

Near-term hosted work should pass the deferred-readiness/product-benefit gate in
`GOVERNANCE_INVENTORY.md`. MVP usability is not cosmetic polish: user-friendly
layout, clear forms, contextual help, efficient facility lookup, understandable
results, accessible structure, and low-friction reviewer actions are product
requirements when they help local/test CCLD testers complete the workflow without
creating avoidable rework. Backend readiness, hardening, or checklist work should
be sequenced when it unlocks that workflow or removes a concrete MVP-blocking
risk.

The hosted scaffold and first local-only read-only source-derived views now
exist. Detailed hosted visual design may begin from that real shell, but early
design work must stay inside local-only, fixture/sample, read-only boundaries
until later implementation decisions approve database, import, authentication,
reviewer-state, deployment, or workflow behavior. The document-governance
dashboard concept may inspire later hosted reviewer UX patterns such as left
navigation, dashboard/status cards, review queues, source-traceability health
panels, contextual onboarding/help, light and dark mode support, and audit/
change-history patterns, but it must not be copied literally. Any adapted
design must preserve this project's source-traceability, accessibility,
cautious-language, tester feedback, and reviewer-state boundaries.

## Design principles

- Prefer review workflows over raw implementation exposure.
- Make the first useful screen obvious after a script completes.
- Preserve the public portal as the source of record.
- Keep every derived record connected to source URL, raw hash, connector details,
  and retrieval time.
- Treat Datasette as a retained validation and inspection layer while
  production-discovery defines the future primary review experience.
- Favor stable, documented local workflows over account-specific services or
  optional paid platform features.
- Treat extracted records as review aids, not authoritative conclusions.

## Usability principles

- Put the most common review fields together in human-readable views.
- Use plain labels in retained Datasette metadata where table or column names are
  terse.
- Preserve useful saved queries for validation, inspection, local exploration,
  and export support.
- Prioritize future reviewer state, queues, annotations, corrections,
  contextual help, and fewer-click paths over additional Datasette-primary UX.
- Keep scripts explicit about what to open next.
- Make empty, missing, or unknown values understandable in documentation and
  exports.
- Avoid requiring users to join tables manually for routine review tasks.
- Keep review terminology consistent across views, saved queries, exports, and
  documentation.

## Visual design principles

- Use visual organization to support scanning, comparison, and repeated review.
- Keep review pages quiet, dense, and readable rather than promotional or
  decorative.
- Prefer clear column order, labels, descriptions, and saved-query names over
  visual novelty.
- Do not add a frontend framework during production-discovery only to improve
  appearance or bypass architecture decisions.
- Do not add decorative graphics, branding treatments, or custom styling that
  distracts from source review and traceability.
- If future presentation styling is added, it must preserve keyboard access,
  visible focus indicators, contrast, semantic structure, and readable exports.

## Accessibility requirements

All user-facing review output must follow `ACCESSIBILITY_REQUIREMENTS.md`.

At minimum:

- Use semantic headings in documentation.
- Use descriptive link text.
- Keep Datasette table columns clearly named and documented.
- Preserve keyboard-operable workflows.
- Preserve visible focus indicators in any presentation layer.
- Do not use color alone to communicate findings, warnings, flags, or status.
- Use clear CSV headers in exports.
- Define field meanings and limitations in user documentation.
- Document known accessibility blockers in `KNOWN_LIMITATIONS.md` before any
  stable release.

## Terminology and plain-language rules

- Use "review flag" or "flagged for review" for screening indicators.
- Use "derived dataset" for extracted local data.
- Use "public portal" or "public source" for the source of record.
- Use "unknown" in user-facing explanations when a value is unavailable.
- Avoid unexplained acronyms in end-user documentation.
- Define technical terms such as raw hash, connector, extraction audit, and source
  traceability before expecting non-technical reviewers to use them.
- Do not describe missing dates as proof that an event did not happen.
- Do not describe a delay flag as proof that an investigation was delayed.

## Retained Datasette table and view usability expectations

Datasette review views retained for validation, inspection, debugging, local
exploration, and export support should:

- Put high-value review fields near the beginning of the view.
- Include facility number and facility name when reviewing complaint records.
- Include complaint control number when available.
- Include source URL and source traceability fields where reviewers need to verify
  extracted data.
- Group delay calculation fields and review flags in a predictable order.
- Prefer review views for common workflows and normalized tables for lower-level
  detail.
- Use metadata labels and descriptions to explain views, columns, and saved
  queries.
- Avoid exposing users to ambiguous status or flag columns without explanatory
  documentation.

The retained local review views should remain aligned with
`docs/user/local-review-workflow.md`.

## Saved-query expectations

Saved queries retained for validation, inspection, local exploration, and export
support should:

- Support common review tasks such as filtering complaints by facility, viewing
  records with review flags, checking source traceability, summarizing allegation
  counts, and listing newest reports.
- Use clear names and descriptions.
- Include source traceability columns when the query result may be exported or
  used for review notes.
- Avoid implying that review flags are conclusions.
- Prefer parameterized queries for reviewer-entered values such as facility
  number.

## Export usability expectations

CSV exports should:

- Keep clear, stable header rows.
- Preserve source traceability columns when records may be cited, shared, or
  reviewed outside Datasette.
- Include enough context for reviewers to understand facility, complaint, finding,
  dates, review flags, and source details.
- Avoid unexplained abbreviations.
- Avoid color-only or formatting-only meaning.
- Be documented as derived review outputs, not official source records.
- Include caution language in surrounding notes when exporting delay review flags.

## Source traceability expectations

Every extracted record must remain traceable to its source document. Review
experiences should make it easy to inspect:

- Source URL.
- Raw SHA-256 hash.
- Raw path when available locally.
- Connector name and version.
- Retrieval timestamp.
- Report index or document type when available.
- Extraction audit details when field-level review is needed.

Source traceability must not be removed to simplify a view, query, export, or
presentation layer when the output may be used for review or citation.

## Delay-flag caution language

Delay review flags are screening aids. They do not prove that an investigation
was delayed.

Use language such as:

```text
flagged for review based on available extracted dates
```

Do not use language such as:

```text
delayed investigation
```

unless a qualified reviewer has independently verified the source record and the
project has documented an approved basis for that conclusion.

Report date may be used as a review proxy only when no first investigation
activity date or visit date is available. Report date alone does not establish
when investigation activity began. Missing dates must be described as missing
from extracted fields, not as evidence that an event did not occur.

## POC scope versus later product work

Proven in the proof of concept and retained for local attorney-review aid:

- SQLite review views that support common reviewer tasks.
- Datasette metadata with clearer labels, descriptions, and saved queries.
- Script output that tells reviewers what command or view to open next.
- User documentation for browsing, filtering, source checking, and exporting.
- Accessible CSV export guidance.
- Fixture-backed tests for extraction and review behavior.
- Small usability improvements that preserve the existing Python, SQLite, and
  Datasette architecture.

Belongs in current production-discovery:

- Product requirements for persistent navigation, saved reviewer state, guided
  queues, annotations, corrections, collaboration, contextual help, accessible
  exports, tester feedback, hosted tester readiness, reset/reload processes, and
  fewer-click reviewer paths.
- Architecture boundaries for ingestion, storage, validation, review state,
  correction state, export generation, and future presentation.
- ADRs comparing production-stack options without selecting a stack before the
  requirements are reviewed.

Belongs in future production-build or production-operations work:

- A custom frontend application.
- Full review queues, assignment workflows, or reviewer accounts.
- Interactive dashboards beyond validation, inspection, or prototype work.
- Role-based access control for a hosted product.
- Custom charting or visualization layers.
- PDF report generation unless accessibility can be validated.
- Optional paid services or account-specific platform features unless explicitly
  approved and documented.

Production-discovery should define the primary reviewer UX requirements while
preserving source traceability, accessibility, cautious public-source language,
raw source preservation, and deterministic extraction safeguards.