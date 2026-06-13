# Production-Discovery Requirements

## Purpose

This document defines the minimum product requirements that must exist before a
hosted online tester version of the primary reviewer application is built.

The project has crossed the Datasette exit threshold for the primary future
reviewer experience. Datasette remains retained for validation, inspection,
debugging, local exploration, and export support, but hosted reviewer work must
start from these requirements and later architecture ADRs rather than from more
Datasette-primary UX.

This document does not choose a production stack, add dependencies, alter
schemas, change extraction behavior, add connectors, or define new
source-derived canonical fields.

## Non-negotiable boundaries

- The public portal remains the source of record.
- Raw source files must remain preserved before extraction.
- Source-derived canonical data remains governed by `DATA_CONTRACT.md` and the
  JSON schemas.
- Reviewer-created state must stay separate from source-derived canonical data.
- Review state, annotations, correction proposals, queue position, tester
  feedback, and export inclusion decisions are application/reviewer state, not
  new source-derived facts.
- Future schema changes for persisted reviewer state require an ADR plus the
  normal schema, documentation, migration/init SQL, and test update path.
- Deterministic extraction and fixture-backed regression expectations remain in
  force.
- Accessibility, security, privacy, and cautious public-source language remain
  release gates.
- The system must not make unsupported legal, facility-wide, delay, harm, abuse,
  neglect, liability, or rights-deprivation conclusions.

## Minimum hosted reviewer workflows

A hosted tester version must support these workflows before it can be considered
ready for external tester use.

### Facility search and selection

Reviewers must be able to search or filter facilities by available
source-derived identifiers and names, select a facility, see source coverage at a
high level, and navigate into that facility's complaint review queue without
manual table joins.

### Complaint review queue

Reviewers must be able to see a guided queue of complaint records for the
selected facility or review scope. The queue must expose review state, source
traceability status, correction needs, annotation presence, export inclusion
state, and cautious review flags without treating flags as conclusions.

### Complaint detail review

Reviewers must be able to inspect one complaint with its source-derived fields,
related allegations, events, extraction audit context when available, known
missing values, and review-state history. The detail view must keep original
extracted values visible when corrections are proposed.

### Source verification

Reviewers must be able to verify each complaint against source URL, raw SHA-256
hash, retrieval timestamp, connector name and version, raw path when available,
report index or document type when available, and extraction audit rows when
field-level source text exists.

### Annotation

Reviewers must be able to add reviewer notes that are clearly marked as
annotations, attributed to a reviewer, timestamped, and connected to the
relevant facility, complaint, field, source document, or export packet context.
Annotations must not change raw source records or canonical extracted values.

### Proposed correction

Reviewers must be able to propose corrections to extracted values without
overwriting the original value. Each proposal must preserve the original value,
proposed value, source basis, reviewer, timestamp, decision status, and source
traceability to the relevant source document and extraction audit when
available.

### Facility pattern review

Reviewers must be able to review source-traceable facility-level patterns over
the derived dataset, including finding mix, allegation categories, date
missingness, review flags, source document coverage, and correction/annotation
counts. Pattern review must be framed as screening and comparison over extracted
public records, not facility-wide conclusions.

### Export packet preparation

Reviewers must be able to prepare source-traceable export packets from reviewed
records, explicitly include or exclude records from export, see unresolved
corrections or caution flags, and preserve clear headers, limitations, source
URLs, raw hashes, connector details, retrieval timestamps, and correction or
annotation context needed for review handoff.

### Tester feedback

Testers must be able to submit feedback tied to the workflow step, facility,
complaint, source document, export packet, or accessibility issue being tested.
Feedback must distinguish product usability feedback from proposed corrections
to source-derived data.

## Review-state requirements

Review state is reviewer/application state. It must not be stored as or treated
as source-derived canonical data unless a future schema ADR explicitly approves
the persistence model.

Minimum review states:

- `unreviewed`: no reviewer has started the record in the hosted workflow.
- `in review`: a reviewer has started review and has not completed source
  checking or disposition.
- `source checked`: a reviewer has checked available source traceability for the
  record.
- `needs correction`: a reviewer has identified a likely extraction issue or
  missing value that needs a correction proposal or review.
- `correction proposed`: at least one correction proposal exists and is awaiting
  a decision.
- `reviewed`: the reviewer has completed the current review pass without open
  correction decisions blocking use.
- `included in export`: the record is selected for a specific export packet.
- `excluded from export`: the record is intentionally left out of a specific
  export packet.

State requirements:

- State changes must be attributed to a reviewer and timestamp.
- State history must be auditable; a later state must not erase earlier review
  history.
- Export inclusion and exclusion must be scoped to an export packet or review
  context, not treated as a permanent fact about the source record.
- A record may have source-derived fields that are unchanged while review state
  changes many times.
- Queue filters may use review state, but exported source-derived fields must
  remain traceable to their source documents.

## Annotation and correction boundaries

Annotations and correction proposals are reviewer-created state.

- Annotations do not change raw source records.
- Annotations do not change canonical extracted fields.
- Proposed corrections do not overwrite original extracted values.
- Every correction proposal must preserve the original value, proposed value,
  source basis, reviewer, timestamp, and decision status.
- Correction workflows must remain traceable to source documents and extraction
  audit rows where available.
- Correction decision statuses must distinguish at least pending, accepted,
  rejected, and superseded decisions before any correction can influence an
  export packet.
- Accepted corrections may affect a reviewed export presentation only through an
  explicit, traceable correction layer; they must not mutate raw files or erase
  original extracted values.
- Rejected and superseded corrections must remain auditable.
- Review notes must not assert legal, facility-wide, delay, harm, abuse,
  neglect, liability, or rights-deprivation conclusions without an approved and
  documented basis outside this derived dataset.

## Hosted tester readiness requirements

A hosted tester version is not ready until it satisfies these minimum
requirements.

### Authenticated tester access

Access must be limited to authenticated testers using an approved access model.
The repository must not store secrets, tokens, private URLs, or account-specific
configuration in committed files.

### Seeded test corpus

The tester environment must use a seeded, documented test corpus with source
traceability. The corpus must be suitable for repeatable testing and must not be
presented as complete statewide coverage or official facility conclusions.

### Known limitations visible

Known limitations must be visible in the hosted workflow at points where testers
review records, interpret flags, prepare exports, or submit feedback.

### Accessibility expectations

The hosted workflow must meet the project accessibility requirements for
keyboard access, logical focus order, visible focus indicators, semantic
structure, screen-reader support, contrast, non-color-only status, plain
language, and accessible exports.

### Source-traceability expectations

Source URL, raw hash, connector details, retrieval timestamp, report context,
and extraction audit context where available must remain accessible from review,
correction, annotation, queue, and export workflows.

### Export restrictions and cautions

Exports must be limited to reviewed, intentionally included records for the
selected packet. Export output must preserve source traceability, original values
when corrected values are shown, correction status, relevant annotations, known
limitations, and cautious public-source language.

### Feedback collection

Tester feedback must be collected with workflow context, tester identity or
approved tester identifier, timestamp, severity or priority, and enough source
context to reproduce the issue without exposing secrets or unnecessary personal
information.

### Reset and reload process

The hosted tester environment must have a documented process for resetting
reviewer-created state and reloading the seeded corpus so repeated tests can
start from a known baseline.

## Architecture decision prerequisites

Before hosted tester MVP implementation starts, ADRs must define:

- The boundary between source-derived storage and reviewer-created state.
- Where review state, annotations, correction proposals, feedback, and export
  packet decisions are persisted.
- How source traceability and extraction audit context remain available to the
  hosted reviewer application.
- How authenticated tester access, audit history, reset/reload, and export
  restrictions are handled without storing secrets in the repository.
- Which accessibility checks are required before tester access is enabled.
- Which production stack, if any, is selected after these requirements are
  reviewed.