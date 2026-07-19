# Issue #477 read-only operator coverage phase report

## Phase result

The read-only operator phase is implemented and integrated with Issue #453's
real deterministic v1 package. This is a phase report, not a full Issue #477
completion statement: every mutation and operational execution capability in
the later scope remains deferred.

Authorized `admin` and `developer_operator` actors with `audit_read` and the
matching scope can use these exact GET-only routes:

- `/operator/source-coverage`;
- `/operator/source-coverage/facilities`;
- `/operator/source-coverage/jobs`;
- `/operator/source-coverage/export.csv`; and
- `/operator/source-coverage/facility-ids.csv?group=<allowed-group>`.

Authentication and authorization complete before any package read. Reviewer
and tester actors remain denied, and operator navigation appears only in the
shared shell for an authorized operator page. Reviewer navigation, pages, APIs,
and exports do not expose the operator route.

The dashboard consumes validated producer aggregates and safe indexes without
recounting or reclassifying them. It separates source-to-screen coverage from
retrieval/import/artifact/checkpoint/job facts, uses bounded filters and opaque
keyset cursors without `OFFSET`, and provides only aggregate or explicitly
grouped Facility ID CSV downloads.

## Deferred Issue #477 scope

This phase intentionally does not implement retry, dry-run start, apply,
confirmation, cancel, resume, backfill, retrieval, import, job creation or
mutation, checkpoint updates, database writes, persistence, migrations,
scheduling, live package discovery, retention cleanup, deployment, or QNAP
operations. Those capabilities require separate authorization, approved design
and governance, mutation-specific audit/evidence, and a later phase report.

Retention remains `pending_policy`; no automated destructive cleanup is
authorized. Issue #490 source-selection, cadence, baseline, and raw-`733`
boundaries remain unchanged.

## Evidence boundary

Automated local hosted evidence uses a fresh server per deterministic scenario,
the exact GET route allowlist, and a real Issue #453 producer package generated
inside the ignored packet. It verifies authorized operator navigation and
in-process reviewer-tier absence without expanding browser routes. The task
produced 23 captures and 590 passing assertions with no failed assertion or
unexpected status. The final ignored zip is
`data/processed/ui-evidence/20260719-080223Z-issues-453-477-operator-coverage.zip`
(6,234,981 bytes; SHA-256
`f22142cce46c50ad2c69613b26fcfe591f5320d1eb791e021facc43bb78d6a66`).
Focused phase validation completed with 31 passing tests, and the complete
local suite completed with 1,223 passing tests and two expected skips.
