# CDSS CCL Facilities ArcGIS connector

This Issue #518 connector is a fixed-policy, read-only client for the inactive
ArcGIS supplementary current-reference source family. Program-specific facility
reference snapshots remain primary. The connector does not activate ArcGIS,
merge source families, write canonical/reviewer fields, or expose facility rows
to a hosted surface.

## Connector contract

- `discover()` is represented by fixed catalog, license, item, service, and
  layer metadata requests plus exact identity validation.
- `fetch()` uses only unauthenticated `GET` requests and fixed query builders.
- `store_raw()` writes every original response once under the Git-ignored
  `data/raw/source-profiling/issue-518-live-query/<UTC-run-id>/` boundary before
  parsing it.
- `extract()` reads ArcGIS `features[].attributes` only and refuses geometry or
  any field outside the approved 19-field set.
- `normalize()` uses the shared source-specific semantic-state normalizer also
  used by the PR #545 lifecycle. `CLIENT_SERVED` and `FAC_CO_NBR` remain raw
  only.
- `validate()` requires approved source identities, exact schema/domain shape,
  strict `ObjectId ASC` ordering, no duplicate ObjectIds, an empty terminal
  page, and exact set equality with the ID-only response.
- `emit()` writes one immutable `snapshot-manifest.json` and one lifecycle
  source-record payload. Emission is withheld when validation fails.

The public callable accepts only repository root, page size from 1 through
1,000, timeout, a test transport, and a deterministic test timestamp. It does
not accept a URL, host, path, method, query expression, field list, credentials,
headers, cookies, fragments, or arbitrary request parameters.

## Approved network identity

The executable allowlist contains only:

- `https://lab.data.ca.gov/dataset/community-care-licensing-facilities`
- `https://lab.data.ca.gov/licenses`
- ArcGIS item `db31b0884a074cff9260facb3f2ade45`
- service `CDSS_CCL_Facilities`
- layer 0 `Master_CCL_County_Intersect_2023`
- that layer's exact `/query` path

Metadata requests use only `f=json` or `f=pjson`. ID reconciliation uses only
`where=1=1`, `returnIdsOnly=true`, and `f=json`. Page requests additionally use
the exact approved 19 fields, `returnGeometry=false`, `orderByFields=ObjectId
ASC`, a nonnegative offset, a count from 1 through 1,000, and `f=json`.
Redirects, export/replica/cache/Azure/generated-file paths, signed or opaque
queries, retries, and caller-provided request values are rejected.

## Evidence and lifecycle

Every manifest records sanitized request identities, timestamps, status, media
type, byte count, original-response hashes, source-record payload hash,
normalized-content hash, schema/domain fingerprints, page evidence, ID-set
evidence, exact source/catalog identity, and the approved provisional
attribution. Real response bodies remain ignored local evidence and are not
committed.

The live lifecycle adapter requires the literal `isolated_nonproduction`
execution scope. It extends PR #545's existing tables and transition logic; it
does not provide a production command. Acceptance-state, promotion, and
rollback remain human-authorized lifecycle decisions and were exercised only in
an isolated disposable PostgreSQL test schema.
