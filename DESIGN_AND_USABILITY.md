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

Detailed hosted visual design should begin after the hosted scaffold and first
read-only source-derived views exist. The document-governance dashboard concept
may inspire later hosted reviewer UX patterns such as left navigation,
dashboard/status cards, review queues, source-traceability health panels,
contextual onboarding/help, light/dark mode support, and audit/change-history
patterns, but it must not be copied literally. Any adapted design must preserve
this project's source-traceability, accessibility, cautious-language, tester
feedback, and reviewer-state boundaries.

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