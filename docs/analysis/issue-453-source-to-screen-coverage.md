# Issue #453 source-to-screen coverage technical report

## Scope and authority

This report describes the Issue #453 producer and its repository-complete
TransparencyAPI/shared-projection extension. It is not a final issue-completion
report: deployment and every applicable non-provider Hosted acceptance gate
remain required. The product owner accepts the residual risk when the approved
automated Cloudflare authenticated-UI assertion provider is unavailable, so
provider unavailability alone does not block completion and must not be reported
as a passed authenticated-UI run. This report does not authorize
lifecycle actions, source retrieval or activation, retention automation,
canonical backfill, scheduling, deployment, or an operational job action.

- Planning merge SHA: `fa5ad12b434020162f813dce34f72a9462a878d8`.
- Shared contract: `1.1.0`.
- Minimum consumer version: `1.1.0`.
- Producer schema ID: `issues-453-477-coverage-report-v1`.
- Producer version: `source-to-screen-audit-v1`.
- JSON Schema:
  `schemas/issues-453-477-coverage-report-v1.schema.json`.

The producer reuses
`python -m ccld_complaints.source_to_screen_audit`. It consumes field IDs from
the existing source-to-screen catalog and tracked inventory. The contract schema
and Issue #490 technical profile schema are package/report schemas, not canonical
field catalogs.

Contract `1.1.0` extends the same report with
`coverage.facility_reference`; it does not add a competing coverage framework.
The extension reuses the active accepted TransparencyAPI lifecycle and
ADR-0017's authorization-before-read shared projection. TransparencyAPI is the
primary current-reference family, ArcGIS remains supplementary, CKAN/program
observations remain historical or controlled fallback, and complaint/report-
time observations remain historical. The older Issue #490 inactive-statewide-
candidate statements later in this report are retained as historical v1.0
context and do not override these merged Issues #553/#554/#482 decisions.

## TransparencyAPI and shared-projection extension

The facility-reference object records safe active-snapshot identity and
fingerprints plus closed aggregate inventories for 16 public projection fields,
10 stages, 11 failure categories, 8 applicable surface IDs, 29 metrics, and 13
release criteria. It includes eligible and leading-zero Facility Number counts;
blank, duplicate, malformed-block, and unknown-code quarantines; valid-zero type
`777`; unresolved raw `733`; address, telephone, administrator, bulk status, and
Closed Date population; placeholder preservation; current/supplementary/
historical conflicts; surface availability; unsafe-report checks; quarantine
exclusion; and reviewer-state immutability.

CONTACT, detail status, and complaint-linked conflict metrics use explicit
`unavailable` status when those authorized detail or historical rows are not in
the measured accepted snapshot/projection. The producer never converts missing
authority into a verified zero. Field-stage rows retain separate blank, absent,
unavailable, invalid, conflict, failure, and not-applicable counts. Surface rows
measure public-projection availability and carry a repository-versus-hosted
evidence status; they do not claim that repository checks are a deployed Hosted
browser run.

The release extension compares the current aggregate object with the prior
accepted package when one exists. Zero-tolerance checks cover facility-count,
blank-state, unresolved-code/label, source-conflict, stored-row/projection
reconciliation, read-model, surface-rendering, stage-balance, quarantine,
placeholder, context-conflation, and unsafe-report regressions. A breach fails,
or becomes `reviewed_exception_required` only when the existing explicit
reviewed-exception input names it; the producer never approves the exception.

## Package and identity

One package contains:

| Artifact | Availability | Boundary |
| --- | --- | --- |
| `manifest.json` | required | Package versions, identities, safe source snapshot metadata, payload hashes, provenance, and retention |
| `coverage-report.json` | required | Aggregate field/stage coverage, terminal categories, operations, reconciliation, criteria, and release assessment |
| `operator-facility-index.jsonl` | explicit available/unavailable state | Public Facility ID plus only the contract-permitted safe operator metadata |
| `operator-job-index.jsonl` | explicit available/unavailable state | Safe recorded-job metadata and aggregate job counts |
| `aggregate-coverage.csv` | generated | Aggregate rows only; no Facility ID column or values |

The manifest lists the four payload artifacts and does not attempt to hash
itself. Each available payload entry records canonical relative name, byte count,
lowercase SHA-256, and media type. An unavailable optional index has zero bytes,
null hash, a controlled reason category, and no file on disk.

The report ID is `coverage-report-v1-<sha256>`. The digest input is canonical
JSON with exactly these named fields:

1. contract major version;
2. evaluation ID;
3. ordered source snapshot IDs;
4. criteria-set ID;
5. scope ID; and
6. producer schema ID.

`generated_at` is captured once in UTC `Z` form and excluded from identity.
JSON uses UTF-8, sorted keys, compact canonical separators, and LF. JSONL uses
one canonical object per LF-terminated line. CSV uses UTF-8, LF, RFC 4180
quoting, stable row ordering, and the exact header documented in the schema
tests. A generation directory is immutable: different bytes cannot overwrite an
existing generation instance, including a different result claiming the same
identity.

## Field and stage coverage

Every governed inventory field is represented at all eight stages:

1. `source_presence`;
2. `extraction`;
3. `normalization`;
4. `canonical_allocation`;
5. `postgresql_population`;
6. `read_model_exposure`;
7. `complaint_page_rendering`; and
8. `facility_hub_rendering`.

An eligible row balances across `successful`, `blank`, `absent`, `unavailable`,
`unsupported`, `conflict`, `failure`, and `skipped`. Structural catalog
projection contributes zero or one observation, while a governed aggregate
read adapter may contribute multiple observations per field/stage. A
non-applicable reviewer surface has zero eligible rows and zero state counts; it
is not treated as missing. The terminal distribution has its own explicit
eligible count. Reconciliation requires both distributions to balance exactly.
The structural catalog dispositions map to the contract terminal vocabulary
without changing the approved inventory or adding a canonical field.

The closed terminal categories are:

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
- `intentionally_internal`; and
- `not_applicable`.

The Issue #453 aliases `source_absent`, `source_unavailable`, and
`conflicting_source` serialize as `source_label_absent`,
`source_artifact_unavailable`, and `conflicting_sources`. Failure categories are
never collapsed to generic missing.

## Operational bridge and separation

The same allowlisted input boundary accepts safe aggregate or operator-index
metadata from governed fixtures or a future existing read-only adapter. It
reports refresh, retrieval, import, processing, change, preserved-artifact,
hash-validation, checkpoint, job, conflict, retry-eligibility, and
operator-intervention state. It contains no source content and performs no
operation.

Operational and coverage dimensions remain independent. A completed operation
can coexist with `read_but_not_rendered`. An interrupted or failed operation can
record that a separately identified previous accepted report remained active.
Neither state is derived from the other.

## Reconciliation

The producer emits every stable invariant ID, even when failed:

- `coverage.facility-eligibility-total`;
- `coverage.processing-outcome-total`;
- `coverage.refresh-state-total`;
- `coverage.change-outcome-total`;
- `coverage.retrieval-state-total`;
- `coverage.import-state-total`;
- `coverage.preserved-artifact-state-total`;
- `coverage.hash-validation-state-total`;
- `coverage.preserved-artifact-total`;
- `coverage.governed-conflict-total`;
- `coverage.operator-facility-conflict-total`;
- `coverage.operator-intervention-total`;
- `coverage.job-state-total`;
- `coverage.field-stage-balances`;
- `coverage.field-stage-inventory`; and
- `coverage.terminal-classification-total`.

Applicable invariant rows contain only expected count, actual count, and
`passed` or `failed`; an unavailable optional index uses `not_applicable` for its
index-dependent invariant. Any failed invariant sets
`reconciliation_status=failed`, package availability to
`reconciliation_failed`, safe failure category to `validation_failed`, and the
release reconciliation criterion to failed. Counts are never repaired or
changed to force a pass.

## Criteria, thresholds, and release assessment

The stable `criteria_set_id` names explicit baseline, threshold, and observed
aggregate inputs for the retained existing or active accepted scope. The v1
checks assess:

- previously populated governed fields becoming blank;
- verified descriptive facility-type labels regressing to unresolved evidence;
- facility-count decline beyond the named maximum;
- required source-to-screen stage regression;
- reconciliation failure; and
- unresolved or conflicting facility identity/type evidence.

Each check records baseline count, observed count, threshold count, status, and
an optional input exception ID. A breached criterion is `failed`, or
`reviewed_exception_required` when explicit exception data was supplied. The
producer does not approve an exception. Nonzero unresolved evidence within its
named threshold is `warning`. The overall result is `passed`, `warning`,
`failed`, or `reviewed_exception_required`.

No statewide baseline is created.

## Privacy and serialization boundary

Allowlisting is the primary output control. Unknown fields are rejected before
serialization. Defense-in-depth validation also rejects narratives, raw HTML,
source bodies, URLs, absolute or raw paths, connection strings, secrets,
credentials, tokens, cookies, authentication claims, container or host names,
stack traces, SQL, and uncontrolled errors.

The aggregate report and CSV contain no Facility IDs. The operator facility
index contains only public Facility ID, a deterministic opaque facility-entry
ID, and the exact contract-safe metadata. Retrieval and import states are used
to calculate report aggregates but are not added to the exact facility-index
row contract. Source names, facility names, addresses, telephone numbers,
licensees, complaint counts, record values, narratives, raw hashes, raw paths,
and source URLs are not serialized.

## Fixture and command evidence

The governed bundle
`tests/fixtures/source_to_screen_coverage/scenarios.json` defines:

- complete balanced;
- verified empty;
- partial unavailable stage;
- failed reconciliation;
- version mismatch;
- hash-validation failure;
- interrupted job with previous accepted data active;
- raw `733` unresolved;
- adjacent keyset pages; and
- prohibited content rejected.

Run one deterministic fixture generation twice into separate ignored generation
directories:

```powershell
Set-Location <repo-root>
.\.venv\Scripts\python.exe -m ccld_complaints.source_to_screen_audit `
  --coverage-fixture tests\fixtures\source_to_screen_coverage\scenarios.json `
  --coverage-scenario complete-balanced `
  --generated-at 2026-07-19T18:00:00Z `
  --output-dir data\processed\source-to-screen-audit\issue-453-evidence-v2-first
```

Repeat with `issue-453-evidence-v2-second`, then compare identities, artifact
names, bytes, ordering, and manifest hashes. These are fixture artifacts, not
current runtime or statewide evidence.

The existing read-only runtime audit shape remains:

```text
python -m ccld_complaints.source_to_screen_audit --mode runtime --output-dir <ignored-runtime-output>
```

This task did not execute that command. Production-style integration must adapt
its aggregate result plus existing operational reads into the allowlisted
contract input with `generation_mode=read_only_boundary`. It must not substitute
the fixture bundle when a runtime stage is unavailable.

## Retention and provenance

Manifest provenance records producer/schema version, criteria, evaluation and
scope IDs, source snapshot identities and selection states, governed fixture and
input-manifest IDs, artifact hashes, generation mode, and generation time.
Logical artifact names are repository-relative.

Retention duration is unresolved. Until a separate policy is approved,
`policy_id` and `retain_until` are null, disposition is `pending_policy`, and no
automated destructive cleanup is authorized. A previous accepted report ID can
be recorded without labeling it current.

## Contract 1.1 local acceptance evidence

Controlled evidence is retained under the ignored repository-relative root
`data/processed/source-to-screen-audit/issue-453-transparencyapi-acceptance/`.
No file under that root is tracked. Two fixture packages generated from the
assigned secondary worktree with the documented primary interpreter and fixed
UTC time are byte-identical:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `aggregate-coverage.csv` | 1,830,569 | `01c330d102bac9f88257eaf6bde4ea0752bc93742ac3b713d1c0c153c8a1539d` |
| `coverage-report.json` | 326,572 | `91bc2a8e9dcdc4e35856d5259a27c6c8019e26a4e111e2b63b1cb8cea19c1be1` |
| `manifest.json` | 3,042 | `bf1f35180c6aa47b7c08f2332206eead58a3f756b62c78234cf92b63d1fdb9a1` |
| `operator-facility-index.jsonl` | 2,028 | `93297aa46bada8c25f9ed01de30b01d399d47e98b7382081a48b8ac5e2df9216` |
| `operator-job-index.jsonl` | 689 | `a300a8160e25f9909bd083a0141ffff03a3ad4df6fbb6a3cb6959e23c435b036` |

The fixture report ID is
`coverage-report-v1-6b6670913151e7bb7f4ef3225f309cdd95a6724090a31f8ca9f1943f6d9a60cd`.
An isolated disposable PostgreSQL 16 run produced report
`coverage-report-v1-12205f2b28224704e9d00afa4b82ff9a29b0c84c922bafa41454c7738f33c1a5`.
Its reconciliation and facility release assessment passed; repeated generation
had the same report ID and artifact bytes; and reviewer-created-state count was
unchanged at one row. The aggregate summary SHA-256 is
`2fa4e29597f5d89483530bbb081651c050bf02a5eabd074531a24310c0db4d1f`.
The applicable PostgreSQL snapshot-lifecycle module completed with three passes;
one separately governed ArcGIS controlled-real-candidate case skipped because
its live manifest was not supplied. The disposable database container was
removed after validation.

Automated scans found no facility/contact values, complaint text, raw report
URL, `fakeout.gov`, source body, credential, token, cookie, authentication
material, private path, or local absolute path in the aggregate extension or
summary. This evidence is local and does not claim deployment or an automated
authenticated Hosted UI pass.

Final validation at the repository-stable point completed with `1,427 passed,
6 skipped`. Full-repository Ruff passed; mypy reported no issues across 83 source
files; documentation validation passed; 57 documentation-quality tests passed;
the bounded secret scan and dependency check passed; Alembic reported the single
head `20260721_0010`; and `git diff --check` passed. The six full-suite skips are
environment- or optional-evidence-gated tests and are not Issue #453 failures.
No production code changed after this full-suite run.

## Historical Issue #490 limits

The original v1.0 package explicitly preserved the then-current Issue #490
outcome. Issues #553/#554/#482 supersede only its forward-looking source-family
selection; the evaluation artifacts remain historical evidence:

- the existing program-specific source family is retained for the evaluated
  scope without a completeness or freshness claim;
- every statewide candidate remains `inactive_candidate`;
- statewide completeness baseline is `not_established`;
- cadence remains `not_approved`; and
- raw `733` mapping status remains `unresolved`, with no STRTP or other
  descriptive label emitted.

## Historical v1.0 validation and evidence

Focused validation completed against the assigned worktree:

- principal deterministic package regression: `1 passed`;
- aggregate-count regression: `1 passed`;
- complete focused source-to-screen unit file: `42 passed`;
- targeted Ruff over the two producer files and focused test: passed;
- strict mypy over the two producer files: passed with no issues;
- `scripts/docs.ps1`: passed;
- focused documentation-quality tests: `11 passed`;
- `scripts/check_no_secrets.py`: passed;
- `git diff --check`: passed; and
- JSON syntax plus deterministic two-generation artifact comparison: passed.

The assigned worktree did not contain a repo-local `.venv`, so the literal
`.\.venv\Scripts\...` Python, pytest, and mypy launchers were unavailable. The
same existing project virtual-environment toolchain was invoked read-only from
the synchronized base checkout with this worktree's `src` on `PYTHONPATH`.
Ruff, documentation, secret, and Git checks ran from the assigned worktree. The
complete local test suite was intentionally not run because the task requires
focused validation only.

Two ignored fixture evidence generations are retained at:

- `data/processed/source-to-screen-audit/issue-453-evidence-v2-first/`; and
- `data/processed/source-to-screen-audit/issue-453-evidence-v2-second/`.

Both use report ID
`coverage-report-v1-ae70bf79d50bb9d3ea399f3d39f10ae829bb98370df575d62dc22f41f36c8c81`,
contain 127 inventory fields, 1,016 field/stage rows, 16 passing invariants, two
synthetic facility rows, one synthetic job row, a terminal eligible count of
127, and a passing release assessment. Both packages also pass the standalone
package validator. Their artifact names and bytes match exactly:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `aggregate-coverage.csv` | 1,820,483 | `bf7098774ee5d0ffb88640bce6c692e17c5ac12601d26a64ce220a1de5b234da` |
| `coverage-report.json` | 282,070 | `567c8cf22ca2c0b7d2bc27b22078d3be3658fa0f81f6066f830c5a98335c2145` |
| `manifest.json` | 2,521 | `d75837099f3b11be470d80b2af62f3c80f3be45b508f1a60819290b6f61a485d` |
| `operator-facility-index.jsonl` | 2,028 | `0ecb611fdb931487a7447ec6d47c9a3126e3f8ab9053c18dd8b27273fdaf0d40` |
| `operator-job-index.jsonl` | 689 | `ee6f8432eb97ed4c54f2b839aeb1a7280a88e6fb6efc0407ab7fccd768d0e2b6` |

Remaining production-style evidence is intentionally outside this isolated
phase: a later authorized integration must connect validated read-only runtime
aggregates to the package boundary, compare the independent Issue #477 consumer
fixture vectors, and demonstrate the contract against a production-style local
runtime without a live source call, data mutation, fixture fallback, deployment,
or QNAP access.
