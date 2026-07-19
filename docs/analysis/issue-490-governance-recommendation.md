# Issue #490 governance recommendation

## Advisory status and evidence boundary

**Verdict: inconclusive pending technical evidence, publisher-terms review, and
source-identity confirmation. Keep the candidate inactive.**

This is the Workstream B advisory recommendation. It is not the final Issue
#490 completion report, does not approve source activation or implementation,
and does not finalize a production precedence rule. It begins none of Issues
#482, #453, #477, or #478.

The branch and Workstream B analysis started from planning-merge base
`73183c13b46d3ad7a81083482bb56c1a79dde3be`. At consumption check time:

- Workstream A handoff: delivered but stopped at its redirect-allowlist gate.
  It reported the same verified base/HEAD SHA, a clean branch, no tracked
  changes, no implementation, and no validation. No completed A commit beyond
  the planning base was supplied.
- A redirect finding: the allowlisted all-resource ZIP returned HTTP 302 to the
  unapproved S3 object path recorded in the companion qualification report. A
  signed query was not retained or reproduced, and the S3 object was not
  accessed.
- A ignored artifacts: the handoff listed controlled GitHub, catalog, ArcGIS
  layer, and ID-only discovery artifacts under
  `data/raw/source-profiling/issue-490/`; Workstream B did not inspect, copy, or
  treat them as a validated manifest.
- Technical report: `docs/analysis/issue-490-technical-source-profile.md` was
  absent.
- Output-contract version: unavailable.
- `snapshot-manifest.json` path and hash: unavailable.
- `validation-summary.json` path, hash, and status: unavailable.
- Generated deliverable hashes and validation status: unavailable.

No validated Workstream A output was consumed or inferred. The stopped handoff
is evidence of response status and an unresolved redirect boundary only. Every
gate involving content, schema, population, equivalence, identity, coverage,
duplicates, conflict frequency, freshness behavior, or code `733` therefore
remains inconclusive.

## Decision rubric, one gate at a time

| Hard gate from the evaluation plan | Current result | Reason and required evidence |
| --- | --- | --- |
| Official publisher and represented system | **Partial / blocked** | CDSS publisher/organization and CCLD program labels are direct catalog evidence. A current record labels an organizational contact `Data steward`, and two experimental records directly link to one CalHHS Geoportal item/layer. No accessed surface names the candidate's steward or maintainer, identifies an operational system of record, chooses among at least four same-title records, or proves which record supersedes another. The originally supplied ArcGIS services remain invalid or City-of-Placentia-specific. |
| Permitted public use | **Blocked** | Current experimental publisher-catalog pages display Creative Commons Attribution; the legacy CHHS publisher page says `No License Provided`; Data.gov separately harvests generic CC-BY metadata; and the allowlisted state terms URL returns 404. The current direct label is stronger than the federal harvest but does not silently resolve the direct legacy conflict or supply a license version. Human/legal confirmation is required. |
| Reproducible bounded retrieval | **Inconclusive** | Workstream A stopped after the ZIP redirected to an unapproved S3 object. The newly linked candidate ArcGIS item/layer and downloads were not allowlisted or technically profiled. Two originally supplied ArcGIS endpoints render `Invalid URL`; the remaining inspected service is geographically limited. |
| Full-download and paginated-query equivalence | **Inconclusive** | No approved snapshot, complete query, stable row key, row fingerprint, or reconciliation output exists. |
| Measurable hashes, schema, counts, identifiers, and change behavior | **Inconclusive** | Catalog and edit timestamps were observed, but no original-byte hash, canonical-row hash, schema/domain fingerprint, row count, identifier set, or repeated retrieval exists. |
| Facility-number coverage and data quality | **Inconclusive** | Field labels alone do not establish population, uniqueness, normalization safety, duplicates, omissions, or program coverage. |
| Governed facility type codes and labels | **Blocked / unresolved** | No official domain or stable code-to-label evidence was accessed. `733` remains unexplained. |
| Provenance-preserving current/historical and conflict rules | **Options defined; approval pending** | This report defines safe candidate models and invariants, but #482 and later integration must choose field ownership after technical profiling. |
| Deterministic offline fixtures and mocks | **Inconclusive** | No Workstream A fixture, mock, schema, or test validation was delivered. |

### Adopt

**Not supportable.** Multiple hard gates are blocked or inconclusive. The
catalog's `Statewide` label and CDSS publisher label are not substitutes for
permitted-use, identity, reproducibility, equivalence, coverage, or code/domain
evidence.

### Supplement

**Not supportable yet.** A supplement decision must name exact fields and
programs whose ownership is qualified. Population, scope, conflict, and timing
evidence is missing, so the necessary field/program boundary cannot be approved.

### Reject

**Not finalized.** The originally supplied ArcGIS identity fails qualification,
the newly linked CDSS ArcGIS identity is unprofiled, and the terms/license record
is materially conflicting. Those facts could support later rejection of a
particular endpoint or catalog record. The evaluation plan, however, requires an
inconclusive verdict when validated Workstream A evidence is absent; this report
does not convert missing evidence into a permanent rejection of all CHHS/CDSS
resources.

### Inconclusive

**Applies.** Keep current governed behavior in place and hold this candidate
inactive until the exact publisher terms and source relationships are confirmed
and a validated Workstream A contract passes the hard gates.

## Current-reference and historical complaint-context rules

The following invariants apply to every candidate model:

1. A complaint report's facility identity values remain historically
   source-reported context linked to that report, retrieval, and extraction
   evidence. A later reference snapshot does not rewrite them.
2. A qualified reference value is presented as current-reference context with
   its source, snapshot/access time, and effective/source date when supplied.
   When no effective date exists, it is `effective date unknown`, not current as
   of the display time.
3. Original source values remain unchanged. Normalized comparison values require
   a documented rule and retain field-level provenance.
4. A newer null, blank, absent, malformed, or unavailable value never erases an
   accepted nonblank value. These states remain distinct.
5. Conflicting nonblank values retain both originals, sources, source/effective
   dates, and conflict status. An operator can inspect technical provenance;
   reviewer pages should show only the approved review value and a concise
   conflict cue when the conflict is material to review.
6. Existing PostgreSQL rows are persistence state. Their presence, recency, or
   agreement is not independent publisher authority.
7. If the selected resource is confirmed to use Creative Commons Attribution,
   provenance must carry the CDSS publisher, dataset title, exact catalog and
   resource identity, access/source-version dates, exact approved license
   version/link, and transformation notice. The unresolved license conflict must
   remain visible until that confirmation occurs.

## Field-level owner candidates

The table defines candidates, not approved ownership. `Statewide candidate`
means only a future version that passes authority, terms, identity, quality, and
reproducibility gates.

| Field | Model 1: statewide current-reference owner | Model 2: named-field/program supplement | Model 3: program sources retain field ownership | Model 4: candidate inactive |
| --- | --- | --- | --- | --- |
| Facility/license number | Candidate supplies current lookup identity only after stable-identity proof; complaint value remains historical | Candidate may fill a verified gap only for named programs, without changing complaint identity | Program source remains reference owner; candidate may supply a separately linked identity alias after proof | Existing governed identity remains; candidate contributes nothing |
| Facility name | Candidate owns dated current-reference name | Candidate may fill blank current-reference name for a named program when population and conflict rules pass | Program source owns current name; candidate difference is conflict evidence | No change |
| Type raw code | Candidate raw code retained as provenance only until an official domain is verified | Only a named code field for a named program may supplement; unresolved codes remain raw | Program raw code remains owner; candidate code is comparison evidence | No change; `733` unresolved |
| Type label | Candidate owns only an official descriptive label with proven code/domain relationship | Candidate may fill a missing label for named programs after code-label validation | Program label remains owner; candidate label may expose a conflict | No change; no dictionary |
| Status | Candidate may own a dated current-reference status, never historical complaint status | Candidate may supplement only programs and statuses whose semantics are documented | Program source retains status ownership; candidate is gap/conflict evidence | No change |
| Address | Candidate may own current address components with snapshot/effective-date context | Candidate may fill named address components for named programs; no composite silent overwrite | Program source owns current address; candidate difference remains visible to operators | No change |
| Geography | Candidate may own source-supplied city, ZIP, county, and regional geography separately | Only named populated fields/programs supplement; geometry-derived and source-supplied values stay distinct | Program source owns named fields; candidate geometry is separate context after approval | No change |
| Capacity | Candidate may own explicit current capacity; verified zero remains zero | Candidate may fill a missing capacity for qualified programs; null cannot erase nonnull | Program source owns capacity; conflicting nonblank candidate capacity is retained as conflict | No change |
| Licensee/operator | Candidate may own a dated current-reference value only if field meaning and population are qualified | Candidate may supplement an exact named field/program; administrator and licensee are not interchangeable | Program source owns the named attribute; candidate supplies comparison/gap evidence | No change |
| Dates | Candidate source/effective dates annotate each field; closed date does not derive status | Only exact documented date fields supplement; catalog-modified and data-effective dates never substitute for each other | Program source date semantics remain; candidate dates are separate evidence | No change |

No model may silently substitute `PROGRAM_TYPE`, `CLIENT_SERVED`, an unrelated
numeric `TYPE`, or a rendered label for the complaint-report `FACILITY TYPE`.
Any later canonical bridge is a separate contract, schema/import/backfill, and
approval decision.

## Candidate precedence and failure models

### Model 1 — statewide source owns current reference

This model is eligible only if the statewide dataset and exact access path pass
all hard gates. For the fields in the table above, the latest accepted
source/effective-dated nonblank candidate value would own current-reference
display. Complaint-report values stay historical. Duplicate facility numbers,
multiple rows, and identifier changes must be resolved through a versioned
identity relationship, never first-row selection. Conflicting nonblank values
remain visible as provenance-preserving conflicts. A disappeared row retains
the last accepted version and enters operator review; it does not become closed
or deleted. A validated explicit inactive/closed value can update current
reference status without rewriting prior complaint context. Validation failure
rejects the candidate version and preserves the previous accepted version.

**Current assessment:** unavailable because source identity, terms, stable
identity, coverage, and technical equivalence are unproved.

### Model 2 — statewide source supplements named fields or programs

This model is eligible only after Workstream A names a bounded program and field
set with adequate population and explainable conflicts. The field table lists
the only candidate attribute classes; final approval must enumerate exact source
fields and programs. Qualified program-specific owners keep all unnamed fields.
A candidate nonblank value may fill an approved gap but cannot erase, replace,
or relabel a conflicting nonblank owner value without an explicit precedence
rule. Multiple candidate rows remain quarantined or grouped until their stable
identity is resolved. Identifier changes require alias/successor evidence.
Inactive, closed, disappeared, validation-failed, and scope-change cases retain
last-accepted values with an explicit reason state; absence is not a tombstone.

**Current assessment:** possible governance shape, but no field/program can yet
be named as qualified.

### Model 3 — program-specific sources retain ownership

Program resources remain current-reference owners for their named fields. A
qualified statewide candidate could later supply only a separately proven
identity alias or documented gap coverage. Candidate nulls do nothing;
conflicting nonblank values become comparison evidence. A candidate duplicate,
identifier change, or multiple-row pattern cannot alter program identity without
human/governance approval. Candidate status, closure, disappearance, or scope
change does not override program state. Candidate validation failure leaves the
program sources and last accepted program versions unchanged. Complaint-report
values remain historical in all cases.

**Current assessment:** conservative option for later comparison, not evidence
that existing program resources are complete, current, or authoritative for
every purpose.

### Model 4 — reject or hold the candidate inactive

Current governed behavior remains unchanged. No candidate field, row, label,
identity, absence, status, or date enters persistence or display. Candidate
duplicates, identifier changes, inactive/closed values, disappearances,
validation failures, and service outages are recorded only as evaluation
results. Existing accepted source versions remain available under their current
rules; no tombstone or rollback action is created. A future reconsideration must
start with new approved evidence rather than treating PostgreSQL rows as a
substitute source.

**Current assessment:** required temporary operating posture while the overall
verdict is inconclusive.

## Shared conflict, disappearance, and rollback requirements

Any later selected model must define finite states for `accepted`, `unchanged`,
`changed`, `conflicted`, `duplicate`, `missing`, `scope_changed`,
`validation_failed`, `source_unavailable`, and `unresolved_code` without
collapsing them. It must also:

- retain the original value and field-level source, resource, retrieval,
  snapshot, and effective-date context;
- distinguish a duplicate source row from a facility with multiple valid
  licenses or time-bounded identities;
- model an identifier change as an evidenced relationship, not an overwrite;
- treat inactive and closed as explicit source values only;
- treat disappearance as unexplained until the source documents closure,
  deletion, identifier change, scope change, or another cause;
- create a tombstone only under a separately approved, evidenced rule;
- reject a partial retrieval, schema/domain drift, identifier-integrity failure,
  unexplained mass disappearance, or unresolved critical type code before
  activation;
- retain the entire previous accepted version and its manifest on failure; and
- support rollback by selecting a previously accepted immutable version, never
  by reconstructing state from current PostgreSQL rows.

## Freshness and change-detection recommendation

The evidence distinguishes these signals:

| Signal | Evidence available now | Future meaning |
| --- | --- | --- |
| Catalog harvest/check | Data.gov catalog checked 2026-02-26 | Aggregator observation only; not content change |
| Dataset/catalog modification | CHHS and Data.gov show 2025-11-06 | Metadata or package change; not proof of row change |
| Experimental catalog modification | Three records show page last updated 2026-07-18 | Catalog migration or metadata signal; their listed resources retain different May/November 2025 and March/June 2026 dates |
| Resource metadata modification | Seven CSV pages show 2025-05-27; ZIP shows 2025-11-06 | Resource metadata signal; must not substitute for byte or row comparison |
| Experimental ArcGIS resource dates | Same-title records show 2026-03-31, 2026-06-24, and 2026-06-25 resource dates | Distinguishes catalog resources but does not prove schema, row, or value change or which record supersedes another |
| ArcGIS metadata/data edit | Placentia layer shows June 2023 edit dates | Applies only to that city service unless a source relationship is proven |
| Original-byte hash | Unavailable | Detect exact retrieved-byte change for a stable artifact |
| Canonical-row hash | Unavailable | Distinguish format/order volatility from normalized content change |
| Schema/domain fingerprint | Unavailable | Detect field, type, alias, domain, and capability drift |
| Record count and facility-ID set | Unavailable | Detect additions, omissions, duplicates, or identifier changes |
| Field-level row change | Unavailable | Detect named current-reference value changes with provenance |
| Accepted content change | Unavailable | May be declared only after complete retrieval and validation pass |

No refresh observation cadence can be recommended from the current evidence.
`Frequency: Other`, catalog timestamps, resource dates, duplicate catalog
records, and the unrelated Placentia edit date do not measure update behavior or
published access limits. The ZIP redirect also prevents treating the catalog
download as a validated stable retrieval contract. Workstream A must identify
the selected record/resource and compare at least two controlled retrievals
before #478 considers a cadence range.

Any future observation process must validate before activation, use bounded
timeouts/retries and published limits, distinguish outage/partial retrieval from
accepted content change, retain the previous accepted version on failure, and
route unexplained disappearance, duplicate identity, schema/domain drift, or
unresolved type codes to operator review. This report does not implement #477
or #478.

## Facility type and code `733`

`733` remains unresolved. Neither the legacy nor experimental catalog pages nor
the CalHHS handbook supplies an official code/domain table. The valid Placentia
layer exposes a nullable string `Facility_Type` field and no coded domain or
`733` mapping; the other originally supplied ArcGIS service/layer URLs are
invalid. The newly linked `CDSS_CCL_Facilities` layer was not allowlisted or
accessed. Workstream A supplied no raw-code inventory, cross-record
relationship, cross-source comparison, or cross-version evidence.

No renderer dictionary, STRTP inference, canonical mapping, backfill rule, or
reviewer-facing label is recommended. A future gate requires an official field
domain or code list that maps the exact source field and raw value to one stable,
unique descriptive label, plus technical evidence that the relationship is
consistent across relevant records and source versions.

## Workstream A conclusions still required

The following remain explicitly inconclusive until a validated A handoff is
consumed by exact commit, contract version, manifest path/hash, and validation
status:

- stable catalog/download/item/service/layer/query relationships;
- exact relationships and supersession rules among the legacy resource record,
  at least three accessed experimental records, the unaccessed fourth same-title
  record, ArcGIS item `db31b0884a074cff9260facb3f2ade45`, and the linked
  `CDSS_CCL_Facilities` layer;
- source response status, redirects, content types, byte sizes, and hashes;
- full-download stability and complete pagination behavior;
- query/full-download multiset equivalence and deterministic ordering;
- field schema, types, domains, geometry, source/effective dates, and drift;
- raw/parsed row counts, identifier population, uniqueness, duplicates,
  multiple rows, rejected rows, and identifier changes;
- statewide/program-specific coverage, omissions, and scope explanations;
- attribute population, blanks, invalid values, conflicts, and normalization
  warnings;
- inactive/closed status representation and disappearance behavior;
- facility type raw codes, labels, STRTP coverage, and `733` status;
- repeated-retrieval byte, canonical-row, schema, identifier-set, and field-level
  changes;
- safe timeout, pagination, retry, and rate-limit behavior; and
- deterministic fixture/mock and output-contract validation.

## Follow-up mapping without implementation

| Issue | Evidence and decisions it may later consume | Dependency still requiring approval |
| --- | --- | --- |
| #482 | Verified source identity; current-reference versus historical rules; field-owner candidates; null/conflict/duplicate/identifier-change/disappearance behavior; code-label status | Exact field precedence, canonical projection, schema/import/backfill, read model, and reviewer display |
| #453 | Source/version and population baselines; raw codes and labels; unresolved-code and conflict counts; regression fixtures | Coverage job, thresholds, database reads, and source-to-screen enforcement |
| #477 | Source/version, hash/schema/count/identifier signals; validation, conflict, unresolved-code, and last-accepted-version states | Operator route, permissions, persistence, monitoring, retry, and evidence UI |
| #478 | Measured access/change behavior; justified cadence; validation-before-activation; idempotence inputs; previous-version retention; disappearance and tombstone rules | Scheduler, locks, checkpoints, notification, import, rollback execution, and QNAP procedure |

Later approval would also be required for any source connector, downloader,
schema, migration, canonical allocation, import, backfill, read-model mapping,
reviewer UI, operator UI, scheduler, retention automation, or production source
activation. None is authorized by this recommendation.

## Unresolved decisions and readiness

Required before a governance decision:

1. Publisher/steward confirmation of the catalog-to-operational-system and
   catalog-to-ArcGIS relationships, including the exact owner and maintainer.
2. Human/legal confirmation of applicable CHHS/CDSS terms, exact license and
   version, attribution, automated access, caching, preservation,
   redistribution, derivative output, and commercial-use conditions.
3. Separate endpoint approval for the material terms/license page, fourth
   same-title catalog record, Geoportal/item/layer, download, data dictionary,
   datastore, ArcGIS JSON/query, and item metadata links listed in the companion
   qualification report. Workstream B does not request or access the S3 object.
4. A complete validated Workstream A evidence handoff that resolves the redirect
   gate without retaining signed parameters and identifies the exact accepted
   resource contract.
5. Later integration reconciliation of existing inventory language and a human
   approval of the combined verdict.
6. Later #482 selection of a field-level precedence model if the candidate is
   qualified.

The two Workstream B documents are ready for **conditional governance review**
of their evidence boundaries and proposed rules. The source candidate is **not
ready for adoption, supplementation, implementation, or activation**.
