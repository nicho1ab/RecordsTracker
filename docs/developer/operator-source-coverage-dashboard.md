# Operator source-coverage dashboard

## Purpose and boundary

The Issue #477 phase-one dashboard is a read-only operator diagnostic surface.
It consumes an immutable coverage-contract package and presents producer-supplied
source-to-screen aggregates separately from retrieval, import, artifact,
checkpoint, and job facts. It does not calculate coverage or infer a coverage
classification from an operational state.

The surface is not part of the attorney/reviewer tier. It is intentionally absent
from primary reviewer navigation, reviewer pages, reviewer APIs, and reviewer
exports. Shared operator navigation remains an integration-owned follow-up.

This phase provides no retry, dry-run start, apply, confirmation, cancel, resume,
backfill, retrieval, import, job creation, checkpoint update, database write, or
artifact mutation.

## Routes and authorization

The exact routes are GET-only:

- `/operator/source-coverage`
- `/operator/source-coverage/facilities`
- `/operator/source-coverage/jobs`
- `/operator/source-coverage/export.csv`
- `/operator/source-coverage/facility-ids.csv?group=<allowed-group>`

Every route reuses the existing `audit_read` permission, existing scope match,
and existing `audit_event` authorization target. An active `admin` or
`developer_operator` actor with the requested scope can read the package.
Unauthenticated, disabled, revoked, reviewer/tester-role, and out-of-scope actors
are denied before a package path is read or package data is serialized.

The route module does not add a role, permission, provider, session, claim,
cookie, or login behavior. Production-style runtime without an explicitly
configured validated package fails closed as `Coverage report unavailable`; it
never silently substitutes fixture data.

## Contract adapter

The narrow adapter consumes contract version `1.0.0` from an explicit package
directory. It validates:

- compatible semantic version and minimum consumer version;
- deterministic report identity from the six governed identity inputs;
- deterministic facility-entry identity from source family and normalized
  Facility ID;
- required manifest/report/artifact identities and fields;
- artifact names, availability, byte counts, SHA-256 values, and media types;
- UTC timestamps, safe stable identifiers, nonnegative counts, and booleans;
- all contract-enumerated coverage, operational, job, source-selection,
  retention, release, and availability vocabularies;
- stage-count, facility-total, artifact-total, and governed-conflict
  reconciliation invariants;
- aggregate CSV header, identity, count, percentage, and safe metadata boundary;
- prohibited package keys and values, including narratives, attributes, URLs,
  paths, credentials, claims, raw errors, SQL, hosts, and source bodies.

The dashboard summary reads only `coverage-report.json`. Facility and job indexes
support authorized drill-down, filters, keyset pagination, and explicit Facility
ID lists; they do not replace producer aggregate calculations. Tiny fixture
indexes may be held in memory only by this explicit fixture adapter. No live
source, database, or producer implementation module is imported.

The shared contract describes `source_layout_classification` as a finite governed
enum but does not enumerate its members. This consumer therefore validates it as
a safe stable identifier and exposes only values already present in the validated
package. Producer/consumer integration must reconcile that missing enum list
before a live package is connected; this phase does not invent one.

## UI states and behavior

The summary keeps these regions visibly distinct:

- `Coverage through reviewer surfaces` for producer-supplied stage and terminal
  classification counts;
- `Retrieval, import, artifacts, checkpoints, and jobs` for recorded operational
  facts.

A successful operation is not described as proof of correct rendering, and a
coverage gap is not described as proof of an operational failure.

Implemented states include complete, verified empty, partial with named
unavailable dimensions, unavailable package, interrupted job with a previous
accepted report still active, controlled operational failure, hash-validation
failure, reconciliation failure, unsupported contract version, filtered empty,
and authorization denial. Unavailable or unprocessed information is never
rendered as verified zero or success.

The facility page supports only the contract allowlisted filters and sort keys.
The default page size is 25 and the maximum is 100. Ordering always adds
normalized Facility ID and facility-entry ID tie-breakers; null timestamps sort
last. Opaque seek/keyset cursors bind the report, active filter fingerprint,
sort, direction, and complete ordering anchor. Filter or sort changes reject an
old cursor and return to the first page. There are no page-number jumps or
`OFFSET` pagination.

Facility ID downloads require exactly one group: `changed`, `unchanged`,
`warning`, `failed`, `missing_artifact`, or `retry_eligible`. They emit exactly
`report_id`, `group`, `facility_id` with LF line endings and deterministic
Facility ID ordering. The aggregate CSV never contains Facility IDs or operator
index rows. Both downloads receive attachment filenames from the hosted server.

## Source-selection limits

The page preserves the Issue #490 decision without extending it:

- seven existing program-specific sources remain retained for the evaluated
  scope;
- every statewide candidate remains inactive;
- no statewide completeness baseline is approved;
- no refresh cadence is approved;
- raw value `733` has no approved `STRTP` or other facility-type mapping.

Fixture evidence is visibly labeled `Fixture coverage data`. It is not current
runtime, production, QNAP, statewide, completeness, currentness, or freshness
evidence.

## Automated validation and evidence

Run the focused tests before capture:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_hosted_operator_coverage_dashboard.py -q
.\.venv\Scripts\python.exe -m pytest tests\unit\test_hosted_operator_coverage_dashboard.py tests\unit\test_hosted_operator_coverage_evidence.py tests\unit\test_hosted_app_scaffold.py -q
```

Then use one unused loopback port:

```powershell
.\scripts\capture-operator-coverage-dashboard-evidence.ps1 -OutputRoot data\processed\ui-evidence -Port <assigned-port> -FixtureMode contract-v1
```

The capture script refuses an occupied port, checks the exact branch and HEAD,
starts a fresh fixture process for each scenario, and verifies branch, commit,
and fixture-mode markers through `/health`. Browser traffic is limited to the
five operator routes; reviewer-tier absence is checked in-process so browser
authority is not expanded.

The ignored packet and zip contain a manifest, route status, route assertions,
sanitized local HTML, CSV samples, screenshots, and a print PDF. Automated
captures cover desktop `1440x1100`, narrow `720x900`, mobile `390x844`, a
`360x450` CSS viewport at device scale factor 2 for 200% reflow evidence,
keyboard focus, long identifiers, filtered and empty states, and print media.
The packet classifies `RT-DOM-001`, `RT-TIER-001`, `RT-STATE-001`,
`RT-RWD-001`, `RT-A11Y-001`, `RT-A11Y-002`, `RT-STRESS-001`,
`RT-PRINT-001`, and `RT-SAFE-001`.

Generated evidence stays under ignored `data/processed/ui-evidence`. Do not
commit it by default.

## Deferred integration decisions

Before live producer output is connected, integration must compare the Issue
#453 producer package and Issue #477 fixture package for exact schema, aggregate
CSV columns, artifact media types, source-layout enum members, deterministic
identity encoding, and reconciliation behavior. A later decision must also set
retention duration; until then `policy_id` remains null, disposition is
`pending_policy`, and automated cleanup is not authorized.

Mutation routes, persistence, schedules, operator navigation, live package
discovery, and every QNAP/deployment concern require separately authorized work.
