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

There is intentionally no production CLI, scheduler, deployment hook, or reviewer
integration in Issue #554. Later activation, projection, refresh, operator, deployment,
and hosted-acceptance work remains under its separately governed issues.
