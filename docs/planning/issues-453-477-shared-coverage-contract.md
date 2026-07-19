# Issues #453 and #477 shared coverage contract

## Status and authority

Contract version: `1.0.0`.

This document is the implementation-neutral contract between the Issue #453
source-to-screen coverage producer and the read-only first phase of the Issue
#477 operator dashboard. It defines data meaning, safe serialization, consumer
behavior, and validation. It does not implement either issue.

The contract takes effect only after the planning change containing it merges to
`main`. Implementations must cite the exact planning merge SHA and this contract
version. The parallel ownership and dispatch rules are in
[Issues #453 and #477 parallel ownership](issues-453-477-parallel-ownership.md).

## Decision boundary inherited from Issue #490

This contract preserves the final Issue #490 verdict:

> **inconclusive; retain existing program-specific sources and keep the statewide candidate inactive**

Accordingly, this contract does not approve, select, activate, or imply:

- a statewide facility source;
- a statewide source-of-record or completeness claim;
- a source-precedence change;
- a refresh cadence or schedule;
- a facility-type mapping for raw value `733`;
- a connector, import, backfill, database, migration, job-action, deployment, or
  QNAP change.

The existing seven program-specific sources may be identified as the retained
current source family for the evaluated scope. Every statewide candidate must
remain `inactive_candidate` unless a later governed decision changes that state.
Catalog timestamps are metadata, not proof of content freshness. A cadence field
must remain absent or explicitly `not_approved` until separately approved.

## Package boundary

One contract package consists of the following deterministic artifacts:

| Artifact | Requirement | Information tier |
| --- | --- | --- |
| `manifest.json` | Required | Safe package identity, versions, hashes, availability, and provenance only |
| `coverage-report.json` | Required | Aggregate-only coverage, operational totals, reconciliation, and release assessment |
| `operator-facility-index.jsonl` | Optional by availability, required for facility drill-down | Authorized operator-only safe facility metadata |
| `operator-job-index.jsonl` | Optional by availability, required for job drill-down | Authorized operator-only safe job metadata |
| `aggregate-coverage.csv` | Optional generated export | Aggregate-only rows; never Facility IDs |

`coverage-report.json` is the source of all dashboard summary counts. The
dashboard must not recount facility rows to replace or silently correct the
producer's aggregate logic. The two JSONL indexes support authorized filtering,
sorting, pagination, and explicit Facility ID lists; they are not reviewer
artifacts and are not general-purpose data exports.

An unavailable optional index is represented in `manifest.json` with an explicit
availability state and reason category. Its absence is never interpreted as an
empty index or verified zero.

## Version and compatibility rules

`contract_version` uses semantic versioning:

- A major version changes required fields, meanings, invariants, canonical enum
  values, identity rules, or privacy boundaries. Consumers must reject an
  unsupported major version as `version_mismatch`.
- A minor version may add optional fields, optional enum-independent metadata,
  or a new optional artifact. A consumer may ignore unknown optional fields
  only after validating all required fields and invariants for its supported
  major version.
- A patch version clarifies serialization or corrects a compatible defect
  without changing meaning.

Every artifact repeats `contract_version` and `report_id`. All values must match
the manifest. A consumer must fail closed when a required artifact has a missing
version, an unsupported major version, a mismatched report identity, a hash
failure, an unknown value in a closed enum, or a failed reconciliation
invariant. It must render `Coverage report unavailable` or `Coverage report
version is not supported`; it must not show stale values as current or turn the
failure into zero.

The v1 consumer compatibility range is `>=1.0.0,<2.0.0`. A later minor version
must declare `minimum_consumer_version` in the manifest. The consumer must reject
the package when its own supported version is below that minimum.

## Canonical serialization and deterministic identity

JSON uses UTF-8, LF line endings, sorted object keys, no byte-order mark, and no
non-finite numbers. JSONL uses one canonical JSON object per LF-terminated line.
CSV uses UTF-8, LF line endings, RFC 4180 quoting, and the exact documented
header order. All arrays are sorted by the stable ordering defined below unless
the field is explicitly documented as order-insensitive and canonicalized before
serialization.

The deterministic identity inputs are:

1. `contract_major`;
2. `evaluation_id`;
3. ordered `source_snapshot_ids`;
4. `criteria_set_id`;
5. `scope_id`;
6. `producer_schema_id`.

The producer serializes those six named values as canonical JSON, computes a
lowercase SHA-256 digest, and emits:

```text
coverage-report-v1-<64 lowercase hexadecimal characters>
```

as `report_id`. `generated_at` is excluded from identity. Re-running the same
evaluation inputs therefore produces the same `report_id`; it may record a new
generation timestamp and payload hash, but it may not silently change counts or
classifications. Different results for the same identity are a deterministic-
output failure.

`generated_at` is required and uses UTC RFC 3339 form with `Z`, for example
`2026-07-20T01:02:03Z`. Local times and timestamps without an offset are invalid.

`evaluation_id`, `criteria_set_id`, `scope_id`, `producer_schema_id`, source
snapshot IDs, field IDs, job IDs, and facility-entry IDs are stable identifiers,
not display labels. They use lowercase ASCII letters, digits, dots, colons,
underscores, and hyphens only.

## Manifest contract

`manifest.json` contains:

| Field | Type | Rule |
| --- | --- | --- |
| `contract_version` | string | Exact package contract version |
| `minimum_consumer_version` | string | Lowest compatible consumer |
| `report_id` | string | Deterministic identity above |
| `generated_at` | UTC timestamp | Generation time, not freshness proof |
| `evaluation_id` | string | Stable identity of evaluated inputs and observation boundary |
| `criteria_set_id` | string | Stable baseline and threshold rule set |
| `scope_id` | string | Safe, non-secret evaluation scope identity |
| `producer_schema_id` | string | Versioned report schema identity |
| `producer_version` | string | Safe application/build version; no path or host value |
| `source_snapshots` | array | Safe snapshot identities and selection states |
| `artifacts` | array | Relative artifact name, availability, byte count, SHA-256, and media type |
| `provenance` | object | Input manifest identities, governed fixture IDs, and generation mode |
| `retention` | object | Policy/disposition fields defined below |

Each source snapshot entry contains only:

- `source_snapshot_id`;
- `source_family_id`;
- `selection_state`;
- `safe_version_label` when available;
- `observed_at` in UTC when measured;
- aggregate `row_count` when measured;
- safe schema/content fingerprints when retained;
- `availability` and a governed reason category;
- `cadence_status`, which is `not_approved` for the Issue #490 statewide
  candidate.

`selection_state` is one of:

- `retained_existing`;
- `active_accepted`;
- `inactive_candidate`;
- `superseded_retained`;
- `unavailable`.

This vocabulary reports a governed state; it does not let the producer approve
a source. Under the current decision, the existing program family is
`retained_existing` and every evaluated statewide candidate is
`inactive_candidate`.

## Aggregate-only privacy boundary

The aggregate report may contain stable identifiers, finite categories,
aggregate counts, percentages derived from those counts, UTC timestamps, safe
source/version metadata, schema/content fingerprints, and repository-relative
evidence identifiers. It must not contain a source record value.

The entire package, including operator indexes, prohibits:

- complaint, allegation, finding, deficiency, plan-of-correction, or other
  source narrative text;
- raw source bodies, raw HTML, rendered page bodies, or uncontrolled excerpts;
- names, addresses, telephone numbers, email addresses, or other unnecessary
  person/facility attributes;
- secrets, credentials, tokens, cookies, private headers, connection strings,
  authentication claims, provider subjects, or provider issuers;
- private or hosted runtime URLs;
- absolute or host-specific paths, raw paths, share names, or local usernames;
- container, service, database-host, or QNAP names;
- stack traces, SQL text, exception representations, or uncontrolled error
  messages;
- claims of source authority, statewide completeness, legal conclusions,
  currentness, freshness, or approved cadence.

The only row-level identifier allowed in `operator-facility-index.jsonl` is the
public Facility ID plus its contract-derived opaque facility-entry ID. That
operator index remains behind existing operator authorization. Aggregate output
and aggregate CSV never include Facility IDs.

## Source-to-screen coverage dimensions

The producer reports both field-level and pipeline-stage coverage. Every field
uses the stable `field_id` from the governed source-to-screen inventory.

The closed pipeline-stage vocabulary is:

1. `source_presence`;
2. `extraction`;
3. `normalization`;
4. `canonical_allocation`;
5. `postgresql_population`;
6. `read_model_exposure`;
7. `complaint_page_rendering`;
8. `facility_hub_rendering`.

Each field/stage row contains `field_id`, `stage`, `eligible_count`, and these
mutually exclusive counts:

- `successful_count`;
- `blank_count`;
- `absent_count`;
- `unavailable_count`;
- `unsupported_count`;
- `conflict_count`;
- `failure_count`;
- `skipped_count`.

For every row:

```text
eligible_count = successful_count + blank_count + absent_count
               + unavailable_count + unsupported_count + conflict_count
               + failure_count + skipped_count
```

No stage is assumed from a later stage. For example, PostgreSQL population does
not prove correct rendering, and a rendered label does not prove correct source
extraction.

## Coverage classification vocabulary

The approved terminal coverage classifications are:

- `present_and_populated`;
- `present_but_not_extracted`;
- `extracted_but_not_allocated`;
- `allocated_but_not_imported`;
- `stored_but_not_read`;
- `read_but_not_rendered`;
- `rendered_incorrectly`;
- `present_blank`;
- `source_label_absent`;
- `source_artifact_unavailable`;
- `unsupported_layout`;
- `conflicting_sources`;
- `intentionally_internal`;
- `not_applicable`.

Issue #453's phrases map without changing meaning as follows:

| Issue phrase | Canonical classification |
| --- | --- |
| `source_absent` | `source_label_absent` |
| `source_unavailable` | `source_artifact_unavailable` |
| `conflicting_source` | `conflicting_sources` |

All other Issue #453 failure phrases are identical to the canonical values. The
producer must not collapse these categories into a generic missing or failed
state.

### Missing and exceptional semantics

- **Blank**: the governed label/key is present in an available supported source
  artifact but its value is empty or whitespace. Blank is not absent, zero,
  unavailable, or successful.
- **Absent**: the governed label/key is not present in an available supported
  artifact where the inventory defines it as eligible. Absence is not proof that
  an event or fact did not exist.
- **Unavailable**: the required artifact, database, stage, contract, or evidence
  could not be inspected. Unavailable has no numeric value and is never zero.
- **Unsupported**: the artifact exists, but its layout or schema is outside the
  governed deterministic parser/contract.
- **Conflict**: approved sources or stages contain differing nonblank evidence
  without a governed resolution. A conflict is not silently resolved by order.
- **Warning**: processing completed sufficiently to retain a result, but one or
  more governed review conditions require attention.
- **Failure**: the governed operation or coverage check did not complete or did
  not meet a required invariant. It exposes only a controlled category.
- **Skipped**: an explicit governed rule chose not to process an eligible item;
  the reason category is required.
- **Not applicable**: the field or stage is outside the governed record type or
  surface requirement. It is not missing.
- **Intentionally internal**: the field exists for identity, traceability, or
  implementation but is deliberately excluded from reviewer presentation. It is
  not a display failure and does not authorize operator disclosure of its value.

## Operational status and outcome vocabulary

Operational state is independent of source-to-screen coverage.

### Refresh state

Every existing facility has exactly one `refresh_state`:

- `not_started`;
- `eligible`;
- `in_progress`;
- `completed`;
- `completed_with_warnings`;
- `failed`;
- `unavailable`.

`eligible` means the governed eligibility checks passed but no attempt is active
or complete for the evaluation. `completed` and `completed_with_warnings`
require a recorded attempt and validation outcome; neither proves statewide
coverage or source freshness. `unavailable` means refresh state could not be
evaluated and is never treated as `not_started` or zero.

### Processing outcome

Every eligible facility has exactly one `processing_outcome`:

- `successful`;
- `skipped`;
- `warning`;
- `failed`;
- `not_yet_processed`.

`not_yet_processed` means no governed attempt is recorded for the evaluation;
it does not mean the facility has no records or no source artifact.

### Change outcome

Every eligible facility has exactly one `change_outcome`:

- `changed`;
- `unchanged`;
- `not_evaluated`.

Changed and unchanged compare validated content under the named criteria set.
Catalog timestamps alone cannot set either value. `not_evaluated` is required
when no valid comparable accepted snapshot exists.

### Retrieval, import, artifact, and hash state

Closed vocabularies are:

- `retrieval_state`: `not_attempted`, `successful`, `warning`, `failed`,
  `unavailable`;
- `import_state`: `not_attempted`, `successful`, `skipped`, `failed`,
  `unavailable`;
- `preserved_artifact_state`: `preserved`, `missing`, `unavailable`,
  `not_applicable`;
- `hash_validation_state`: `valid`, `failed`, `not_checked`, `unavailable`,
  `not_applicable`;
- `refresh_eligibility`: `eligible`, `ineligible`, `unknown`;
- `retry_eligibility`: `eligible`, `ineligible`, `not_evaluated`.

`preserved` means the governed artifact identity exists and retention validation
passed; it does not expose the artifact or path. `hash_validation_state=valid`
means the preserved bytes matched the retained governed fingerprint.
`not_checked` is not valid. A failed hash does not activate or replace a source.

### Checkpoint and job state

`checkpoint_state` is one of `not_started`, `available`, `complete`,
`interrupted`, `failed`, or `unavailable`.

`job_state` is one of `queued`, `active`, `completed`, `interrupted`, or
`failed`. Historical jobs may also carry `superseded` only after a later
compatible minor contract explicitly adds it; v1 consumers otherwise reject the
unknown value.

`execution_mode` is `dry_run` or `apply`. It describes how an already-recorded
job was configured; it is not an action instruction.

### Governed operational failure categories

The closed v1 category set is:

- `none`;
- `retrieval_failed`;
- `import_failed`;
- `validation_failed`;
- `missing_artifact`;
- `hash_validation_failed`;
- `unsupported_layout`;
- `conflicting_sources`;
- `checkpoint_interrupted`;
- `contract_unavailable`;
- `contract_version_mismatch`;
- `controlled_unknown_failure`.

`controlled_unknown_failure` replaces an uncontrolled exception with a safe
category. The package must never serialize the exception text.

## Explicit coverage-versus-operations distinction

Source-to-screen coverage answers whether governed fields move correctly from
source evidence through extraction, normalization, allocation, PostgreSQL, read
models, and required reviewer surfaces.

Operational refresh status answers whether retrieval, preserved-artifact
validation, import, checkpoint, and job processing ran and what controlled
outcome was recorded.

Neither dimension proves the other. Implementations must preserve examples such
as:

- operational `successful` with `read_but_not_rendered` coverage;
- operational `failed` while the previous accepted source-to-screen report
  remains available;
- coverage `source_artifact_unavailable` with no operational attempt;
- operational `unchanged` without a statewide completeness or freshness claim.

The dashboard presents these as separately labeled regions and filters. It must
not derive a coverage classification from operational state or vice versa.

## Aggregate totals and reconciliation invariants

`coverage-report.json` includes these required totals:

- `existing_facility_total`;
- `preserved_artifact_facility_total`;
- `eligible_facility_total`;
- `ineligible_facility_total`;
- `unknown_eligibility_total`;
- `refresh_state_counts`;
- `processing_outcome_counts`;
- `change_outcome_counts`;
- `preserved_artifact_state_counts`;
- `hash_validation_state_counts`;
- `governed_conflict_facility_total`;
- `operator_intervention_required_total`;
- `job_state_counts`;
- field/stage counts and `terminal_classification_counts`.

All counts are nonnegative integers. Percentages, when emitted, are decimal
numbers derived from named numerator and denominator counts and never replace
the counts.

Required invariants are:

```text
eligible_facility_total + ineligible_facility_total
  + unknown_eligibility_total = existing_facility_total

sum(processing_outcome_counts) = existing_facility_total

sum(refresh_state_counts) = existing_facility_total

sum(change_outcome_counts) = existing_facility_total

sum(preserved_artifact_state_counts) = existing_facility_total

sum(hash_validation_state_counts) = existing_facility_total

preserved_artifact_facility_total
  = preserved_artifact_state_counts.preserved

governed_conflict_facility_total = count of facilities with governed_conflict true

when the operator facility index is available, its governed_conflict true count
  = governed_conflict_facility_total

each field/stage eligible_count = the eight mutually exclusive stage counts
```

The report also carries `reconciliation_status` as `passed` or `failed` plus a
finite list of invariant IDs. A failed invariant makes the contract unavailable
to the dashboard. The consumer must not repair counts.

## Baselines, thresholds, and release assessment

The producer identifies a versioned `criteria_set_id` and emits each applied
baseline and threshold as safe metadata. Thresholds must be explicit,
deterministic, reviewable, and based only on the active accepted or retained
source scope. No statewide baseline may be invented.

`release_assessment` is one of `passed`, `warning`, `failed`, or
`reviewed_exception_required`. At minimum, the criteria set must fail or require
an explicit reviewed exception when:

- a previously populated governed field becomes blank without an approved
  explanation;
- a verified descriptive facility-type label regresses to an unresolved raw
  code;
- an expected facility count declines beyond its named threshold;
- any required reconciliation invariant fails;
- a required source-to-screen stage regresses.

Raw value `733` remains unresolved and must be a regression fixture that proves
the producer does not label it `STRTP` or another facility type without new
governed evidence.

## Authorized operator facility metadata

Each `operator-facility-index.jsonl` row contains only:

- `contract_version` and `report_id`;
- `facility_entry_id`, computed as `facility-v1-` plus the SHA-256 of canonical
  `source_family_id` and normalized Facility ID;
- public `facility_id` as a string;
- `source_snapshot_id`;
- `refresh_eligibility`;
- `preserved_source_document_count`;
- `last_retrieval_attempt_at`, `last_successful_retrieval_at`,
  `last_refresh_attempt_at`, and `last_successful_refresh_at` in UTC or null;
- safe `pipeline_version`;
- `preserved_artifact_state`;
- `hash_validation_state`;
- `source_layout_classification` from a finite governed enum;
- `processing_outcome` and `change_outcome`;
- `refresh_state`;
- `governed_conflict` boolean;
- `operational_failure_category`;
- `retry_eligibility`;
- `operator_intervention_required` boolean;
- `checkpoint_state`;
- safe `last_job_id` or null.

Facility name, address, licensee, administrator, telephone, complaint counts,
source values, narratives, source URLs, raw hashes, raw paths, and uncontrolled
messages are not permitted in this index. The public Facility ID is permitted
only for authorized operators and explicit Facility ID list downloads.

## Authorized operator job metadata

Each `operator-job-index.jsonl` row contains only:

- stable safe `job_id`;
- `contract_version` and `report_id`;
- `job_state` and `execution_mode`;
- `started_at`, `completed_at`, and `last_successful_refresh_at` in UTC or null;
- safe pipeline/extractor version;
- `checkpoint_state` and safe checkpoint identity;
- aggregate selected, processed, changed, unchanged, skipped, warning, and
  failed counts;
- `operational_failure_category`;
- whether the previous accepted dataset remained active;
- `operator_intervention_required`.

No command, SQL, path, source body, exception, host, container, authentication
claim, or mutable action URL is allowed.

## Deterministic ordering, filtering, and pagination

The default facility ordering tuple is:

```text
(normalized facility_id ascending, facility_entry_id ascending)
```

Allowed alternate primary sort keys are `processing_outcome`, `change_outcome`,
`refresh_state`, `refresh_eligibility`, `hash_validation_state`,
`source_layout_classification`, `operational_failure_category`,
`operator_intervention_required`, `last_retrieval_attempt_at`, and
`last_refresh_attempt_at`.
Every alternate ordering appends normalized Facility ID and facility-entry ID as
ascending tie-breakers. Null timestamps sort last in both directions.

Allowed filters are the closed enum values above, exact Facility ID, operator-
intervention boolean, governed-conflict boolean, and UTC timestamp bounds.
Free-text search is limited to normalized Facility ID. No narrative or
uncontrolled field is searchable.
Changing a filter or sort returns to the first page.

Pagination uses seek/keyset cursors over the complete visible ordering tuple.
The default page size is 25 and the maximum is 100. Cursors bind `report_id`,
filter fingerprint, sort tuple, direction, and the last row's complete ordering
tuple. They are opaque to users and rejected when the report, filters, or sort
changes.

Deep `OFFSET`, progressive `OFFSET`, scan-and-discard equivalents, arbitrary
page-number jumps, and full-corpus application-memory slicing are prohibited.
This is the contract's explicit no deep OFFSET requirement.
Tiny deterministic fixtures may be loaded in memory for tests only; that test
adapter is not a production pagination implementation.

Adjacent pages must reconcile without duplicate or omitted facility-entry IDs.
Displayed result-position text uses `Showing X–Y of Z facilities` and preserves
active filters and sort.

## Unavailable and version-mismatch behavior

Package availability is one of `available`, `partial`, `unavailable`,
`version_mismatch`, `hash_failed`, or `reconciliation_failed`.

- `partial` may show only validated dimensions and must name unavailable
  dimensions. Missing totals are unavailable, not zero.
- `unavailable` shows no current counts and a controlled recovery statement.
- `version_mismatch`, `hash_failed`, and `reconciliation_failed` fail closed and
  show no package data.
- A previously accepted report may be shown only when separately validated and
  labeled `Previous accepted report`, with its generation time and the current
  failure state. It must not be labeled current.
- Fixture fallback is allowed only in explicit local/test fixture mode and must
  be visibly labeled. Production-style runtime must never silently substitute a
  fixture.

## CSV and explicit Facility ID list boundaries

Aggregate CSV may contain only report identity, dimension/category identifiers,
numerator/denominator counts, derived percentages, status, and safe source/
criteria metadata. It must not contain Facility IDs or operator-index rows.

An explicit Facility ID list download:

- requires existing operator authorization;
- requires exactly one selected group from `changed`, `unchanged`, `warning`,
  `failed`, `missing_artifact`, or `retry_eligible`;
- is bounded to the active report and active authorized scope;
- contains the exact headers `report_id`, `group`, `facility_id` in that order;
- sorts by normalized Facility ID, then original Facility ID;
- contains no facility names, record values, narratives, URLs, paths, hashes,
  errors, credentials, or authentication data;
- is never exposed through reviewer routes or reviewer navigation.

An export with no explicit group, multiple groups, an unsupported group, a
failed contract, or an unauthorized actor is rejected. A zero-row authorized
list retains the header and is labeled verified empty only when the relevant
aggregate count is zero and reconciliation passed.

## Dry-run and apply separation

The read-only Issue #477 phase implements no job action. `execution_mode`,
`retry_eligibility`, and checkpoint state are descriptive fields only.

Any later action phase must preserve these boundaries:

- dry-run performs no database, source-derived, reviewer-created, job, artifact,
  or checkpoint mutation;
- apply is a separate request and permission boundary, requires an explicit
  bounded Facility ID selection and separate confirmation, and cannot be inferred
  from a prior dry-run;
- retry is limited to explicitly selected eligible failures;
- cancel affects only future/unstarted work and cannot corrupt completed work;
- resume uses a validated checkpoint and never reclassifies prior work silently.

Those actions require a later separately approved phase, owned paths,
authorization decision, data model, tests, cleanup/state disposition, and
evidence. This contract does not authorize them.

## Reviewer and operator authorization boundary

The aggregate package and operator indexes are operator diagnostics, not
attorney/reviewer content. The read-only dashboard must reuse the existing
`audit_read` permission and existing role/scope enforcement. It must not add or
change roles, permissions, authentication middleware, provider configuration,
claims, sessions, cookies, or authorization targets in the parallel phase.

Admin and `developer_operator` actors with `audit_read` and matching scope may
consume the dashboard contract. Reviewer and read-only tester roles must be
denied even if they have source-derived read permission. No operator route,
summary, drill-down, CSV, or Facility ID list may appear in reviewer navigation,
reviewer HTML, reviewer exports, or reviewer APIs.

## Fixture and production-style validation

Both workstreams implement the same named contract scenarios independently in
their exclusive fixture directories:

1. `complete-balanced`;
2. `empty-verified`;
3. `partial-unavailable-stage`;
4. `failed-reconciliation`;
5. `version-mismatch`;
6. `hash-validation-failure`;
7. `interrupted-job-previous-accepted-active`;
8. `raw-733-unresolved`;
9. `pagination-adjacent-pages`;
10. `prohibited-content-rejected`.

Workstream A proves its producer emits the contract and invariants. Workstream B
proves its narrow adapter consumes the fixtures without importing or duplicating
producer counting/classification logic. Integration compares the two fixture
sets and schema before connecting the producer output.

Validation must include:

- JSON Schema or equivalent closed-enum validation;
- deterministic identity, ordering, canonical serialization, and repeat-run
  equality excluding allowed generation metadata;
- redaction and rejection of narratives, raw HTML, URLs, paths, secrets,
  credentials, claims, container names, and uncontrolled errors;
- every coverage and operational state;
- aggregate and adjacent-page reconciliation;
- blank/absent/unavailable/unsupported/conflict distinctions;
- contract unavailable, partial, hash-failed, reconciliation-failed, and
  version-mismatch behavior;
- authorization denial for every reviewer/tester role without `audit_read`;
- aggregate CSV and exact Facility ID list boundaries;
- no writes during report generation, adapter reads, dashboard GETs, exports,
  filtering, sorting, or pagination;
- responsive, keyboard, focus, non-color-only status, 200% zoom, print, and
  long-content evidence for the operator route;
- production-style local evidence using validated fixtures and a fresh local
  server, with no live source call, remote database, deployment, or QNAP access.

Fixture evidence is labeled fixture evidence and is never described as current
production or statewide coverage.

## Retention and provenance

Every package is immutable by `report_id` and generation instance. It records:

- producer version and schema ID;
- exact criteria-set ID;
- evaluation and scope IDs;
- source snapshot identities and selection states;
- governed input manifest and fixture identities;
- artifact byte counts and SHA-256 values;
- generation mode and UTC generation time;
- reconciliation and validation results;
- previous accepted report identity when applicable.

Artifacts use repository-relative logical names only. They never include an
absolute storage path. A new generation must not overwrite evidence needed to
reproduce or explain a prior accepted report.

The required `retention` object contains:

- `policy_id`, nullable until a later policy is approved;
- `disposition`: `retained`, `superseded_retained`, `expired`, or
  `pending_policy`;
- `retain_until`, UTC timestamp or null;
- `previous_accepted_report_id`, string or null.

Until a retention policy is separately approved, `policy_id` is null,
`disposition` is `pending_policy`, and no automated destructive cleanup is
authorized. This unresolved duration does not invalidate an otherwise valid
read-only report, but the dashboard must not claim that retention automation is
configured.

## Producer and consumer obligations

Issue #453 owns calculation, classification, reconciliation, schema validation,
safe serialization, and deterministic package generation. It must not implement
operator routes, authorization changes, UI, downloads, or job actions.

Issue #477 owns contract validation at the adapter boundary, existing operator
authorization, presentation, safe filtering/sorting/keyset pagination, downloads,
accessibility, and unavailable/mismatch states. It must not recalculate coverage,
change classifications, query raw source bodies, mutate data, or implement job
actions in the first phase.

Any ambiguity that would require either workstream to guess another enum,
invariant, field meaning, source approval, cadence, authorization rule, or shared
file is an integration blocker. The workstream stops and reports it instead of
extending this contract unilaterally.

## Integration resolution

The integration branch resolved the independent fixture differences through the
stable `ccld_complaints.source_to_screen_coverage` read boundary. The dashboard
imports that boundary and does not import the producer implementation directly.
The boundary delegates schema, canonical serialization, hashes, deterministic
identity, reconciliation, and closed-enum validation to the producer's public
validator, then exposes only validated manifest, report, facility index, job
index, and aggregate CSV values.

For real producer packages, `source_layout_classification` is exactly
`supported`, `unsupported`, `unavailable`, or `not_applicable`; no business
label is inferred. JSON uses `application/json`, JSONL uses
`application/x-ndjson`, and CSV uses `text/csv`. The aggregate CSV header and
`checkpoint_identity` job field remain producer-owned. The older Issue #477
scenario shape is available only behind explicit fixture mode and its legacy
producer-schema marker. It is not a production compatibility contract.
