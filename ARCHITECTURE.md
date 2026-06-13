# Architecture

## Current architecture and production-discovery boundary

```text
Public source portal/API
   -> connector discovery
   -> raw fetcher
   -> raw file storage
   -> extractor
   -> normalizer
   -> contract validator
   -> SQLite database
      -> Datasette validation/inspection/export-support layer
      -> production-discovery boundary for future primary review UX
         -> future reviewer-created state layer
            (review state, annotations, proposed corrections, tester feedback,
             export packet decisions)
```

The proof of concept proved the ingestion, extraction, raw preservation, source
traceability, local review, and export path. Datasette is retained over SQLite
for validation, inspection, debugging, local exploration, and export support. It
is no longer the terminal primary presentation layer for the future product
direction.

The production-discovery boundary is where the project defines requirements and
architecture decisions for reviewer state, guided queues, annotations,
corrections, collaboration, accessibility, exports, and source traceability. This
document does not select a production stack.

## Components

### Connectors

Connectors are source-specific modules responsible for discovering, fetching, and extracting data from one public data source.

### Raw source storage

Raw source files are stored in ordinary file storage under `data/raw/`. Each file must have a stable name, source URL, retrieval timestamp, and SHA-256 hash.

### Structured storage

SQLite is the initial database. PostgreSQL may be introduced later if concurrency, multi-user editing, or dashboarding requires it.

### Presentation

Datasette is the retained browser/search/API interface for validation,
inspection, debugging, local exploration, and export support because it can
expose SQLite data quickly without creating a custom application.

### Production-discovery review boundary

The future primary review experience is undecided. Production-discovery must
define product requirements and architecture boundaries before selecting a stack
or building a production application.

The future review boundary must account for persistent navigation, guided
queues, saved reviewer state, annotations, correction workflows, contextual help,
collaboration constraints, accessible exports, and source traceability.

The minimum workflow and hosted tester readiness requirements are defined in
`PRODUCTION_DISCOVERY_REQUIREMENTS.md`.

### Future reviewer-created state layer

Review state, annotations, proposed corrections, tester feedback, and export
packet inclusion decisions are future application/reviewer state. They must stay
separate from source-derived canonical data unless a future schema ADR approves
the persistence model.

The layer must preserve original extracted values, source document traceability,
raw source preservation, and extraction audit context where available. Proposed
corrections may influence a reviewed export presentation only through an
explicit traceable correction layer; they must not overwrite raw files or erase
original extracted values.

## Boundaries

- The repository owns ingestion, extraction, validation, storage, documentation, and tests.
- The public portal remains the public source of record.
- Raw storage is evidence for reproducibility and regression testing, not a replacement for the public portal.
- Datasette is a retained validation, inspection, debugging, local exploration,
  and export-support layer, not the governed primary future reviewer UX.
- Reviewer-created state for hosted review workflows is separate from
  source-derived canonical records and must be defined by production-discovery
  requirements and future ADRs before implementation.
- Production stack selection belongs in future ADRs after production-discovery
  requirements are documented.

## Accessibility

Any user-facing output must meet the accessibility requirements in `ACCESSIBILITY_REQUIREMENTS.md`. Retained Datasette views, Datasette templates/plugins, exports, prototypes, and future UI layers must be evaluated before use.
