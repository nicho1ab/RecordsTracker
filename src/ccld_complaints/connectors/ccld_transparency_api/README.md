# CCLD TransparencyAPI facility-reference connector

This versioned connector implements Issue #554's governed current-reference source family.
It uses only the official public CCLD TransparencyAPI allowlist:

- `DownloadStateData?id={exportId}` for the seven approved exports;
- `FacilityDetail/{facilityNumber}` for bounded current detail;
- `Group/` and `CACounty` for type and county taxonomies;
- `FacilityReports/{facilityNumber}` for ordered report metadata; and
- `FacilityReports?facNum={facilityNumber}&inx={zeroBasedIndex}` only after the
  preserved list proves the index is in range.

`FacilitySearch` is never used for enumeration. Raw `REPORTPAGE` values containing
`fakeout.gov` are retained only as rejected source evidence and are never requested.
Requests are unauthenticated GETs, permit no redirect, and accept no caller URL.

## Snapshot boundary

Every response body is written byte-for-byte before parsing. The manifest records the
request and final URL, retrieval time, status, safe response headers, media type,
content disposition, byte count, SHA-256, and source identity. Cookie or authentication
headers are neither sent nor retained. One promotable candidate requires all seven bulk
exports plus `Group/` and `CACounty`.

The parser uses Python's CSV implementation, enforces the exact 31- or 38-column fixed
header contract, keeps Facility Number as text, and preserves repeating complaint blocks
in source order. Blank and duplicate identifiers, malformed trailing blocks, unknown
detail type codes, not-found detail sentinels, and report list/helper mismatches remain
explicit quarantines. Warnings retain suspicious dates, status/Closed Date disagreement,
and source disappearances without inventing corrections, closure, or deletion.

Snapshot metadata and active/prior pointers reuse the shared immutable lifecycle.
TransparencyAPI artifacts, rows, quarantines, and disappearances have separate tables;
ArcGIS supplementary observations and CKAN historical evidence remain separate. This
connector does not write canonical facility values or reviewer-created state.

## Commands and scheduling

The operator lifecycle CLI invokes the existing package and shared snapshot-lifecycle
functions; it does not implement another state machine. Invoke it as:

```text
python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle <command>
```

Its explicit commands are `inspect-package`, `stage`, `validate`, `accept`, `promote`,
`rollback`, `status`, and `dry-run`. `inspect-package` needs only a manifest path.
`status` and `dry-run` use read-only database connections. Every other database command
runs as one transaction and never combines lifecycle stages.

Promotion and rollback require both `--expected-active` and `--expected-prior`. Use the
literal `none` for an expected absent pointer; the first promotion therefore requires
`--expected-active none --expected-prior none`. The guards are checked in the same
transaction as the existing promotion or rollback function. A mismatch fails closed.

All successful output is deterministic aggregate-safe JSON on stdout. Failures emit a
concise category-only JSON object on stderr and return nonzero. Output excludes raw rows,
source bodies, arbitrary source values, URLs, headers, contact details, reviewer content,
database connection values, and local paths. The only named record checks are the three
explicitly approved public Facility ID/name pairs in `dry-run`.

The lifecycle CLI cannot retrieve a package. A human operator must place one
already-preserved, complete source family in an approved mounted raw-data path and pass
its `manifest.json`. The lifecycle CLI also provides no scheduler, automatic refresh,
canonical allocation/backfill, reviewer-state mutation, snapshot deletion, browser
route, or deployment hook.

### Local package capture

The separate local capture CLI invokes `TransparencyApiConnector.capture_snapshot` and
then validates the resulting manifest with `inspect_transparencyapi_package`:

```text
python -m ccld_complaints.cli.transparencyapi_snapshot_capture capture --output-dir <repo-root>
```

`--output-dir` must be a RecordsTracker repository root. The connector creates a new
timestamped package under the ignored
`data/raw/ccld/transparencyapi-facility-reference` directory. No URL argument exists.
The command always requests exactly the seven approved bulk exports followed by `Group/`
and `CACounty`; it does not call `FacilitySearch`, facility detail, or report endpoints.

Each response body is written before parsing. A successful command requires nine exact
artifacts and a rejection-free lifecycle inspection. It emits aggregate-safe JSON with
the repository-relative package directory, manifest filename, snapshot and hash
identities, counts, and timestamp. It neither reads nor writes a database.

If transport or validation fails, the command returns nonzero and emits only a sanitized
failure category on stderr. Any partial timestamped directory left by a transport failure
is preserved evidence, not a complete package: it has no acceptance authority and must
not be transferred, staged, or reconstructed. Capture is manual and local-only; the CLI
does not schedule retrieval, upload files, access QNAP, or invoke lifecycle mutations.
