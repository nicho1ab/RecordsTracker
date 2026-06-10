# ADR-0004: Treat Accessibility as a Release Gate

## Status

Accepted

## Context

The project must meet ADA digital accessibility requirements.

## Decision

Accessibility requirements are release gates for all user-facing documentation, exported data views, and presentation layers.

## Reason

Accessibility is not an optional enhancement. It must be built into project structure, testing, documentation, and user-facing output.

## Consequences

- Documentation must use accessible headings, link text, table structure, and plain language.
- Datasette pages and any future UI must be tested for keyboard access, screen reader semantics, color contrast, and responsive behavior.
- Accessibility exceptions must be documented in `KNOWN_LIMITATIONS.md`.
