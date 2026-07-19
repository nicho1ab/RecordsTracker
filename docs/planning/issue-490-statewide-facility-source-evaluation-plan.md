# Issue #490 statewide facility source evaluation plan

## Status and authority

This document is the planning and coordination contract for GitHub Issue #490,
"Evaluate statewide CCLD facility dataset as governed reference source." It does
not approve a connector, downloader, import, schema, migration, production source
change, backfill, reviewer-facing change, scheduled job, deployment, or QNAP
operation.

The evaluation may begin only after the planning change containing this document
has merged. Its two bounded workstreams and later integration step are defined in
[Issue #490 parallel work ownership](issue-490-parallel-work-ownership.md). The
executable task templates are:

- [Workstream A — technical source profiling](issue-490-workstream-a-codex-prompt.md)
- [Workstream B — governance and source qualification](issue-490-workstream-b-codex-prompt.md)

## Goal

Determine, with reproducible public-source evidence, whether the newly identified
statewide ArcGIS-backed California Community Care Licensing Facilities dataset
should be adopted, used only as a supplement, or rejected as a governed facility
reference source for RecordsTracker.

The evaluation must establish what the source actually represents, how it can be
retrieved reproducibly, what records and fields it contains, how it differs from
the existing program-specific facility resources, and what downstream governance
or implementation work would be required. A catalog modification date is not
evidence that facility rows changed.

## Boundaries

### In scope

- Read-only qualification of public catalog, metadata, download, and ArcGIS REST
  endpoints on an explicit network allowlist.
- Controlled local preservation of public source snapshots and deterministic
  response representations in existing ignored raw-data locations.
- Offline profiling code, schemas for evaluation outputs, minimized or synthetic
  fixtures, mocked ArcGIS responses, and deterministic tests.
- Quantitative comparison with the existing program-specific facility sources.
- Source-authority, terms, license, attribution, precedence, conflict, freshness,
  and change-detection analysis.
- Machine-readable technical outputs and a cautious human-readable recommendation.

### Explicit non-goals

- No production source replacement or activation.
- No production import, canonical allocation, facility backfill, or mutation of
  existing SQLite or PostgreSQL data.
- No application schema or Alembic migration.
- No application, read-model, reviewer, operator-dashboard, or UI change.
- No page-local mapping or display dictionary for facility type code `733`.
- No assertion that `733` means a particular facility type until governed source
  evidence proves both the code and label relationship.
- No scheduled retrieval or refresh automation.
- No statewide complaint crawl or expansion of the existing complaint retrieval
  boundary.
- No browser/computer-use, private/authenticated source access, secrets, QNAP,
  SSH, Docker, Compose, deployment, database administration, Cloudflare, or other
  infrastructure operation.
- No completeness, legal, official-status, safety, or facility-wide conclusion.

## Dependencies and sequence

1. This planning package merges.
2. Workstream A and Workstream B begin from the same clean, synchronized planning
   merge SHA with exclusive file ownership.
3. Workstream A publishes its immutable technical evidence contract and reports
   the exact commit and generated-output manifest.
4. Workstream B may finish source qualification in parallel, but it must not
   issue an unconditional adopt/supplement/reject verdict until it has consumed
   Workstream A's identified evidence. It may publish a conditional recommendation
   with unresolved evidence gates.
5. A later integration branch combines both workstreams, resolves the current
   inventory-language conflict, updates only approved reserved files, and creates
   the final Issue #490 completion report.
6. Only after that report is accepted may follow-up issues consider source
   selection, facility identity projection, source-to-screen coverage, operator
   monitoring, or refresh automation.

Issue #490 is upstream of #482, #453, #477, and #478. It is not authorization to
begin any of them.

## Questions the evaluation must answer

### Identity, authority, and permitted use

1. What are the exact catalog, dataset, stable download, ArcGIS item, ArcGIS
   service, layer, query, and metadata URLs?
2. Which public agency publishes each surface, and which agency or system is
   represented as the system of record?
3. Are the catalog record, ArcGIS item, service, and downloadable content the
   same dataset and publisher, or are they linked aggregations with different
   ownership or update paths?
4. What terms of use, license, attribution language, access restrictions, public-
   data handling expectations, and redistribution limits apply?
5. Does the source claim authority, statewide scope, currency, or completeness?
   If so, what exact source evidence supports the claim and what cautions qualify
   it?
6. What stable identifiers exist for the dataset, item, service, layer, resource,
   version, and individual facility?

### Retrieval and change behavior

7. Is there a stable full-download endpoint? Does it return deterministic content
   for the same source state?
8. What ArcGIS layer identifiers, supported query formats, pagination controls,
   object-ID behavior, ordering guarantees, maximum record counts, transfer
   limits, rate limits, timeouts, and response-format options apply?
9. Can every row be retrieved without relying on an implicit default result cap?
10. Do a full download and complete paginated service query represent the same
    facility multiset after format-only normalization?
11. Are repeated retrievals byte-identical? If not, do canonical row fingerprints
    remain identical, and which volatile fields explain byte differences?
12. Which catalog or service timestamps change when metadata changes, and which
    evidence proves actual content change?
13. What schema or service-version metadata is exposed, and which fields may
    change without notice?
14. What bounded timeout, retry, and backoff behavior is safe for later use?
15. What observed behavior supports a future refresh cadence? The evaluation
    must not infer cadence from a catalog date alone.

### Coverage and fitness

16. What are the raw and parsed row counts, column counts, encodings, geometry
    behavior, null markers, field types, date formats, and parser warnings?
17. Is facility/license number present, stable, unique where expected, normalized
    safely, and comparable with existing sources?
18. Which duplicate facility numbers, duplicate object IDs, missing identifiers,
    identifier changes, and multiple-row-per-facility patterns exist?
19. Which facility type code fields and descriptive label fields exist? Are code
    and label supplied on the same row, by a related table/domain, or only through
    metadata?
20. Does the source include Short-Term Residential Therapeutic Program facilities
    and other relevant 24-hour residential facility types? What source values
    demonstrate that coverage?
21. What does raw code `733` represent, if anything, in this dataset? Is its
    relationship to a descriptive label explicit, stable, unique, and consistent
    across records and source versions?
22. What facility status, address, city, state, ZIP, county, latitude/longitude,
    regional geography, capacity, licensee/operator, administrator, telephone,
    first-license, closed-date, and source-date fields exist?
23. For each field, what are population, blank, null, invalid, distinct-value,
    and normalization-warning counts?
24. How are active, inactive, closed, pending, or other status values represented?
    Does disappearance from a later snapshot have any documented meaning?
25. Which fields or values conflict within the statewide source, with existing
    program-specific sources, with complaint-report historical values, or with
    existing hosted facility rows?
26. Which differences are true source conflicts versus timing, scope, formatting,
    identifier, or normalization differences?
27. Would this source support current reference identity, historical complaint
    context, or both? What effective-date and source-date evidence exists?

### RecordsTracker fit

28. Can access follow `discover -> fetch -> store raw -> extract -> normalize ->
    validate -> emit` without browser-only steps or a live dependency in tests?
29. Which existing canonical fields could be populated only after a separately
    approved contract and precedence decision, and which source fields must remain
    source-reference-only?
30. What provenance must accompany any later field bridge so current reference
    attributes never silently rewrite historically source-reported complaint
    context?
31. What downstream schema, import, backfill, read-model, UI, test, operator, and
    documentation dependencies would be required later? Listing dependencies is
    not approval to implement them.

## Required source evidence register

The evaluation must record the following without secrets or private machine
paths. Every entry includes the exact public URL, UTC access time, retrieval
method, observed HTTP/content metadata, publisher attribution, evidence status,
and limitations.

| Evidence class | Required evidence |
| --- | --- |
| Catalog | Catalog URL, title, description, publisher, owner/maintainer when public, created/modified metadata, tags, scope language, and linked resources. |
| Dataset/resource | Dataset and resource identifiers, names, formats, stable and resolved download URLs, snapshot/file dates, and public metadata. |
| ArcGIS item | Item identifier, owner/publisher shown publicly, item type, description, terms/license/attribution, modified metadata, and service relationship. |
| ArcGIS service | Exact service URL, service type, capabilities, supported formats, current version metadata, limits, spatial reference, and public access behavior. |
| ArcGIS layer | Layer ID, name, fields, domains, object-ID field, display field, geometry, supported query capabilities, pagination/order behavior, maximum record count, and layer metadata. |
| Terms and authority | Terms URL/text summary, license, required attribution, restrictions, publishing agency, represented system of record, and unresolved authority questions. |
| Retrieval | Request URL and safe parameters, UTC retrieval time, status/content type, byte count, deterministic SHA-256, row count, schema fingerprint, warnings, and source-version metadata. |

Catalog metadata and dataset-content observations must be reported separately.
No field may use a catalog modification timestamp as a substitute for a content
hash, schema fingerprint, or row-level change comparison.

## Controlled snapshot and service checks

### Preservation

- Preserve the original full-download bytes, service/layer metadata responses,
  query definitions, and every paginated response needed to reconstruct the
  evaluated snapshot under the existing ignored raw source-profiling boundary.
- Record SHA-256 for every preserved evaluation artifact. This is evaluation
  evidence; it does not change the current product contract for structured
  facility CSV hashes.
- Use relative artifact references in generated manifests and public docs. Never
  expose a personal, server, container, or QNAP path.
- Never overwrite a preserved artifact. A repeated access creates a new retrieval
  manifest or proves identical content through its hash.

### Required deterministic checks

- Hash original bytes and a documented canonical row representation separately.
- Fingerprint ordered field definitions, field domains, layer capabilities, and
  output schema.
- Count raw responses, parsed rows, unique object IDs, unique facility numbers,
  missing identifiers, duplicate identifiers, and rejected rows.
- Exercise the source-reported maximum page size, a smaller page size, explicit
  object-ID batching when supported, stable ordering when supported, and the
  terminal short or empty page.
- Prove no duplicate or omitted record across page boundaries.
- Compare full download and paginated service results using a documented stable
  row key and canonical row fingerprint. Report additions, omissions, duplicates,
  and value differences; do not reduce equivalence to row count alone.
- Repeat equivalent queries with supported formats or query shapes and explain
  any result difference.
- Record observed timeouts, throttling, transient failures, retry headers, and
  safe bounded behavior without stress testing or attempting to bypass limits.
- Compare at least two controlled retrievals when available to distinguish byte,
  metadata, schema, and actual record-content changes.

## Comparison with existing program-specific sources

The comparison must use controlled snapshots or existing approved local evidence
for the current program-specific sources. It must not treat existing PostgreSQL
rows as source truth or silently overwrite either side.

At minimum, compare:

- Source family, resource identity, snapshot/access date, schema, and row count.
- Facility-number set intersection, statewide-only rows, program-only rows, and
  missing/invalid identifiers.
- Duplicate facility numbers and the row cardinality per facility.
- Facility type raw codes, descriptive labels, program types, and unresolved
  mappings.
- Status and inactive/closed representation.
- Name, address, geography, capacity, licensee/operator, and other identity-field
  population.
- Same-facility differing nonblank values, with source and time context.
- Scope differences that explain apparent omissions.
- Exact treatment of STRTP and every row or metadata relationship involving code
  `733`.

Comparisons must retain original values and publish normalized values only with
an explicit normalization rule. Blank, absent, invalid, unavailable, and
conflicting states remain distinct.

## Code 733 investigation protocol

`733` begins as an unexplained raw value, not as a label.

1. Identify every field, record, domain, code list, metadata item, and existing
   source in which `733` appears.
2. Preserve the exact field name and original surrounding record/metadata
   context in controlled evidence.
3. Determine whether an official field domain or code list maps `733` to one and
   only one descriptive label.
4. Compare that relationship across the statewide download, service query,
   program-specific sources, and more than one facility when possible.
5. Check whether the code is a facility type, program type, internal category,
   or unrelated identifier.
6. Report contradictory, missing, time-varying, or non-unique mappings as
   unresolved.
7. Do not add a renderer dictionary, canonical mapping, or reviewer-facing label
   in Issue #490.

## Fixture and mock strategy

Automated tests must never call the live catalog, download endpoint, or ArcGIS
service.

- Commit only small, documented, safe, synthetic or minimized fixtures. Do not
  commit a full statewide snapshot or generated profiling output.
- Include representative service metadata, layer metadata, one full-download
  shape, multiple paginated responses, a terminal page, code/label domains,
  duplicate identifiers, missing identifiers, null/blank values, inactive or
  closed values, schema drift, throttling/timeout responses, and conflicting
  source values.
- Mock redirect, timeout, rate-limit, malformed response, unsupported format,
  changed schema, duplicate page, missing page, and result-cap behavior.
- Verify fixture hashes from Git-normalized bytes when expected hashes are
  committed.
- Make output ordering deterministic and independent of filesystem, locale,
  response order, and platform path separators.
- Test that query equivalence fails on an omitted row, duplicate row, value
  difference, or unexplained schema mismatch even when row counts match.
- Test no-secret output, relative-path portability, redaction, schema validation,
  and repeat-run determinism.

## Connector-contract evaluation sequence

The technical evaluation must demonstrate, without activating a production
connector, that a later approved source path could satisfy
`discover -> fetch -> store raw -> extract -> normalize -> validate -> emit`:

1. `discover`: resolve the official dataset, item, service, layer, and stable
   resources from allowlisted public metadata.
2. `fetch`: perform bounded, timeout-limited, rate-aware retrieval from exact
   allowlisted endpoints.
3. `store raw`: preserve original response bytes and retrieval metadata before
   parsing.
4. `extract`: parse the structured source deterministically while retaining
   original fields.
5. `normalize`: create evaluation-only comparison values without inventing
   canonical fields or erasing originals.
6. `validate`: validate content type, schema, identifiers, counts, pagination,
   hashes, warnings, and comparison invariants.
7. `emit`: write only the approved ignored profiling artifacts and safe reports;
   do not import into application persistence.

Any stage that cannot be demonstrated must remain an explicit blocker in the
recommendation.

## Security, privacy, and public-source rules

- Public, unauthenticated source data only.
- Exact source and GitHub read allowlists must be set in each dispatched task.
- No credentials, tokens, cookies, private headers, private URLs, account data,
  or `.env` values may be read, stored, logged, tested, or documented.
- Do not include personal local paths, raw exception dumps, or server paths in
  artifacts or reports.
- Treat public facility and complaint data cautiously. Do not copy unnecessary
  narrative or person-level content into fixtures, logs, reports, or diffs.
- Reports may contain necessary public facility identifiers for controlled
  reconciliation, but aggregate or fingerprint evidence is preferred when the
  raw value is unnecessary.
- Respect terms, robots directives, documented limits, rate limits, and source
  availability. No load testing, scraping around controls, CAPTCHA bypass, or
  authenticated access is permitted.
- A failed or unavailable source remains a measured outcome; it is not permission
  to switch to a private, cached, or unapproved substitute.

## Deliverables

### Workstream A — technical and machine-readable

Generated outputs remain ignored under
`data/processed/source-profiling/issue-490/` and are never committed as the
statewide dataset. The technical report records their manifest and safe summary.

- `source-endpoints.json`: exact endpoint identities, relationships, and observed
  capabilities.
- `snapshot-manifest.json`: artifact-relative references, retrieval metadata,
  hashes, sizes, content types, source versions, and warnings.
- `schema-profile.json`: ordered fields, types, domains, nullability observations,
  schema fingerprint, and drift results.
- `pagination-equivalence.json`: page strategy, counts, IDs, fingerprints,
  duplicates/omissions, full-download comparison, and verdict.
- `facility-profile.json`: deterministic aggregate profile and missingness.
- `facility-type-code-label.csv`: observed raw code/label pairs, counts, source
  fields, evidence status, and unresolved mappings.
- `coverage-comparison.csv`: statewide/program-specific set and field coverage.
- `source-conflicts.csv`: bounded, provenance-preserving conflict categories and
  source references.
- `content-change.json`: metadata, byte, schema, row-set, and value-change results.
- `validation-summary.json`: checks, pass/fail/block status, warnings, tool version,
  and manifest linkage.
- `docs/analysis/issue-490-technical-source-profile.md`: reproducible method,
  safe quantitative findings, validation results, and technical blockers.

Machine-readable outputs require an explicit versioned evaluation schema or
documented finite contract. All timestamps use UTC and all ordering is stable.

### Workstream B — governance and human-readable

- `docs/analysis/issue-490-governance-source-qualification.md`: publishing agency,
  system-of-record representation, terms, license, attribution, authority,
  access restrictions, allowed-use, and unresolved qualification findings.
- `docs/analysis/issue-490-governance-recommendation.md`: source precedence
  options, current-versus-historical identity rules, conflict choices, freshness
  and change-detection analysis, conditional or evidence-supported
  adopt/supplement/reject recommendation, and follow-up dependencies.

### Later integration only

- The final Issue #490 completion report.
- Any changes to `CHANGELOG.md`, `ROADMAP.md`,
  `PUBLIC_SOURCE_DATA_INVENTORY.md`, `GOVERNANCE_INVENTORY.md`, or a shared index
  or decision-summary file.
- Final reconciliation of the current inventory's authoritative-resource
  wording with Issue #490's unprofiled-candidate status.

## Automated validation requirements

Workstream A must run, without live network access during tests:

- New focused unit tests for discovery metadata parsing, hashing, raw
  preservation order, schema fingerprinting, pagination, stable ordering,
  full-download/query equivalence, source comparison, code/label inventory,
  deterministic output, redaction, and path portability.
- Existing affected `source_profiling` tests.
- JSON Schema or equivalent finite-contract validation for every machine-readable
  output.
- Targeted Ruff and mypy for changed Python.
- Documentation validation for technical documentation.
- `git diff --check` and a changed-file scope audit.

Workstream B must run:

- Documentation validation.
- Affected documentation-check unit tests.
- Link/citation presence and access-date checks appropriate to the committed
  documents.
- Deterministic scans proving required sections, cautious language, no secret or
  personal paths, no unsupported authority/completeness claims, and no edits to
  Workstream A or reserved files.
- `git diff --check` and a changed-file scope audit.

The later integration branch must rerun both focused suites, documentation
validation, security/path checks, and all required checks appropriate to the
combined change. Live endpoint observations are evidence inputs, not unit-test
dependencies.

## Decision rubric

All verdicts are recommendations for a later approval decision. None activates a
source.

### Adopt as the governed facility reference source

Recommend **adopt** only if all hard gates pass:

- Official publisher/system representation and allowed public use are verified.
- Terms, license, and attribution obligations are compatible and documented.
- Stable bounded retrieval is reproducible without browser-only behavior.
- Full-download and complete paginated query results reconcile, or a single
  authoritative access method has a documented reason to supersede the other.
- Content hashes, schema fingerprints, row counts, identifiers, and change
  behavior are measurable.
- Facility-number coverage and data quality are fit for the intended reference
  use, with explained duplicates and omissions.
- Facility type codes and labels are governed; code `733` is verified or remains
  safely unresolved without corrupting display.
- Current-versus-historical identity, precedence, conflict, blank, disappearance,
  and rollback rules can preserve provenance.
- Tests can operate entirely on deterministic fixtures and mocks.

### Use as a supplement

Recommend **supplement** when the source is qualified and reproducible but has a
bounded limitation that prevents sole-source use, such as incomplete program
scope, materially missing fields, explainable coverage gaps, unresolved type
codes, timing differences, or a need to retain program-specific sources for
particular attributes. The recommendation must name the exact ownership and
precedence of every supplemented field and keep conflicts visible.

### Reject

Recommend **reject** when any critical condition is unresolved or fails, including
incompatible or unclear permitted use, unverifiable publisher/source identity,
non-reproducible or browser-only access, unexplained service/download mismatch,
unbounded omissions/duplicates, inadequate stable facility identity, material
schema instability without controls, or inability to preserve provenance and
historical context. Rejection may be temporary pending named evidence; it must
not silently promote an older source to complete or authoritative status.

### Inconclusive

If evidence is insufficient, report **inconclusive** with explicit blockers. Do
not force adopt, supplement, or reject to satisfy the issue schedule.

## Follow-up mapping

| Issue | What Issue #490 must provide | What remains prohibited in Issue #490 |
| --- | --- | --- |
| #482 — governed facility identity projection | Verified candidate source identity; code/label inventory; current-versus-historical distinctions; precedence and conflict options; effective/source-date and disappearance questions; required provenance. | No projection, renderer dictionary, canonical bridge, backfill, or reviewer-surface change. |
| #453 — source-to-screen coverage | Active-source/version candidates; facility-number and field population counts; raw-code, descriptive-label, unresolved-code, conflict, and regression baselines; representative `733` evidence if verified. | No coverage job, release threshold enforcement, database read, or UI regression implementation. |
| #477 — operator coverage and refresh dashboard | Observable metadata, hash/schema/row-change signals, added/changed/missing categories, validation outcomes, unresolved codes, and last-accepted-source behavior. | No operator route, authorization, monitoring UI, retry action, or persisted job model. |
| #478 — scheduled governed refresh | Justified cadence evidence; stable retrieval contract; content-versus-catalog change rules; validation-before-activation; idempotence inputs; last-accepted retention; conflict, disappearance, and tombstone questions. | No scheduler, lock, checkpoint, notification, import, activation, QNAP, rollback, or deletion behavior. |

## Completion criteria

Issue #490 evaluation is ready for integration review only when:

- Every question in this plan is answered, marked not applicable with evidence,
  or listed as an explicit blocker.
- Exact public source endpoints, publisher/system representation, terms, license,
  attribution, and access limitations are evidenced.
- Controlled snapshots, hashes, schemas, counts, pagination, query/download
  equivalence, change behavior, and warnings are reproducible.
- Statewide and program-specific coverage is compared quantitatively.
- Facility types, raw codes, labels, unresolved mappings, and code `733` are
  reported without assumption.
- Deterministic fixtures and mocked responses cover the live-service boundary.
- Machine-readable outputs validate and the two human-readable reports cite
  their evidence.
- A cautious adopt, supplement, reject, or inconclusive recommendation follows
  the rubric and names all blockers.
- Dependencies for #482, #453, #477, and #478 are mapped without beginning them.
- The integration diff proves no production data, app behavior, schema, migration,
  backfill, UI, schedule, deployment, or QNAP state changed.

Completion of this evaluation still requires a separate human approval before
any source selection or downstream implementation begins.
