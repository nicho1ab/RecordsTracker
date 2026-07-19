# Build Week 2026 ArcGIS facility-reference shadow comparison

## Evidence boundary and result

This Phase A evaluation compares the current CDSS ArcGIS facility layer with
its catalog-advertised CSV export and the seven retained program-specific
facility datastores. It does not activate a source, change precedence, write to
PostgreSQL, backfill data, schedule refresh, or change an application route.

The definitive ignored evidence is:

- raw source responses:
  `data/raw/source-profiling/build-week-arcgis/20260719T224146Z/`;
- processed contract `build-week-2026.arcgis-shadow-evaluation.v1` package:
  `data/processed/source-profiling/build-week-arcgis/20260719T224145Z-live-definitive/`.

The raw boundary contains 100 immutable artifacts. `snapshot-manifest.json`
records every sanitized request and final identity, response status, media
type, byte count, retrieval time, SHA-256, relative artifact reference,
redirect chain, and available source-version metadata. The nine processed
outputs are JSON Schema-valid and are listed in `validation-summary.json`.

## Exact source identity

| Identity element | Evaluated value |
| --- | --- |
| Publisher | California Department of Social Services (CDSS) |
| Program | Community Care Licensing Division |
| ArcGIS item | `db31b0884a074cff9260facb3f2ade45` |
| Service | `CDSS_CCL_Facilities` |
| Service URL | `https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/CDSS_CCL_Facilities/FeatureServer` |
| Layer | `0`, named `Master_CCL_County_Intersect_2023` |
| Layer URL | `https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/CDSS_CCL_Facilities/FeatureServer/0` |
| Object-ID field | `ObjectId` |
| Geometry | `esriGeometryPoint` |
| Capabilities | `Query,Extract` |
| Query formats | `JSON, geoJSON, PBF` |
| Maximum record count | 1,000 |
| Advertised exports | CSV, Excel, feature collection, file geodatabase, GeoPackage, GeoJSON, KML, shapefile, and SQLite |
| Evaluated export | Catalog-advertised CSV for item `db31b0884a074cff9260facb3f2ade45`, layer `0` |

Three same-titled `lab.data.ca.gov` ArcGIS catalog records independently link
the same item, layer, and export identities. Their page hashes and catalog
modified values differ, but the candidate relationship set is identical. They
are therefore duplicate catalog representations of one ArcGIS source
candidate, not three different services. The program-specific catalog record
is a separate source family.

The layer reports ArcGIS version `12`. Its source-version metadata is:

- last edit: `1784152772803` / `2026-07-15T21:59:32.803Z`;
- schema last edit: `1784152772803` / `2026-07-15T21:59:32.803Z`;
- data last edit: `1784152657049` / `2026-07-15T21:57:37.049Z`.

These dates are metadata signals. Content change is determined from preserved
bytes and normalized rows, not from those dates.

## Governed export retrieval

Both observations followed the same sanitized chain:

1. `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/csv?layers=0`
2. `https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/CDSS_CCL_Facilities/FeatureServer/replicafilescache/CDSS_CCL_Facilities_-6873909777392143700.csv`
3. `https://stg-arcgisazurecdataprod.az.arcgis.com/exportfiles-20707-4235/CDSS_CCL_Facilities_-6873909777392143700.csv`

The final redirect carried transient query transport material. The evaluator
used it only in process for the exact authorized GET. The query was not parsed,
printed, logged, retained, reproduced, placed in exception text, or included in
evidence. A retained-file search found no query-bearing Azure URL. No further
redirect occurred.

The final response passed prohibited-content inspection and parsed as a direct,
nonempty CSV with a governed Facility ID field before retention:

| Property | Value |
| --- | --- |
| Artifact | `observation-02/export/facility-reference-export.bin` |
| Retrieval | `2026-07-19T22:41:46Z` |
| HTTP status | `200` |
| Media type | `application/octet-stream` |
| Bytes | `6,778,951` |
| Original-byte SHA-256 | `9310789f4077320e44afa2aa7ed24c6ec082f20311ab53063801ed6432788ac7` |
| CSV fields | `21` |
| CSV rows | `29,871` |
| Normalized-content SHA-256 | `965e141dbc082bf8e2cc0faaea67cc66373570c0b0b24c55d94bb790d9b60afa` |

The first observation's export has the same bytes and hashes.

## Pagination and identity integrity

The ID-only query returned 29,871 object IDs. Ordered pagination returned 29
pages of 1,000 rows, one page of 871 rows, and an empty terminal page. The
retrieved set reconciled exactly with the ID-only set:

- 29,871 rows;
- 29,871 unique `ObjectId` values;
- 29,714 unique nonblank `FAC_NBR` values;
- zero missing Facility IDs;
- zero duplicate, omitted, or unexpected object IDs;
- 129 duplicate Facility IDs covering 286 rows.

All 129 duplicate groups retain the same facility type and program within the
group. Their complete classification is:

| Classification | Groups | Evidence |
| --- | ---: | --- |
| Object-ID-only duplicate | 84 | Every compared value is identical; only `ObjectId` differs. |
| Coordinate-difference duplicate | 44 | `FAC_LATITUDE` and `FAC_LONGITUDE` differ. |
| Coordinate-and-county conflict | 1 | Coordinates and `COUNTY` differ. |

No row carries a temporal, successor, license-instance, or other field that
proves why these duplicates exist. Even the 84 value-identical groups retain
distinct ArcGIS object IDs. Phase A therefore does not call any group safely
collapsible. `ObjectId` is the source-row identity within an immutable
snapshot; `FAC_NBR` is a non-unique facility grouping key.

## Schema, domains, and field coverage

- schema fingerprint:
  `105c7c968bd33060d48899dfbf0a1855d5510c618cabe8e2cd1a1364410a97d0`;
- domain fingerprint:
  `661d51aa67306bb1fca01997e80dfc3ba2043edb88b1af117724d0f824c60dd5`.

All 19 layer fields, aliases, types, nullability, lengths, and domains are in
`schema-profile.json`. The layer exposes no coded-value domains. Directly
mapped fields and population are:

| Logical field | ArcGIS field | Populated | Missing |
| --- | --- | ---: | ---: |
| Facility number | `FAC_NBR` | 29,871 | 0 |
| Facility name | `NAME` | 29,871 | 0 |
| Facility type label | `FAC_TYPE_DESC` | 29,871 | 0 |
| Raw status | `STATUS` | 29,871 | 0 |
| Address | `RES_STREET_ADDR` | 29,871 | 0 |
| City | `RES_CITY` | 29,871 | 0 |
| State | `RES_STATE` | 29,871 | 0 |
| ZIP | `RES_ZIP_CODE` | 29,870 | 1 |
| County | `COUNTY` | 29,867 | 4 |
| Capacity | `CAPACITY` | 29,871 | 0 |
| Telephone | `FAC_PHONE_NBR` | 29,871 | 0 |
| Regional office | `FAC_DO_DESC` | 29,871 | 0 |

The ArcGIS layer does not provide governed matches for licensee,
administrator, first-license date, closed date, or source/file date. `STATUS`
and `TYPE` are integers without official coded-value domains, so Phase A does
not invent descriptive mappings for either field. `FAC_TYPE_DESC` is an
independent, directly supplied descriptive field.

### Raw value `733`

The live ArcGIS rows contain no exact raw `733` value. Across the seven retained
program datastores, the exact value occurs six times only in the ordinary
datastore `_id` field. It occurs zero times in an evaluated facility-type field,
and no official domain or dictionary maps it to a descriptive label. Raw `733`
must not be rendered as STRTP or any other facility type.

## Query-versus-export comparison

The query and CSV agree on row count, Facility ID set, missing-ID count, unique
ID count, and the complete 129-ID duplicate set. They are not semantically
equivalent at the field-value level:

- query normalized SHA-256:
  `5577b3a890e27f627921aba92e7258691d4aa96e2a29c908391b833fdcf871cb`;
- export normalized SHA-256:
  `965e141dbc082bf8e2cc0faaea67cc66373570c0b0b24c55d94bb790d9b60afa`;
- 47 Facility IDs have changed row fingerprints;
- 26 Facility IDs differ in address;
- 21 Facility IDs differ in facility name;
- neither side has a Facility ID absent from the other.

The comparison preserves duplicate row-fingerprint multisets. Duplicate
Facility IDs do not themselves cause failure when both representations contain
the same rows. The failure is the 47 field-value differences, consistent with
the query and generated export representing closely timed but not identical
source views. Production replacement cannot assume those interfaces are one
atomic snapshot.

## Retained-program comparison

All seven program datastores passed bounded pagination and reported-total
reconciliation. Together they contain 68,527 rows and 68,526 unique nonblank
Facility IDs; one 24-Hour Residential Care for Children row has a blank
Facility ID and no program source has a duplicate nonblank Facility ID.

| Measure | Count |
| --- | ---: |
| Shared Facility IDs | 27,831 |
| ArcGIS-only Facility IDs | 1,883 |
| Program-only Facility IDs | 40,695 |
| Shared share of retained program IDs | 40.6138% |

The 40,695 program-only IDs are consistent with a substantial scope and/or
current-versus-historical difference; absence from ArcGIS does not prove
closure or deletion. The 1,883 ArcGIS-only IDs likewise require reconciliation
before they can alter facility identity.

Across shared IDs, major conflicting-nonblank counts include 27,831 statuses,
27,831 regional-office values, 11,845 facility-type labels, 4,978 counties,
4,452 telephone values, 3,424 facility names, 1,980 capacities, 1,735 cities,
1,411 addresses, 170 ZIP values, and one state value. Telephone and county also
show large normalized-format differences. Licensee, administrator, first-license
date, closed date, and source/file date are missing from ArcGIS for all shared
records. Original values and bounded conflict fingerprints are preserved; no
first row or winning value is silently selected for duplicate groups.

## Two-observation content comparison

Two complete sequential observations were made inside the bounded run. Both
have combined raw SHA-256
`c663a8862799b127b593e27beb7c5c6564db4eefdc7c963132cef1d737ce652c`.
They have the same normalized query hash, schema fingerprint, domain
fingerprint, Facility ID set, and row fingerprints. No change was observed in
that short interval. This does not establish a publication cadence. Cadence
remains unresolved.

## Terms, authority, and attribution

The current ArcGIS catalog pages identify CDSS as publisher and display
`Creative Commons Attribution`. The retained legacy program catalog says `No
License Provided`. The exact license version and publisher-approved attribution
text are not supplied by the evaluated records. General CalHHS publication
governance does not establish candidate-specific operational
system-of-record, steward, maintainer, or update-owner status.

Human or legal confirmation remains required for the applicable license and
version, automated preservation and caching, redistribution, derivative
outputs, commercial use, and exact attribution. If supplementation is later
authorized, minimum provenance must include CDSS, the dataset title, exact
catalog/item/service/layer/snapshot identities, access and source-version
dates, the approved license version and link, and a transformation notice.

## Processed output hashes

| Output | Bytes | SHA-256 |
| --- | ---: | --- |
| `content-change.json` | 1,032 | `772e5e7ccab62e16aa6e47e188fb05eda25e33de67b093ac7b0f8d88acaacf78` |
| `decision.json` | 4,157 | `ee5785642f604cf14fc7b94a481ea0bf295745dfbcc7367a7cf4fba9d64e16f8` |
| `export-query-equivalence.json` | 5,902 | `5704c9851eddc2272f7f1be9d16cc0864d47de1c806e661bf4178e1d5266c56e` |
| `pagination-profile.json` | 39,373 | `ac59acf1ced1aba4d3e2dedb5eb49f140af9280babffdb5a3697b427f3c6f6a2` |
| `program-comparison.json` | 15,350 | `e788180dd0a8f893a41bd6764c2c66b962d45f668d8fc15e3fe4c36724f4f704` |
| `schema-profile.json` | 5,281 | `1334c4c77aee5942697bf6212df7de8e162981f28cefc17faf770f3ef92ea711` |
| `snapshot-manifest.json` | 79,438 | `bfd44b6a8b521f35b6670a224581b0286c57d9098384500bee0d1fb7aeb3cb35` |
| `source-inventory.json` | 38,994 | `0070cdd8ce137f6e439f0190aabf89edd25776823dbae75a38938cbb7dfc1f0a` |
| `validation-summary.json` | 1,059 | `6be071b454a0b127a923b0c57b84686eda47ee3f2756eee54711bdfbd44d9198` |

The complete 100-artifact inventory, including every individual raw byte count
and SHA-256, is the definitive `snapshot-manifest.json`; this report does not
duplicate that machine-readable manifest.

