# ADR-0007: Evaluate Hosted Tester MVP Production Stack Direction

## Status

Accepted

## Context

The project is in production-discovery for a source-traceable public-record
review solution. The proof of concept already provides a Python ingestion and
extraction pipeline, raw source preservation, extraction audit records,
fixture-backed validation, SQLite storage, retained Datasette validation and
inspection workflows, and source-traceable exports.

ADR-0005 established that Datasette is no longer the governed primary future
reviewer experience. ADR-0006 established that the hosted tester MVP needs a
primary reviewer application layer separate from Datasette, while Datasette
continues as a validation, inspection, debugging, local exploration,
export-support, and transition-comparison layer.

The hosted tester MVP must support authenticated tester access, a seeded
public-record test corpus, facility search and selection, complaint review
queues, complaint detail review, persistent review state, annotations, proposed
corrections, correction decisions, source verification notes, tester feedback,
export packet selection, source-traceable exports, reset/reload, accessibility
validation, pilot-level auditability, and separation of source-derived canonical
data from reviewer-created state.

This ADR evaluates production stack directions against those project-specific
requirements. It does not scaffold an application, add dependencies, change
schemas, alter extraction behavior, add connectors, implement authentication,
implement review queues, implement annotations, implement corrections, implement
hosted exports, or modify Datasette-primary UX.

## Decision Drivers

- Preserve source traceability through source URL, raw hash, raw path where
  available, connector metadata, retrieval timestamp, report index where
  available, and extraction audit context.
- Preserve raw source files and deterministic extraction behavior.
- Keep source-derived canonical data separate from reviewer-created state.
- Support accessible hosted review workflows, including keyboard access, clear
  structure, screen reader support, contrast, non-color-only status, plain
  language, and accessible exports.
- Support authenticated tester access and role-aware reviewer workflows.
- Support auditability for review state changes, annotations, correction
  proposals, correction decisions, feedback, export packet selections, reset and
  reload events, and access-relevant pilot events.
- Support correction, annotation, queue, saved-state, and feedback workflows.
- Support source-traceable export generation with caution language.
- Support reset/reload for a seeded test corpus.
- Keep local development and CI validation practical for a small Python-centered
  repository.
- Avoid optional paid platform dependencies in the baseline workflow.
- Preserve the current Python extraction investment and fixture-backed tests.
- Reduce rework risk while moving quickly enough to reach a hosted tester MVP.
- Leave room for eventual production operations decisions.

## Options Considered

### Option 1: Python API plus hosted relational database plus separate web frontend

The existing Python extraction pipeline remains the upstream source-derived data
producer. A Python API exposes review workflows, a hosted relational database
stores imported source-derived records plus reviewer-created state, and a
separate frontend provides the primary reviewer UX.

Strengths:

- Preserves current Python extraction investment and test habits.
- Keeps source-derived data and reviewer-created state behind explicit API and
  database boundaries.
- Fits auditability, correction workflows, queues, feedback, and reset/reload
  requirements well.
- Gives a clear migration path from SQLite/Datasette to hosted review workflows
  while retaining Datasette for validation and comparison.

Tradeoffs:

- Introduces more moving parts than the current local workflow.
- Requires future ADRs for API framework, frontend framework, database,
  authentication provider, hosting, sync/import, export generation, and audit
  logging.

### Option 2: Full-stack JavaScript or TypeScript application

A single full-stack application handles UI, API routes, authentication
integration, database access, and hosted review workflows while preserving the
existing Python extraction pipeline as an upstream process.

Strengths:

- Can move quickly for web UI, routes, authentication integration, and frontend
  behavior if the team is comfortable with the stack.
- May reduce app/API/frontend boundary overhead for the hosted review layer.
- Mature ecosystem for accessible UI testing and deployment.

Tradeoffs:

- Splits the system across Python extraction and JavaScript/TypeScript review
  application concerns.
- Raises rework risk around data import, source traceability, and correction
  semantics if the full-stack app becomes the center of gravity too early.
- Adds a second primary language/toolchain to a Python-centered project.

### Option 3: Low-code or internal-tool platform

A low-code or internal-tool platform supports early tester review workflows
while the extraction pipeline remains separate.

Strengths:

- Fastest path to basic CRUD-like review forms and internal tester workflows.
- Could help validate workflow language, queue needs, and correction states
  before a custom build.

Tradeoffs:

- Risky fit for strict source traceability, correction auditability,
  accessibility validation, reset/reload, export caution language, and public
  repository portability.
- May depend on optional paid services or account-specific platform features.
- Can create migration and rework risk if tester workflows become embedded in a
  platform that cannot enforce project safeguards.

### Option 4: Continue with SQLite/Datasette plus lightweight extensions

SQLite and Datasette remain the primary review surface with lightweight
extensions or metadata additions.

Strengths:

- Lowest new infrastructure cost.
- Best fit for validation, inspection, debugging, local exploration,
  source-traceability checks, and export support.
- Preserves current local development simplicity.

Tradeoffs:

- ADR-0005 and ADR-0006 already establish that Datasette is no longer the
  primary future reviewer UX.
- Poor fit for authenticated hosted tester access, persistent reviewer state,
  guided queues, annotations, correction decisions, audit events, reset/reload,
  and fewer-click reviewer workflows as primary product behavior.
- Should remain a retained support layer, not the hosted tester MVP direction.

### Option 5: Hybrid transition approach

Retain SQLite and Datasette for local validation, debugging, inspection,
transition comparison, and export-support checks. Preserve the existing Python
ingestion and extraction pipeline. Introduce a hosted relational database for
imported source-derived records and reviewer-created state, plus a small hosted
reviewer application/API boundary for authenticated tester workflows.

Strengths:

- Best preserves current Python extraction investment while creating the hosted
  application boundary required by ADR-0006.
- Keeps source-derived data and reviewer-created state separable in the hosted
  model.
- Allows Datasette and SQLite to continue validating hosted behavior during the
  transition.
- Supports future reviewer-state data model, authentication, audit, export, and
  reset/reload ADRs without prematurely choosing vendors.
- Reduces rework risk by making the sync/import boundary explicit before app
  build work.

Tradeoffs:

- Requires careful future decisions for source-derived import/sync,
  reviewer-created state persistence, audit events, export generation, and
  tester data retention.
- Requires coordination between local validation data and hosted tester data.

## Comparison Table

| Criterion | Python API + relational DB + frontend | Full-stack JS/TS app | Low-code/internal tool | SQLite/Datasette extensions | Hybrid transition |
|---|---|---|---|---|---|
| Source traceability | Strong if API and schema enforce traceability | Strong if import model is disciplined | Variable and platform-dependent | Strong for local validation | Strong; local validation plus hosted boundary |
| Raw source preservation | Strong; keeps Python pipeline upstream | Strong if Python pipeline remains authoritative | Variable | Strong | Strong |
| Source/reviewer-state separation | Strong | Medium to strong | Variable | Weak for hosted reviewer state | Strong |
| Accessibility | Strong with deliberate UI validation | Strong with deliberate UI validation | Variable | Limited by Datasette/customization | Strong with deliberate UI validation |
| Authentication and roles | Strong | Strong | Variable to strong | Weak as primary hosted UX | Strong, deferred to auth ADR |
| Auditability | Strong | Strong | Variable | Weak for hosted reviewer workflows | Strong |
| Corrections and annotations | Strong | Strong | Variable | Weak as primary workflow | Strong |
| Queues and saved state | Strong | Strong | Variable | Weak as primary workflow | Strong |
| Export generation | Strong but needs ADR | Strong but needs ADR | Variable | Strong for local CSV support | Strong with retained comparison |
| Reset/reload | Strong if designed | Strong if designed | Variable | Strong locally, weak hosted | Strong |
| Local development simplicity | Medium | Medium | High for platform UI, low portability | Strong | Medium |
| Deployment simplicity | Medium | Medium to strong | Strong initially | Strong locally, weak hosted | Medium |
| Cost | Medium | Medium | Variable, often paid | Low | Medium |
| Security/privacy fit | Strong if designed | Strong if designed | Variable | Limited hosted fit | Strong if designed |
| Maintainability | Strong for Python-centered team | Medium unless JS/TS ownership is clear | Variable | Strong locally, weak product fit | Strong |
| Testability and CI/CD | Strong | Strong with extra toolchain | Variable | Strong locally | Strong |
| Migration from SQLite/Datasette | Strong | Medium | Variable | No real migration | Strong |
| Preserve Python extraction investment | Strong | Medium to strong | Medium | Strong | Strong |
| Risk of rework | Medium | Medium to high | High | High for hosted MVP | Low to medium |
| Speed to hosted tester MVP | Medium | Medium to fast | Fast initially | Slow for true hosted needs | Medium with lower rework |
| Production operations fit | Strong | Strong | Variable | Weak | Strong |

## Recommended Direction

Adopt the hybrid transition approach as the preferred direction for hosted
tester MVP planning.

The preferred architecture direction is:

- Keep the existing Python ingestion and extraction pipeline as the source of
  source-derived records, raw source preservation, extraction audit records,
  fixture-backed validation, and source-traceability discipline.
- Keep SQLite and Datasette for validation, inspection, debugging, local
  exploration, export support, and comparison against hosted-app behavior during
  the transition.
- Introduce a hosted relational database boundary for the tester environment,
  with future ADRs deciding exact database choice and data model.
- Store reviewer-created state separately from source-derived canonical data,
  including review status, queue membership, assignments if applicable,
  annotations, field-level notes, source verification notes, proposed
  corrections, correction decisions, tester feedback, export packet selections,
  and audit events.
- Build a hosted reviewer application/API boundary in a future implementation
  phase only after data model, authentication/access, import/sync, export, audit
  log, and retention ADRs are complete.

This recommendation is a general architecture direction, not a vendor, cloud,
framework, hosted database product, or authentication provider selection.

## Consequences

- The existing connector, raw-source preservation, extraction, normalization,
  extraction audit, fixture-backed tests, SQLite validation dataset, Datasette
  inspection layer, and source-traceable export discipline remain preserved.
- Hosted tester MVP planning can focus next on the reviewer-created data model,
  source-derived import/sync boundary, authentication/access model, audit log,
  export generation, and tester data retention.
- The project can evaluate frontend, API, database, auth, hosting, and job
  options against a concrete hybrid direction instead of generic web-development
  preferences.
- Datasette remains useful, but continuing to extend it as the primary reviewer
  UX is not the preferred hosted tester MVP path.

## Risks

- The hybrid approach can create duplicate representations of source-derived
  records unless import/sync rules are explicit and tested.
- Hosted review state could drift from local SQLite validation output unless the
  transition-comparison workflow is defined.
- A hosted relational database and app/API boundary add operational complexity
  compared with the local proof of concept.
- Accessibility and export caution language must be validated in the future UI,
  not assumed from architecture alone.
- Authentication, audit logging, reset/reload, and retention decisions can
  affect schema and operational design, so they must be made before build work.

## Deferred Decisions

This ADR explicitly defers:

- Frontend framework.
- API framework.
- Hosted database product and schema.
- Authentication provider and role model.
- Hosting platform.
- Background job approach.
- Source-derived import/sync approach from the existing extraction pipeline.
- Export generation implementation.
- Audit log implementation.
- Tester data retention policy.
- Production monitoring, incident response, backup, and operational support
  model.

## Work Not Approved By This ADR

This ADR does not approve:

- App scaffolding.
- New dependencies.
- Hosted database schema implementation.
- Authentication implementation.
- Queue implementation.
- Annotation implementation.
- Correction workflow implementation.
- Hosted export implementation.
- Connector changes.
- Extraction behavior changes.
- Schema changes.
- Datasette-primary UX expansion.

## Follow-up ADRs and Implementation Branches Needed

Before hosted tester MVP implementation starts, complete ADRs or equivalent
governance decisions for:

- Reviewer-created data model and hosted relational persistence boundary.
- Source-derived import/sync from the existing pipeline into the hosted tester
  environment.
- Authentication, tester access, and role model.
- Audit log and tester data retention.
- Source-traceable export generation and caution language.
- Reset/reload process for the seeded corpus and reviewer-created state.
- Frontend/API/framework and hosting choices, if not covered by the data model
  and access ADRs.

Implementation branches should begin only after the relevant ADRs are accepted
and should include focused validation for source traceability, reviewer-state
separation, accessibility, security/privacy, reset/reload, auditability, and
export caution behavior.