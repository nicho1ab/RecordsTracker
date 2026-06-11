# ADR-0002: Improve the Local Review Experience Before Building a Custom Frontend

## Status

Accepted

## Context

The proof of concept needs to help reviewers browse, filter, understand, verify,
and export derived complaint records. Reviewers need a useful local experience,
but the project charter says not to build a custom web application during the
initial proof of concept.

The project already uses Python, SQLite, and Datasette. SQLite can provide review
views, Datasette can provide a local browser interface, metadata can clarify
tables and columns, saved queries can support repeated workflows, documentation
can explain limitations, and scripts can guide users toward the right local
commands and views.

## Decision

The project will improve the Datasette and local review workflow first using:

- SQLite review views.
- Datasette metadata with clear labels, descriptions, and column notes.
- Saved queries for common review tasks.
- User documentation for browsing, filtering, source checking, and exporting.
- Script guidance that tells reviewers what to open next.
- Accessibility and plain-language review guidance.

The project will not add a custom frontend during the proof of concept only to
improve presentation or visual polish.

## Reason

Improving the local review workflow first keeps the project focused on source
traceability, extraction quality, data validation, and reviewer comprehension.
This approach also avoids unnecessary product complexity, avoids optional paid
platform dependencies, and keeps the baseline workflow usable in local VS Code
and Datasette.

## Consequences

- Review views and saved queries become the primary user-facing interface during
  the proof of concept.
- Datasette metadata and documentation must carry plain-language explanations of
  fields, limitations, source traceability, and delay-flag caution language.
- Usability work should improve table layout, labels, queries, exports, and
  scripts before introducing new interface technology.
- Future custom frontend work remains possible after the project validates the
  data model, review workflows, accessibility requirements, and product needs.
- The baseline branch must not add frontend frameworks or optional paid
  dependencies for this decision.