# ADR-0009: Define Hosted Tester MVP Import and Sync Strategy

## Status

Accepted

## Context

The existing Python pipeline discovers, fetches, preserves, extracts, and
normalizes public CCLD source records. It preserves raw public source files
before extraction, stores source document metadata and raw SHA-256 hashes,
emits extraction audit context, validates normalized records, and writes a
source-derived SQLite dataset for local validation and review support.

SQLite and Datasette remain useful for validation, inspection, debugging, local
exploration, export support, and transition comparison. ADR-0005 retained
Datasette for those support roles after the primary future reviewer experience
moved into production-discovery.

ADR-0007 recommends a hybrid transition: preserve the Python ingestion and
extraction pipeline and retained SQLite/Datasette validation layer while
planning a hosted relational reviewer-state store and hosted reviewer
application/API boundary. ADR-0008 separates source-derived imported records
from reviewer-created state, including review status, annotations, proposed
corrections, tester feedback, export packet decisions, and audit events.

The hosted tester MVP now needs a controlled way to populate hosted
source-derived records without weakening source traceability, raw source
preservation, deterministic extraction expectations, local validation, or
cautious public-source language. The import/sync boundary must avoid creating
drift between the validated source-derived pipeline output and hosted review
records, while also keeping reviewer-created state separate from imported
source-derived values.

Current note: ADR-0012 later approved scaffold-first sequencing, and later local
implementation PRs added only the local scaffold, setup checks, read-only sample
source-record shell, and semantic/accessibility validation. This ADR still does
not approve import/sync implementation, hosted live crawling, hosted connector
execution, reset/reload implementation, or production data population.

## Decision

The hosted tester MVP will treat the existing Python ingestion and extraction
pipeline as the source-derived data producer.

Hosted source-derived records will be populated through controlled imports from
validated pipeline output. For the tester MVP, the preferred starting approach
is a scripted or operator-initiated snapshot import from a validated SQLite
database or export artifact produced by the existing pipeline. Incremental
import may be added later only within the same source-derived/reviewer-created
boundary and after the physical schema, artifact format, validation, reset, and
audit details are approved.

Reviewer-created state remains in the hosted reviewer domain. Review statuses,
annotations, proposed corrections, correction decisions, tester feedback,
export packet membership, and audit events must not be written back into the
source-derived canonical records or treated as public-source facts.

Imports should be idempotent where possible. Re-importing the same
source-derived record should update or confirm the hosted source-derived
snapshot for the same stable identity, not create duplicate review items, unless
a later ADR explicitly approves a versioned duplicate-review strategy.

Imports must preserve stable source-derived identifiers or deterministic
identity keys, source URLs, raw hashes, connector metadata, retrieval
timestamps, raw source links where available, report context where available,
extraction audit context, original extracted values, extraction confidence, and
warnings where available.

The hosted tester MVP will not directly run connector discovery, live fetch, or
crawling workflows. Direct hosted live crawling, hosted connector execution, or
automatic source expansion is not approved unless a later ADR explicitly
approves it.

## Options Considered

Each option was compared against source traceability, drift risk, reset/reload
simplicity, tester safety, reproducibility, auditability, implementation
complexity, local validation compatibility, long-term maintainability, and the
risk of accidentally weakening public-source caution language.

| Option | Evaluation |
|---|---|
| Snapshot import from validated SQLite/export output | Strong source traceability when the artifact is generated after local validation. Low drift risk for a seeded tester corpus because each import batch has a clear source artifact. Simple reset/reload behavior and strong reproducibility. Good tester safety because operators can inspect the local output before import. Strong auditability if batch metadata and counts are recorded. Lowest implementation complexity for the hosted tester MVP. Fully compatible with local SQLite/Datasette validation and transition comparison. Maintainable as an initial bridge, though not enough by itself for long-term frequent updates. Low risk of weakening public-source caution language because the import starts from validated derived data and can carry existing limitations. |
| Incremental import from pipeline-generated source-derived records | Strong traceability if stable identities, extraction audit links, raw hashes, and batch metadata are preserved. Lower reload cost than full snapshots and better long-term maintainability for repeated updates. Higher drift risk because partial updates can leave hosted source-derived records out of sync with local validation output if batch boundaries are unclear. Tester safety, reproducibility, and auditability depend on explicit duplicate, deletion, supersession, value-change, and retry rules. Implementation complexity is higher than snapshot import. Compatible with local validation only if comparison tooling and import manifests are defined. Medium caution-language risk unless each partial batch carries limitations and source context consistently. |
| Hosted app directly reads from SQLite/Datasette | Strong local traceability and validation compatibility, but weak fit for hosted tester state, authentication, reset/reload, and audit boundaries. Drift risk appears low at first because the hosted app reads the same SQLite data, but it couples the primary hosted reviewer workflow to a validation layer that ADR-0005 and ADR-0006 intentionally retained as support tooling. Reset/reload is simple locally but awkward for hosted tester safety. Reproducibility is good for a local artifact but weak for a hosted tester lifecycle. Implementation complexity is low at first, but long-term maintainability is poor because Datasette should remain validation, inspection, debugging, local exploration, export support, and transition comparison rather than the primary hosted data access strategy. Caution-language risk grows if hosted UI behavior starts treating the validation layer as the product system of record. |
| Hosted app directly runs the connector/live fetch workflow | Preserves traceability only if the full connector, raw preservation, validation, and extraction audit discipline is reproduced in hosted operations. High tester-safety and drift risk because hosted review behavior could accidentally expand public fetching or crawl scope. Reset/reload is harder because live source availability and changed public records affect reproducibility. Auditability and public-source caution language become more complex. Implementation complexity and operational risk are high. Local validation compatibility is weaker unless hosted fetch output is exported back for comparison. Long-term maintainability is poor for the tester MVP because this conflicts with the controlled import boundary. |
| API-mediated import from the Python pipeline | Strong long-term direction if the API exposes validated source-derived records, import manifests, counts, validation results, traceability fields, and caution-language metadata. Good auditability and maintainability once schema, authentication, artifact format, and operational ownership are decided. Reset/reload and reproducibility can be strong if API batches are immutable and replayable, but those details are not approved yet. Too much implementation and infrastructure surface for the first tester-MVP import decision. Drift risk is manageable only after API contracts, validation implementation, retry/idempotency behavior, and local comparison rules are specified. Tester safety depends on authentication and operational controls that are deferred. |
| Manual CSV upload/import as an early tester-only bridge | Fast and easy to inspect manually, with low initial infrastructure complexity. Reproducibility, traceability, raw hash validation, extraction audit links, and duplicate handling are fragile unless the CSV format and manifest are tightly governed. Reset/reload is simple for small seeded data but easy to perform inconsistently. Auditability depends on manual records unless an import manifest is required. Local validation compatibility is limited to whatever columns the CSV preserves. Long-term maintainability is weak. Higher risk of accidental column omission, reviewer-state mixing, or weakened caution language. Useful only as a narrow tester-only fallback for a seeded corpus, not as the preferred strategy when a validated SQLite/export artifact can be imported through a scripted process. |

## Recommended Strategy

The hosted tester MVP should start with a scripted or operator-initiated
snapshot import from a validated pipeline artifact, such as the local SQLite
database or a deliberately generated source-derived export bundle. The import
should be repeatable, auditable, and documented before testers use the hosted
environment.

During the tester MVP, imports should be manual or scripted. CI/CD may validate
the pipeline and import artifact format in the future, but CI/CD should not
silently replace hosted tester data until reset/reload, retention, backup,
access, and audit behavior are approved.

Each import batch must record enough metadata to identify the source artifact,
pipeline version, validation status, record counts, raw hash validation status,
warnings, errors, and any reset/reload relationship. The hosted reviewer
application must be able to distinguish records imported by one batch from
reviewer-created state that existed before or after that import.

Duplicate imports or re-imports should be idempotent when the stable
source-derived identity matches. The import should update or confirm the hosted
source-derived snapshot for that identity and preserve an audit trail of changed
source-derived values. It should not create duplicate review items unless a
future ADR approves a deliberate versioned duplicate-review model.

Raw source preservation remains linked through source document identity, source
URL, raw SHA-256 hash, raw path or artifact reference where available,
connector metadata, retrieval timestamp, and report context where available.
The import process must not replace raw source preservation with hosted review
state.

Extraction audit context remains linked through source document identity,
field-level audit identity where available, field name, extraction method,
extractor version, extracted value, source text, source section, confidence, and
warning where available. Hosted review screens and exports may use this context,
but reviewer-created notes and corrections must remain distinguishable from
extraction audit records.

Reviewer-created state should survive normal re-imports. Review status,
annotations, proposed corrections, correction decisions, tester feedback, export
packet membership, and audit history must remain linked when stable
source-derived identity matches. Re-imports may mark source-derived values as
changed or superseded for review, but they must not silently overwrite reviewer
state.

Reset/reload should support replacing the seeded source-derived tester corpus
from a known validated artifact. It should not delete reviewer-created state,
feedback, correction history, export packet decisions, or audit events unless an
approved reset operation explicitly allows that behavior, records the action,
and testers have been told what will happen.

## Import Batch Requirements

Each import batch must record at least:

- Import batch ID.
- Import timestamp.
- Imported by or process identity where available.
- Source pipeline version or commit where available.
- Source database, export path, or artifact identity.
- Record counts by entity.
- Source document count.
- Raw hash validation status.
- Validation status.
- Warnings and errors.
- Reset/reload relationship if applicable.

## Source-Derived Record Identity

Source-derived records need stable IDs or deterministic identity keys across
imports. Hosted reviewer-created state must link to those stable
source-derived identities rather than to transient row positions, display
labels, file order, or upload order.

Re-importing the same source-derived facility, source document, complaint,
allegation, event, or extraction audit record must not create duplicate review
items unless a future ADR explicitly approves a duplicate or versioned review
strategy.

Changes in extracted values across imports must be detectable and auditable.
The hosted reviewer domain must be able to tell when a source-derived value came
from the original imported snapshot, a later imported snapshot, or a
reviewer-created correction proposal or decision.

Original extracted values and later imported values must remain distinguishable
when needed for source verification, correction review, export preparation, and
audit history. Later imported values must not erase the fact that reviewers saw
or annotated earlier imported values.

## Reviewer-Created State Preservation

Review statuses should not be overwritten by source-data re-import unless an
approved reset operation explicitly does so.

Annotations should remain linked to their target records when stable identity
matches. If a source-derived value changes, existing annotations must remain
auditable and must not be reinterpreted as annotations on a different record or
field without an explicit migration or review step.

Proposed corrections should remain visible and distinguishable from imported
source-derived values. Accepted, rejected, pending, and superseded correction
decisions must not become canonical source-derived facts through import.

Export packet membership should not silently change when source-derived records
are re-imported. If an imported change affects an included record, the hosted
reviewer domain should make that condition auditable for later export review.

Tester feedback should survive normal re-imports unless an approved reset
policy explicitly says otherwise. Feedback must remain distinguishable from
source-derived facts and correction proposals.

## Reset and Reload Boundary

For the tester MVP, reset/reload may replace the seeded source-derived hosted
corpus with records from a validated import artifact. It may also clear
non-production seeded data when an approved tester reset operation says that is
the intended behavior.

Reset/reload must preserve source traceability, raw source links or artifact
references, import batch history, and audit history needed to understand what
changed. It must preserve reviewer-created state by default unless the reset
operation explicitly includes a reviewed and audited reviewer-state reset.

Reset/reload events must be audited with who or what initiated the operation
where available, when it happened, which import batch or artifact was used, what
record counts changed, whether raw hash and validation checks passed, and what
reviewer-created state was preserved or removed.

Seeded tester source-derived data can be fully replaced only through the
documented reset/reload process. Replacement must not imply that the public
source is complete, current, statewide, official, or legally conclusive.

Accidental deletion of reviewer-created state should be prevented by default
through separate domains, explicit reset scopes, audit requirements, and clear
operator documentation before testers use the system.

Before testers use the hosted environment, the project must document what
normal re-import preserves, what reset/reload can replace, whether any tester
state may be cleared, how testers will be warned, and what audit trail remains.

## What This ADR Does Not Approve

No schema changes are approved by this ADR.

This ADR does not approve:

- Implementation of import/sync code.
- Physical hosted schema.
- Migration files.
- API endpoints.
- Authentication.
- Hosted connector execution.
- Direct live crawling from the hosted app.
- Production data retention policy.
- Reviewer-state deletion behavior.
- App scaffold.

## Deferred Decisions

This ADR explicitly defers:

- Physical schema and migration strategy.
- Database product.
- API framework.
- Frontend framework.
- Authentication provider.
- Hosting platform.
- Import artifact format.
- Import command or API implementation.
- Import validation implementation.
- Reset/reload implementation.
- Retention policy.
- Backup/restore policy.

## Consequences

The hosted tester MVP has a clear import/sync boundary that preserves the
existing Python pipeline as the source-derived producer while allowing hosted
reviewer workflows to use imported source-derived snapshots.

SQLite and Datasette remain valuable for validating, inspecting, debugging,
locally exploring, exporting, and comparing source-derived records before and
after hosted imports.

The next production-discovery decisions can focus on physical schema and
migration strategy, authentication and access, audit logging, export generation,
reset/reload implementation, retention, backup/restore, and app scaffold
sequencing without reopening whether the hosted tester MVP should crawl public
sources directly.

Future implementation work must add validation for import idempotency, stable
source-derived identity, raw hash and extraction audit preservation,
reviewer-created state preservation, reset/reload auditability, security and
privacy expectations, accessibility expectations, and cautious public-source
language at the level of the implemented change.