# ADR-0018: Retain Complaint-Report Address and City as Audit-Only Evidence

## Status

Accepted

## Context

Complaint investigation reports can contain `ADDRESS` and `CITY` observations in
their facility-details section. The governed fixtures currently demonstrate
present-but-blank observations only. Extraction audit already retains the source
document linkage, field identity, semantic blank state, permitted source section
or text evidence, extraction confidence, and warnings for those observations.

Current facility-reference address and city are a different, current-reference
concern. Treating complaint-time observations as current-reference facts would
lose temporal meaning and could silently change facility identity.

No approved reviewer or analyst requirement currently needs historical
address/city display or comparison. The governed evidence also does not establish
whether a report can have one authoritative observation, repeated observations,
conflicting observations, or revised observations over time.

## Decision

Option C applies now: retain complaint-report `ADDRESS` and `CITY` as
source-document-linked extraction-audit evidence only. No normalized complaint
field, canonical facility field, or historical observation entity is created at
this time.

The observations retain their governed missing-state semantics. In particular,
populated, blank, absent, unavailable, unsupported, and extraction-failed states
remain distinct where the audit can establish them. Present blank is not an
absent label, an unavailable source, or a failed extraction.

Complaint-time address and city do not participate in current-reference
address/city selection. They must never overwrite, supplement, or silently
replace current-reference facility identity, and they remain unrendered as
canonical historical values. They may be represented truthfully as governed
missing-state evidence where appropriate.

## Rejected alternatives

### Option A: Complaint-owned columns

Rejected for now because the current evidence is blank-only, no reviewer use is
approved, and it would commit to one-value-per-report semantics before the
source proves that model. It would also add schema, migration, local/hosted
import, replay, and testing work without current reviewer value.

### Option B: Source-document-linked historical observation entity

Rejected for now because, although it is the stronger future model for
multiplicity, current evidence does not demonstrate repeated, conflicting, or
revised observations. It would add disproportionate schema, provenance-key,
SQLite/PostgreSQL parity, replay, and testing complexity before it is justified.

Option C is the approved present contract, not a permanent prohibition.

## Future implementation triggers

A future implementation decision requires all applicable conditions:

- At least one governed fixture has a populated complaint-report address or city.
- Extraction distinguishes populated, blank, absent, unavailable, unsupported,
  and failed states.
- An approved reviewer or analyst requirement needs display or comparison.
- Fixture-backed evidence establishes observation cardinality.
- Report-time or observation-time semantics are defined.
- Import identity is deterministic.
- Null-preserving and blank-protection behavior is specified.
- Conflicts are retained.
- Preserved-artifact replay is covered.
- SQLite and hosted PostgreSQL behavior is equivalent.
- The source-to-screen status and presentation contract is defined.
- Privacy and retention review approves any new canonical storage.

If future evidence proves one authoritative observation per complaint report,
complaint-owned fields remain plausible. If it demonstrates repeated,
conflicting, or revised observations, a source-document-linked historical
observation entity becomes preferable.

## Consequences

Issue #450 can truthfully represent governed source and missing states without
historical canonical address/city storage. It neither creates nor implies
historical address/city values, and this decision does not require reopening or
modifying its implementation.

Deferral avoids duplicating historical location observations beyond existing
retained source and audit evidence. It changes no public-source retention
obligation. Any future canonical storage requires a new privacy and retention
review.

## Non-goals

This decision does not add complaint or facility columns, observation tables,
migrations, import mappings, replay behavior, read-model fields, reviewer UI,
exports, API fields, extraction changes, or current-reference selection rules.
