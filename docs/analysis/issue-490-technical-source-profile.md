# Issue #490 technical statewide facility source profile

## Outcome and boundary

**Technical outcome: inconclusive.** The existing seven program-specific
California Open Data datastores were retrieved, preserved, and profiled
successfully. The allowlisted Licensed Child Care Centers ArcGIS layer was also
profiled successfully, but it contains only 15 records and is not assumed to be
statewide or equivalent to a program download. The allowlisted Family Child
Care Homes ArcGIS identity returned an application-level `Invalid URL` result.

The approved Community Care Licensing Facilities ZIP redirected to the exact
approved S3 object, but the one bounded retrieval returned HTTP `403`. The
official California Open Data catalog also identifies a different statewide
ArcGIS service and GIS export endpoints that were not in the network allowlist.
The statewide candidate's row schema, row count, pagination, and
download/service equivalence therefore remain blocked.

This report evaluates a candidate. It does **not** approve adoption, production
import, a connector, canonical allocation, precedence, backfill, UI behavior,
scheduling, deployment, QNAP activity, or any data-store change. It is not the
Issue #490 governance recommendation.

## Evidence contract and method

Evaluation contract: `issue-490.source-profile.v1`.

Validated generated output directory:

`data/processed/source-profiling/issue-490/20260719T035408Z/`

The output set is:

- `source-endpoints.json`
- `snapshot-manifest.json`
- `schema-profile.json`
- `pagination-equivalence.json`
- `facility-profile.json`
- `facility-type-code-label.csv`
- `coverage-comparison.csv`
- `source-conflicts.csv`
- `content-change.json`
- `validation-summary.json`

The evaluation follows this isolated sequence:

`discover -> fetch -> store raw -> extract -> normalize -> validate -> emit`

Original response bytes were written with exclusive-create behavior before
parsing. SHA-256 covers the original stored bytes. Canonical row hashes are
separate SHA-256 fingerprints over stable field order and normalized scalar
representations; they do not replace original values or create canonical
RecordsTracker fields. JSON output uses sorted keys and finite statuses. CSV
output uses stable row ordering and LF line endings. Raw statewide and
program-specific rows remain ignored and untracked.

Reproduction from preserved evidence, using placeholders rather than a local
machine path:

```powershell
Set-Location <repo-root>
$env:PYTHONPATH = (Resolve-Path src).Path
python scripts/profile_statewide_facility_source.py `
  --evaluate-snapshots `
  --catalog-dir <catalog-snapshot-dir> `
  --arcgis-dir <arcgis-metadata-snapshot-dir> `
  --arcgis-query-dir <arcgis-query-snapshot-dir> `
  --prior-discovery-dir <prior-discovery-snapshot-dir> `
  --datastore-metadata-dir <datastore-metadata-snapshot-dir> `
  --dictionary-dir <dictionary-snapshot-dir> `
  --program-records-dir <program-record-pages-dir> `
  --statewide-safe-attempt <sanitized-statewide-attempt-json> `
  --output-dir <new-ignored-output-dir>
```

Automated tests make zero live network calls. Live retrieval and offline
evaluation are separate CLI actions.

## Catalog and candidate identities

The three California Lab pages all returned HTTP `200`, but their identifiers,
creation dates, and resource families differ. They remain separate candidate
identities:

| Catalog page | Dataset identifier | Created | Metadata modified | Resources | Technical relationship |
| --- | --- | --- | --- | ---: | --- |
| `community-care-licensing-facilities` | `c5cb7a9e-e99a-4f7a-b183-60bc4799a7c8` | `2025-01-11T06:22:36.062066` | `2026-07-18T06:15:38.936919` | 7 CSV datastores plus 1 ZIP | Existing program-specific resource family; relationship to geospatial candidates unresolved |
| `community-care-licensing-facilities1` | `88edd96b-b84b-4d1a-85f9-0a7029b6b4a6` | `2026-03-31T06:15:35.114317` | `2026-07-18T06:15:35.231693` | 9 CSV/geospatial/aggregate resources | Catalog-linked statewide ArcGIS candidate; relationship to other pages unresolved |
| `community-care-licensing-facilities2` | `5b8c30a1-387d-4361-9c0e-b333b909c71d` | `2026-06-25T06:15:35.965241` | `2026-07-18T06:15:33.667801` | 7 CSV/geospatial/aggregate resources | Separate geospatial candidate; predecessor/successor/duplicate status unresolved |

The primary CHHS dataset page, each allowlisted resource page, the California
Lab publisher listing, and the Data.gov catalog page were preserved. Both
allowlisted CKAN `package_show` requests returned `404`: one used the
`ccl-facilities` slug and one used dataset UUID
`46ffcbdf-4874-4cc1-92c2-fb715e3ad014`. Those failures were not retried.

Catalog modification timestamps are reported only as metadata. They are not
treated as evidence that row content changed.

## Retrieval and hash findings

The sanitized statewide redirect chain was:

1. `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/7115b4ae-4f70-463c-975f-192bd32fa826/download/ccl-facilities-zjho3_b6.zip`
2. `https://s3.amazonaws.com/og-production-open-data-chelseama-892364687672/resources/7115b4ae-4f70-463c-975f-192bd32fa826/ccl-facilities-zjho3_b6.zip`

No signed query parameter was retained. The final response was HTTP `403`,
`application/xml`, 2,674 bytes, retrieved at `2026-07-19T03:16:04Z`, with
SHA-256
`171115bf135d62bca2e907e468699ab1154c3cb5b177aa31a62a6f292d129e6c`.
The error body echoed signed-request material, so it was removed after hashing;
only the sanitized result metadata remains in the ignored log boundary. This is
a measured source-access failure, not a valid ZIP snapshot.

The final snapshot manifest contains 62 retained raw artifacts and the
sanitized non-retained ZIP-attempt record. Exact request URLs, safe query
parameters, UTC retrieval times, response status, content type, byte count,
SHA-256, relative artifact reference, and warnings are recorded in
`snapshot-manifest.json`.

Key generated-output hashes are:

| Output | SHA-256 |
| --- | --- |
| `source-endpoints.json` | `33090da686efe47f33d6332f68cfe3c27117ef95531b4ea15986828c7c54aaf9` |
| `snapshot-manifest.json` | `ba3e053fe83f3941210fd1fa29603677b2343c2a55d4e81cac03e21a37ce0589` |
| `schema-profile.json` | `3ac9efa4ea3e87d74ae7720ce0a179169848de6adc205e030f220c6db738accf` |
| `pagination-equivalence.json` | `d304ec4256c1e91ff46284271a8b4b9a811ec1a861c5ac224e26a3243ab2035e` |
| `facility-profile.json` | `e091928f35951fe23a8a5c4b99dcd77f5433e3acbcbb40d2ca5115389a2a779e` |
| `facility-type-code-label.csv` | `bc4bef9d3a49afe4601bbdd600d9e1e45b9853a3a3e05d9d5c38b839abb2fbcb` |
| `coverage-comparison.csv` | `692649cc5e63a929e344b7a7baf49007b4fe3223f40c6c716eb992cf85329674` |
| `source-conflicts.csv` | `45cc4cfb6d8fcd9997ed3f3137e31bb11c6679ec6fa387a41bbadf569c8f5545` |
| `content-change.json` | `86dc9c977a089a50764152d452cfd147a59ebcc3fa914df9dd1e62d70338db13` |
| `validation-summary.json` | `7e3492c702cd042bbe38017387209a50ca557181eec862619ca44ad8766432c0` |

## Program-source schema and facility profile

All seven datastore resources returned a common ordered 18-field shape:
`_id`, facility type and number, name, licensee, administrator, telephone,
address, city, state, ZIP, county, regional office, capacity, status,
first-license date, closed date, and file date. Metadata types differ: some
resources declare the two license dates as timestamps, one declares them as
text, and the remaining group produces a third schema fingerprint. These
differences are preserved rather than coerced away.

The controlled snapshot contains 68,527 program rows and 68,526 nonblank unique
facility identifiers. One 24-Hour Residential Care for Children row has no
facility identifier. No resource has a duplicate nonblank facility identifier.

| Program source | Rows | Unique IDs | Missing IDs | Licensed | Closed | Inactive | Pending | Other observed status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Child Care Centers | 19,426 | 19,426 | 0 | 14,072 | 4,448 | 401 | 481 | `ON PROBATION`: 24 |
| Residential Care Facilities for the Elderly | 12,522 | 12,522 | 0 | 7,939 | 3,821 | 0 | 739 | `ON PROBATION`: 23 |
| 24-Hour Residential Care for Children | 1,960 | 1,959 | 1 | 1,162 | 620 | 0 | 172 | `ON PROBATION`: 6 |
| Foster Family Agencies | 709 | 709 | 0 | 411 | 296 | 0 | 2 | none |
| Home Care Organization | 3,654 | 3,654 | 0 | 2,247 | 1,197 | 0 | 210 | none |
| Family Child Care Homes | 19,758 | 19,758 | 0 | 13,986 | 5,160 | 415 | 170 | `ON PROBATION`: 27 |
| Adult Residential Facilities | 10,498 | 10,498 | 0 | 7,622 | 2,354 | 0 | 511 | `ON PROBATION`: 10; anomalous date-like value `9/2/1997`: 1 |

Names, licensees, addresses, cities, states, ZIPs, counties, and capacity are
nearly complete for most resources. Bounded exceptions include one missing
Child Care Centers administrator and telephone, two missing regional-office
values in the 24-hour source, 13 missing Foster Family Agency capacities, and
only 1 populated capacity among 3,654 Home Care Organization rows. Date coverage
is partial by design: closed dates are not populated for every non-closed row,
and first-license dates are not universal. Exact blank, null, absent, invalid,
distinct-value, date-format, and normalization-warning counts are in
`facility-profile.json`.

The program resources expose descriptive `facility_type` values, not a separate
type-code field or code domain. Observed labels include 594 rows labeled
`SHORT TERM RESIDENTIAL THERAPEUTIC PROGRAM` and 3 rows labeled
`STRTP - CHILDRENS CRISIS RESIDENTIAL` in the 24-hour source. This establishes
only observed labels; it does not map numeric code `733`.

## ArcGIS pagination, ordering, and equivalence

The allowlisted Licensed Child Care Centers layer reports:

- Layer ID `0`, name `ChildCareFacilities`.
- Point geometry.
- Object-ID field `OBJECTID`.
- Maximum record count `1000`.
- Supported query formats `JSON`, `geoJSON`, and `PBF`.
- 17 ordered fields and no accessible facility-type code domain.

The ID query returned 15 object IDs. Maximum-size pagination produced page
counts `[15, 0]`; smaller pagination produced `[7, 7, 1, 0]`. Both terminated,
used stable `OBJECTID` ordering, and had no duplicate, omitted, unexpected, or
malformed record. The maximum page, small pages, object-ID batch, and GeoJSON
property set were equivalent by facility identifier and canonical row
fingerprint.

Two ID-only snapshots had different raw byte hashes because response bytes
differed, but their schema, 15-ID row set, and field values were equivalent.
This demonstrates why byte change, metadata change, schema change, row-set
change, and field-value change are reported separately.

The 15 ArcGIS rows all intersect the 19,426-row Child Care Centers datastore;
there are 0 ArcGIS-only identifiers and 19,411 datastore-only identifiers.
There are 12 differing nonblank values across those shared records: 5 licensee,
4 name, 1 address, 1 capacity, and 1 status difference. Values are represented
only by bounded source-preserving fingerprints in generated conflict output.
The relationship remains `inconclusive`: the approved evidence does not show
that the 15-row ArcGIS layer is a complete, current, or equivalent Child Care
Centers source.

Statewide download/service equivalence is **blocked**, not failed. The ZIP was
unavailable, and the catalog-linked statewide service was not allowlisted. A
matching row count alone would not have been accepted; identifier sets, schema,
and row fingerprints are required by the implementation and tests.

## Cross-source coverage and conflicts

All 21 program-to-program comparisons had zero shared nonblank facility
identifiers in this snapshot. One-side-only rows are retained as scope
differences, not classified as omissions or closures. The program sources have
different represented populations and must not be silently combined as if they
were duplicate snapshots.

`coverage-comparison.csv` contains 22 comparison rows: 21 program-pair scope
comparisons and the ArcGIS-center/program-center comparison.
`source-conflicts.csv` contains five bounded conflict categories totaling 12
field differences. Existing PostgreSQL rows were not read or treated as public
source truth.

Disappearing rows are not treated as closures. Closure is reported only from an
observed source status or closed-date value.

## Code 733 finding

**Status: unresolved.** Exact value `733` occurs in ordinary datastore `_id`
contexts, but it occurs zero times in every approved `facility_type` or
`Facility_Type` field. The approved dictionaries contain field types only and
provide no facility-type code domain. No accessed ArcGIS metadata exposes a
domain mapping `733` to a label.

There is therefore no technical evidence in the approved sources that `733`
uniquely means STRTP or any other facility type. No application mapping,
renderer dictionary, canonical mapping, or reviewer-facing label was added.

## Blocked endpoints and dependent work

The official catalog exposed these exact relevant endpoints, but they were not
allowlisted and were not accessed:

- `https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/CDSS_CCL_Facilities/FeatureServer/0`
- `https://gis.data.chhs.ca.gov/datasets/CDSS::community-care-licensing-facilities`
- `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/csv?layers=0`
- Other format-specific endpoints and three aggregate ZIP identities listed in
  `source-endpoints.json`.

Access to the catalog-linked statewide layer and one stable corresponding CSV
or ZIP export is required to complete statewide schema profiling, row counts,
pagination, download/service equivalence, facility type/domain analysis, code
`733` investigation, and statewide-to-program coverage comparison. The three
California Lab candidate identities also require an evidence-supported
predecessor/successor/duplicate relationship before any cross-candidate
equivalence conclusion.

## Validation

Focused validation status at report preparation:

| Check | Result |
| --- | --- |
| New Workstream A regression module independently | Pass: 20 tests |
| Existing plus new focused modules together | Pass: 27 tests |
| Targeted Ruff | Pass |
| Targeted mypy | Pass: 2 source files |
| Documentation validation | Pass |
| `git diff --check` | Pass |
| Workstream A ownership and ignored-artifact audit | Pass |
| Versioned JSON output contract | Pass for all 7 JSON outputs |
| CSV finite header contracts and stable ordering | Pass for all 3 CSV outputs |
| Program datastore ordered pagination and terminal pages | Pass for all 7 resources |
| ArcGIS maximum/small/object-ID/GeoJSON checks | Pass |
| Sensitive-query and personal-path scan of final output | Pass |
| Statewide ZIP retrieval | Blocked: HTTP `403` |
| Statewide download/service equivalence | Blocked: unavailable download and unallowlisted service |
| Family Child Care Homes ArcGIS endpoint | Fail: application-level `Invalid URL` |
| Code `733` unique mapping | Inconclusive |

The generic repository secret scanner also identified the same static ArcGIS
HTML URL-construction placeholder in three ignored public response snapshots.
No credential value was present; a separate non-value scan of retained evidence
found no signed parameter, cookie, authorization header, or personal path.
