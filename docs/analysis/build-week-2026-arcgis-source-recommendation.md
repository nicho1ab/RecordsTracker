# Build Week 2026 ArcGIS facility-source recommendation

## Primary recommendation

> **SUPPLEMENT**

Retain the seven program-specific source families as primary. The exact CDSS
ArcGIS item, service, layer, and accepted immutable snapshots may be considered
later as a bounded current-reference supplement only after separate production
authorization and the remaining authority, terms, acceptance, identity, and
operational gates are satisfied.

This is not an adoption, production activation, backfill authorization, or
finding that the ArcGIS source is a safe replacement. Phase A changes no
runtime, database, source precedence, schedule, or reviewer surface.

## Why this recommendation is responsible

`ADOPT` is not supported because:

- query and export are not semantically equivalent: 47 Facility IDs differ in
  address or facility name despite identical counts and ID sets;
- ArcGIS shares only 27,831 of 68,526 retained program Facility IDs, or
  40.6138%, leaving 40,695 program-only IDs;
- 129 Facility IDs are non-unique across 286 ArcGIS rows, and no evidence
  authorizes collapsing them;
- ArcGIS lacks licensee, administrator, first-license, closed, and source/file
  dates;
- raw `STATUS` and `TYPE` values have no coded-value domains;
- candidate-specific system-of-record and maintainer status remain
  unconfirmed; and
- the license version, publisher-approved attribution, and allowed-use details
  require human or legal confirmation.

`REJECT` is too broad because the exact source is publicly accessible, complete
bounded pagination passes, the catalog/item/service/layer identity is resolved,
the schema is deterministic, the direct `FAC_TYPE_DESC` label and multiple
current-reference fields are fully populated, and 1,883 Facility IDs occur only
in ArcGIS. Those facts make a governed supplement potentially useful without
making it a replacement.

`INCONCLUSIVE` is unnecessary because no access or evaluation stop gate remains:
the complete source, export, program comparison, two observations, duplicate
analysis, terms evidence, and deterministic validation are available. The
remaining failed gates define the supplement boundary rather than preventing a
decision.

The 129 duplicate groups are compatible with this recommendation only because
the supplement model preserves every row. It does not treat Facility ID as a
unique row key and does not select a first or winning row.

## Approved source identity for later consideration

Only this evaluated identity may advance to a later supplement-design task:

- publisher: California Department of Social Services;
- program: Community Care Licensing Division;
- item: `db31b0884a074cff9260facb3f2ade45`;
- service: `CDSS_CCL_Facilities`;
- layer: `0`, `Master_CCL_County_Intersect_2023`;
- service path:
  `https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/CDSS_CCL_Facilities/FeatureServer`;
- catalog-advertised CSV for the same item and layer;
- immutable snapshot manifest, schema/domain fingerprints, and validation
  contract recorded by Phase A.

The three same-titled experimental catalog pages are duplicate catalog
representations of that same item/layer/export relationship. This conclusion
does not make CDSS or CalHHS a confirmed operational system of record and does
not identify a candidate-specific maintainer.

## Source ownership and precedence

After a separate supplement authorization, an accepted ArcGIS snapshot may
supply only these current-reference supplement values:

- `NAME` as facility name;
- `FAC_TYPE_DESC` as the direct descriptive facility-type label;
- `RES_STREET_ADDR`, `RES_CITY`, `RES_STATE`, and `RES_ZIP_CODE`;
- `COUNTY`;
- `CAPACITY`;
- `FAC_PHONE_NBR`;
- `FAC_DO_DESC` as regional-office text; and
- source latitude and longitude as separately identified source coordinates.

`FAC_NBR` may be used to group and compare source rows, but it must not uniquely
own canonical facility identity. ArcGIS must not own or derive:

- a unique facility row key;
- descriptive status from raw `STATUS`;
- a facility-type label from raw `TYPE` or raw `733`;
- licensee or administrator;
- first-license, closed, effective, or source/file dates;
- historical complaint-report facts;
- reviewer-created state; or
- a winning value for a conflicting nonblank program field.

Retained program snapshots remain primary. An ArcGIS value may fill an empty
approved current-reference supplement field only after the whole candidate
snapshot passes validation. It may not silently overwrite a conflicting
nonblank program value. Any later exception requires an explicit field- and
program-specific governance decision with field-level provenance.

## Stable identity and PostgreSQL implications

Within one ArcGIS snapshot, use the immutable snapshot identity plus `ObjectId`
as the source-row key. Use `FAC_NBR` only as a non-unique facility grouping and
matching value. A later PostgreSQL design must therefore not impose a unique
constraint on ArcGIS `FAC_NBR` or use it alone as an upsert key.

The 84 object-ID-only groups, 44 coordinate-difference groups, and one
coordinate-and-county-conflict group all remain separate source rows. No
evaluated temporal, license-instance, or successor attribute distinguishes
their meanings. Backfill must remain blocked until #482 defines a versioned
facility identity projection, row grouping, conflict retention, and field-level
provenance capable of representing all rows without loss.

## Blank, conflict, disappearance, and history rules

1. Blank, null, absent, invalid, and unavailable remain distinct. An ArcGIS
   blank never erases a retained nonblank value.
2. Conflicting nonblank values retain both originals, exact source snapshot,
   retrieval/source dates, normalized comparison values, and conflict status.
3. Duplicate groups retain every row and object ID. No first-row selection is
   allowed.
4. A missing Facility ID or ObjectId in a later accepted snapshot does not mean
   closure or deletion. Preserve the last accepted row and create a
   reconciliation state.
5. ArcGIS values are current-reference supplement context with effective date
   unknown unless the source supplies one. Program and complaint-report values
   retain their historical source dates and meanings.
6. Explicit source status and closure are not interchangeable. No closed date
   may be derived from raw status or disappearance.
7. The single missing ZIP and four missing counties remain missing; they are not
   inferred from geometry in this phase.

## Snapshot acceptance, prior accepted behavior, and rollback

A candidate ArcGIS snapshot is acceptable for later supplementation only when
all of these checks pass as one governed unit:

- exact catalog/item/service/layer/export identity and redirect policy;
- response privacy and prohibited-content checks;
- original-byte hashes and immutable retention;
- complete object-ID reconciliation, bounded pagination, and terminal page;
- schema and domain fingerprints;
- row, object-ID, Facility ID, duplicate, and missing-ID thresholds;
- normalized row fingerprints and documented query/export differences;
- direct field mapping and population checks;
- conflict, disappearance, and unresolved-code checks; and
- approved terms, attribution, and operational authorization.

Any failed candidate preserves the last accepted program and ArcGIS snapshots;
it does not partially apply. Rollback selects an intact prior accepted snapshot
and its manifest. It never reconstructs history from current PostgreSQL rows.

The current Phase A package is evaluation evidence, not an accepted production
snapshot.

## Cadence

Cadence is unresolved. Two sequential complete observations were byte- and
content-identical, but the interval was too short to prove update frequency.
Catalog and ArcGIS edit timestamps are not substitutes for observed content
change. Issue #478 must not schedule production refresh until repeated governed
observations justify a cadence and define overlap prevention, checkpoints,
recovery, reconciliation, and last-accepted behavior.

## Terms, authority, and attribution gates

The catalog identifies CDSS as publisher and displays `Creative Commons
Attribution`; the legacy program catalog displays `No License Provided`. No
evaluated record supplies the exact CC license version or publisher-approved
attribution. Candidate-specific system-of-record, source owner, maintainer,
steward, and update owner remain unconfirmed.

Before production supplementation, a human or legal reviewer must confirm the
applicable license/version, automated access, retention and caching,
redistribution, derivatives, commercial use, and exact attribution. Minimum
conditional attribution is CDSS, dataset title, exact catalog/item/service/
layer/snapshot identities, access and source-version dates, approved license
version/link, and transformation notice.

## Downstream issue effects

| Issue | Phase A result carried forward | Remaining gate |
| --- | --- | --- |
| Production-source follow-up | `SUPPLEMENT`; no replacement or activation. | Create a separately authorized supplement implementation only after authority, terms, acceptance, and operational rules are approved. |
| #482 | Facility ID is non-unique; snapshot plus `ObjectId` is source-row identity; every duplicate and conflict is retained. | Define unified facility identity, PostgreSQL keys, field-level provenance, conflict states, and any controlled backfill. |
| #453 | Exact source-to-claim evidence now includes source identity, field mappings, population, hashes, conflicts, and unresolved values. | Extend source-to-screen coverage only after an approved supplement is implemented and hosted evidence is available. |
| #477 | Required diagnostics include snapshot identity, query/export difference, duplicate groups, scope gaps, schema/domain drift, conflicts, failed candidates, and last accepted state. | Implement read-only monitoring and only separately authorized minimum controls; Phase A adds no mutation action. |
| #478 | Two observations show no short-interval change and do not establish cadence. | Define scheduled refresh, non-overlap, checkpoints, retry eligibility, reconciliation, recovery, and evidence after cadence is supported. |

No downstream issue is started, changed, or closed by this recommendation.

