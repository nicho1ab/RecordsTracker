# Governance Inventory

## Current state

- Active phase: production-discovery with local hosted scaffold implementation
  now started under ADR-0012.
- Current implementation state: the Python, SQLite, and Datasette proof of
  concept has proven governed ingestion, deterministic extraction, raw source
  preservation, source traceability, local validation and review support, and
  source-traceable exports. The hosted tester work currently consists of a
  local Python standard-library scaffold, health and smoke validation, local
  setup checks, and a read-only `/source-records` list/detail shell with local
  sample filtering/search and fixture/sample-only source traceability summary
  panels over fixture/sample records, plus a read-only `/facilities` list/detail
  sample view backed by committed tiny public-source facility fixtures and
  manifest placeholder metadata. Facility detail pages now include fixture-only
  source coverage indicators and related fixture/sample source-record context
  where the local sample mapping exists.
- Local-only sample filtering/search: implemented for the hosted source-record
  shell using in-memory fixture/sample records only.
- Fixture/sample-only source traceability summary panels: implemented for the
  hosted source-record list/detail shell using in-memory fixture/sample records
  only.
- Recent hosted sequence: PR #106 added the local hosted scaffold foundation,
  PR #107 added local setup checks, PR #108 added the first local-only read-only
  source-record view shell, and PR #109 added local-only semantic/accessibility
  validation for that shell.
- Primary UX direction: future primary reviewer UX belongs in a hosted reviewer
  application/API boundary, separate from Datasette, with source-derived records
  kept separate from reviewer-created state. The current scaffold is an
  implementation path toward that direction, not a final production framework or
  functioning reviewer workflow.
- Local-only scaffold status: the scaffold is sample-only, read-only, local to a
  development workstation, and not backed by live public data, ignored raw CSVs,
  generated profiling outputs, SQLite, a hosted database, import/sync,
  authentication, authorization, reviewer-created state, queues, annotations,
  corrections, exports, audit trail, reset/reload, deployment, QNAP, Azure,
  AWS, or public URL behavior.
- Datasette role: Datasette remains retained for validation, inspection,
  debugging, local exploration, export support, and transition comparison. It is
  not the governed primary future reviewer UX.
- Public-source expansion status: `PUBLIC_SOURCE_DATA_INVENTORY.md` inventories
  future public-source candidates, uploaded CSV example planning, conceptual
  source adapter metadata, attorney focus-area planning, and gated feedback or
  GitHub intake planning without approving imports, connectors, schemas, hosted
  behavior, issue automation, role-based UI, multi-state support, or legal
  conclusions.

## Completed ADR decisions

- ADR-0001 accepted Python, SQLite, and Datasette for the initial proof of
  concept; ADR-0005 supersedes it only for the primary future reviewer UX.
- ADR-0002-local-review-experience accepted Datasette and SQLite local review
  improvements for the proof of concept and retained local review aid workflows;
  ADR-0005 supersedes it only for the primary future reviewer UX.
- ADR-0002-raw-source-storage accepted ordinary file storage for preserved raw
  source files and source traceability.
- ADR-0003 accepted avoiding optional paid platform dependencies in the baseline
  workflow.
- ADR-0004 accepted accessibility as a release gate.
- ADR-0005 accepted the Datasette exit governance transition and retained
  Datasette as a validation, inspection, debugging, local exploration, and
  export-support layer.
- ADR-0006 accepted the hosted tester MVP architecture boundary and the
  source-derived versus reviewer-created state separation.
- ADR-0007 accepted a hybrid hosted direction: keep the Python pipeline and
  SQLite/Datasette validation layer while planning a hosted relational reviewer
  state store and hosted reviewer application/API boundary.
- ADR-0008 accepted the conceptual data and review-state model boundary.
- ADR-0009 accepted controlled imports from validated pipeline output and
  rejected hosted live crawling or hosted connector execution for the tester MVP
  unless a later ADR approves them.
- ADR-0010 accepted the future schema and migration separation strategy without
  creating schemas or migrations.
- ADR-0011 accepted authenticated, role-scoped tester access boundaries without
  choosing or implementing an authentication provider.
- ADR-0012 accepted scaffold-first hosted tester MVP sequencing. Later local
  implementation PRs used that approval only for the local scaffold, setup
  checks, read-only sample source-record shell, and semantic/accessibility
  validation.
- ADR-0013 accepted hosted tester MVP operational boundaries for audit logging,
  export generation, reset/reload, and tester data retention, clearing the next
  product-moving implementation path without implementing schemas, APIs,
  imports, exports, audit persistence, reset commands, retention automation, or
  deployment.

## Remaining deferred decisions

- Concrete frontend framework, API framework, database product, migration tool,
  authentication provider, hosting platform, deployment pipeline, retention
  durations and automation, backup/restore policy, final design system, and
  production operations model.
- Controlled import artifact format, import command or API implementation,
  import validation, idempotency, reset/reload behavior, and comparison against
  retained SQLite/Datasette validation output.
- Physical hosted schemas and migrations for import metadata, source-derived
  imported records, reviewer-created state, audit events, export packet state,
  tester feedback, and operational/reset metadata.
- Authentication, authorization, role storage, invitation flow, account
  lifecycle, access revocation, audit schema, and user deprovisioning
  implementation.
- Audit persistence implementation, export builder implementation,
  reset/reload command or API implementation, tester feedback persistence,
  reviewer-created state persistence, annotations, corrections, queues, and
  review-state workflows.
- QNAP, Azure, AWS, cloud deployment, public URL behavior, hosted live crawling,
  hosted connector execution, production monitoring, incident response, and
  operational support.

## Stale guidance assessment

- Datasette-primary assumptions are stale when they imply Datasette should be
  extended as the primary future reviewer UX. Datasette remains valid only for
  retained validation, inspection, debugging, local exploration, export support,
  and transition comparison.
- POC-only language remains accurate when it describes historical proof-of-
  concept decisions, but current planning should describe production-discovery
  and the local hosted scaffold implementation state.
- Older ADR statements saying app scaffold work was not approved were accurate
  when written. They are now superseded only by ADR-0012 and the later local
  scaffold implementation PRs. They do not approve schemas, authentication,
  authorization, imports, queues, annotations, corrections, exports, reset/
  reload, hosted deployment, hosted live crawling, hosted connector execution,
  source-derived canonical field changes, reviewer-created state persistence, or
  extraction behavior changes.
- Roadmap items for the first hosted scaffold, local setup checks, local-only
  read-only source-record shell, semantic/accessibility validation, and
  local-only sample filtering/search, and fixture/sample-only source
  traceability summary panels, local CSV profiling, tiny public-source facility
  fixtures, the first fixture-backed facility master sample view, and the
  fixture-only facility source coverage panel are complete. ADR-0013 has also
  completed the operational boundary decision for audit, export, reset/reload,
  and retention planning. Next work should move to the approved product-moving
  implementation path, not repeat those completed items.
- Local-only/sample-only boundaries remain active. Sample records must stay
  clearly marked as fixture/sample records and must not be presented as live,
  database-backed, complete, statewide, official, or production data.
- QNAP, Azure, AWS, public URL, cloud deployment, hosted connector execution,
  and hosted live crawling remain deferred.

## Gap analysis

- Future fixture-backed source view expansion: additional source-record fields,
  list/detail states, empty states, navigation states, filter facets, or
  traceability summary states should be backed by representative fixtures and
  semantic/accessibility validation before any live or database-backed source is
  introduced.
- Future import path into hosted view: source-derived hosted records should come
  from a controlled snapshot import from validated pipeline output. ADR-0013
  now defines reset/reload and audit expectations at the operational boundary;
  implementation still needs import artifact format, validation, stable
  identities, idempotency, schema/API behavior, and comparison details.
- Future database/schema implementation: no schema changes are approved by the
  current scaffold. Future schema work must preserve separate physical areas or
  table groups for source-derived imported records, reviewer-created state,
  import metadata, audit events, export packet state, tester feedback, and
  operational/reset metadata.
- Future auth/access implementation: hosted tester access must be authenticated,
  explicitly invited or provisioned, role-scoped, revocable, and auditable where
  feasible before tester workflows expose reviewer-created state.
- Future deployment/hosting decision: QNAP, Azure, AWS, public URL, cloud
  deployment, DNS, app registration, cloud database, and deployment credential
  choices remain deferred and must not be implied by local scaffold tooling.
- Future audit, reviewer-state, correction, export, feedback, and reset/reload
  workflows: ADR-0013 defines the operational boundaries for audit, export,
  reset/reload, and retention. Implementations must still preserve them as
  reviewer-created state and operational layers that do not overwrite
  source-derived canonical records, raw source files, source document metadata,
  extraction audit rows, source URLs, raw hashes, connector metadata, retrieval
  timestamps, or original extracted values.
- Future public-source expansion: structured CSV/open-data files, HTML portal
  pages, PDFs, metadata/catalog pages, and future multi-state sources need
  source inventory entries, local profiling, terms and sensitivity review,
  source metadata, traceability requirements, fixture plans, parser warnings,
  and caution language before connector, import, schema, or hosted-view work.
- Future attorney focus profiles and feedback intake: focus profiles may guide
  queues, filters, dashboards, and issue spotting only after implementation
  decisions define the relevant layer. Feedback or bug reports may integrate
  with GitHub only after triage, classification, privacy/secrets review,
  duplicate check, priority/severity assignment, human approval, and traceable
  issue linkage are defined.

## Safeguards preserved

- Source traceability and raw source preservation remain mandatory.
- Deterministic extraction and fixture-backed regression expectations remain in
  force.
- Accessibility, security, privacy, and cautious public-source language remain
  release gates.
- The system must not make unsupported legal, facility-wide, public-source
  completeness, delay, harm, abuse, neglect, liability, or rights-deprivation
  conclusions.
- Source-derived records remain separate from reviewer-created state.
- Sample data must stay clearly marked as sample-only.