# ADR-0012: Define Hosted Tester MVP Scope and Scaffold Sequencing

## Status

Accepted

## Context

The project is in production-discovery for a source-traceable public-record
review solution. The proof of concept has proven ingestion, deterministic
extraction, raw source preservation, source traceability, local review, and
source-traceable exports.

Datasette is retained for validation, inspection, debugging, local exploration,
export support, and transition comparison. It is no longer the governed primary
future reviewer UX. The future primary reviewer UX is a hosted reviewer
application that supports authenticated tester workflows, guided review, source
verification, reviewer-created state, annotations, proposed corrections, export
packet preparation, tester feedback, and accessible review paths.

ADR-0007 recommends a hybrid transition architecture: preserve the existing
Python ingestion and extraction pipeline, retain SQLite and Datasette for local
validation and comparison, and plan a hosted relational reviewer-state boundary
with a hosted reviewer application/API.

ADR-0008 separates source-derived records from reviewer-created state.
Source-derived records preserve public-source-derived values, raw source
traceability, extraction audit context, and data-contract discipline.
Reviewer-created state includes review statuses, annotations, proposed
corrections, correction decisions, tester feedback, export packet decisions,
and audit events.

ADR-0009 defines controlled snapshot imports from validated pipeline output.
The hosted tester MVP must not directly run connector discovery, live fetch, or
crawling workflows unless a later ADR explicitly approves that behavior.

ADR-0010 defines schema and migration boundaries. Future hosted schema work
must keep import metadata, source-derived records, reviewer-created state,
audit events, export packet state, tester feedback, and operational/reset
metadata physically separated or clearly grouped.

ADR-0011 defines authentication and access boundaries. Hosted tester access
must be authenticated, explicitly invited or provisioned, role-scoped,
auditable where feasible, and revocable. Anonymous hosted tester access is not
allowed.

The next decision is implementation sequencing, not more broad architecture
discovery. Prior ADRs have established enough boundaries to begin implementation
after this PR, provided implementation remains sequenced, scaffold-first,
small, and validated at each layer.

## Decision

Hosted tester MVP implementation may begin after this ADR, but only through a
sequenced scaffold-first path.

The first implementation branch must create the hosted application scaffold
only. It may establish project structure, minimal shells, tests, local run
instructions, and smoke validation. It must not implement business workflows,
domain schema, authentication, authorization, import/sync, review queues,
annotations, corrections, exports, reset/reload, hosted deployment, or
extraction changes unless a later scaffold task explicitly approves a narrow
placeholder with no workflow behavior.

Implementation after the first scaffold must proceed in small PRs. Each PR must
state which accepted ADR boundary it implements, what remains deferred, what it
does not approve, and which focused validation matches the changed layer.

This ADR approves the sequence and criteria for beginning implementation next.
It does not approve implementation in this PR.

## Minimum Hosted Tester MVP Implementation Sequence

The intended implementation sequence is:

1. Hosted scaffold foundation.
2. Development and runtime tooling.
3. Configuration and secrets pattern.
4. Empty or placeholder app shell.
5. Health check or smoke route, or an equivalent smoke validation path.
6. CI validation for scaffold.
7. Database and migration tooling setup after provider/tooling decision if
   still deferred.
8. Initial schema implementation.
9. Controlled import/load path from validated pipeline output.
10. Facility search and read-only source-derived view.
11. Complaint and source document detail view.
12. Authentication and access implementation.
13. Review-state implementation.
14. Annotations.
15. Proposed corrections.
16. Export packet preparation.
17. Audit trail.
18. Tester feedback.
19. Reset/reload workflow.

This sequence is a planning boundary, not a mandate that every item be one PR
or that every item be implemented in a single stack decision. Later work may
split, combine, or reorder small PRs when a PR explains why the change remains
inside accepted ADR boundaries and does not weaken source traceability,
reviewer-state separation, accessibility, security/privacy, cautious
public-source language, or fixture-backed validation.

The sequence intentionally starts with scaffold and validation plumbing before
domain behavior. The hosted app should become runnable and testable before it
stores or changes source-derived records, reviewer-created state, authentication
state, or export state.

## First Scaffold Branch Boundaries

The first scaffold implementation branch may include:

- Project structure for the hosted app.
- Minimal app shell.
- Minimal API shell if applicable.
- Health or smoke endpoint, page, command, or equivalent validation path.
- Test harness for the scaffold.
- Local development instructions.
- CI hooks if needed for scaffold validation.
- Placeholder navigation only if no workflow behavior is implemented.
- Documentation for how to run the scaffold.

The first scaffold implementation branch must not include:

- Real authentication.
- Authorization.
- Production schema.
- Migrations with domain tables.
- Import/sync implementation.
- Real queues.
- Annotations.
- Corrections.
- Exports.
- Reset/reload.
- Hosted live crawling.
- Hosted connector execution.
- Production deployment.
- Source-derived canonical field changes.
- Reviewer-created state stored inside source-derived canonical records.

Scaffold placeholders must be clearly labeled as placeholders in code,
documentation, tests, or UI copy where applicable. Placeholders must not imply
that seeded data, authentication, review workflows, exports, or deployment are
available before their implementation PRs are approved and validated.

## Tester-Visible MVP Definition

The first point where testers can see something useful is a controlled hosted
reviewer experience with:

- Authenticated or controlled-access app shell.
- Seeded or imported source-derived test corpus.
- Facility search.
- Complaint and source document read-only detail.
- Visible source traceability.
- Known limitations and cautious public-source language.
- Basic feedback path.

Review-state workflows can come after the first visible read-only tester view.
The first useful tester milestone should prioritize safe source-derived reading,
source traceability, cautious language, accessibility, and feedback over
editable reviewer-created workflows.

The tester-visible MVP must not present the seeded corpus as complete statewide
coverage, official public-source truth, a legal conclusion, a facility-wide
conclusion, verified delay, harm, abuse, neglect, liability, or rights
deprivation.

## Design and UX Timing

Detailed visual design work should begin after the scaffold and first read-only
source-derived views exist. Early scaffold work should favor accessibility,
semantic structure, clear labels, testability, and stable navigation hooks over
polished visual design.

When the project enters hosted reviewer UX/design implementation, the
document-governance dashboard concept may be used as inspiration for:

- Left navigation.
- Dashboard and status cards.
- Review queues.
- Source-traceability health panels.
- Contextual onboarding and help.
- Light and dark mode support.
- Audit and change-history patterns.

The design should not copy that concept literally. It should adapt only the
useful interaction ideas to this project's review workflows, source
traceability, cautious public-source language, accessibility requirements,
tester feedback needs, and reviewer-state boundaries.

## Validation Expectations for Implementation Branches

Future implementation PRs must include focused validation based on the changed
layer:

- Scaffold PR: scaffold tests, lint, smoke route or equivalent smoke check, and
  docs.
- Schema PR: migration tests, rollback or recovery guidance, and docs.
- Import PR: import validation, idempotency or duplicate handling, and
  traceability checks.
- Auth PR: access-control tests and security checks.
- Read-only UI PR: accessibility checks and source-traceability display checks.
- Review-state PR: reviewer-state preservation and audit tests.
- Correction PR: original value preservation and correction-boundary tests.
- Export PR: source traceability, caution language, and source/reviewer-state
  separation checks.

Every implementation PR must also run standard PR validation unless the task is
analysis-only and edits no files. Focused validation is required because hosted
implementation will touch different safeguards at different layers.

## Remaining Deferred Decisions

The following decisions remain deferred after this ADR:

- Concrete frontend framework.
- Concrete API framework.
- Database product.
- Migration tool.
- Auth provider.
- Hosting platform.
- Deployment pipeline.
- Production retention policy.
- Backup/restore policy.
- Final design system.
- Full production operations model.

These decisions may be made in small ADRs, implementation planning PRs, or
implementation PRs when enough context exists. A scaffold PR may choose minimal
tooling only at the level explicitly approved by its task and must explain why
the choice does not create an unreviewed production commitment.

## Consequences

Benefits:

- Hosted implementation can begin without reopening broad architecture
  discovery.
- The first implementation step is constrained to a runnable, testable scaffold
  rather than business workflow behavior.
- Source-derived data, reviewer-created state, authentication, schema, import,
  export, audit, feedback, and reset/reload behavior remain protected by
  accepted ADR boundaries and layer-specific validation.
- Design work can start from real read-only source-derived views rather than
  abstract mockups alone.

Tradeoffs and risks:

- A scaffold-first path may feel slower than building visible workflows
  immediately.
- Deferred vendor and framework choices still need to be made deliberately.
- Scaffold placeholders could be mistaken for product behavior unless they are
  clearly labeled and tested as placeholders.
- Later implementation PRs must avoid expanding scope beyond the layer they are
  validating.

## Work Not Approved By This ADR

No schema changes are approved by this ADR.

This ADR does not approve implementation of:

- Scaffold code.
- Authentication.
- Authorization.
- Schema.
- Migrations.
- Import/sync.
- Queues.
- Annotations.
- Corrections.
- Exports.
- Reset/reload.
- Hosted deployment.
- Extraction changes.

This ADR only approves the sequence and criteria for beginning implementation
next.