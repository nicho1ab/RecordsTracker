# Issue #490 statewide facility source evaluation completion report

## Final governed outcome

> **inconclusive; retain existing program-specific sources and keep the statewide candidate inactive**

Issue #490 is complete as an evaluation, not as a source-adoption or production
implementation decision. The evaluated statewide source is not approved,
adopted, or activated as a production source. The seven existing program
datastores remain the validated current program-specific facility-source family
for this evaluation and existing governed behavior remains unchanged.

This report reconciles the completed
[technical source profile](issue-490-technical-source-profile.md),
[governance source qualification](issue-490-governance-source-qualification.md),
and [governance recommendation](issue-490-governance-recommendation.md) under the
[evaluation plan](../planning/issue-490-statewide-facility-source-evaluation-plan.md)
and [parallel ownership contract](../planning/issue-490-parallel-work-ownership.md).
It does not replace either workstream report or broaden their evidence.

## Decision boundary

The completed evidence supports only these decisions:

- Retain the existing seven program-specific datastores as the current validated
  facility-source family for this evaluation. This is not a claim that they are
  complete, current for every facility, or the operational system of record.
- Keep every evaluated statewide candidate inactive.
- Do not select a statewide source, source-precedence model, refresh cadence,
  facility-type mapping, or production access path from the current evidence.
- Require a separate governed decision after the blockers and evidence gates in
  this report are resolved.

No production connector, importer, backfill, UI mapping, schedule, database,
deployment, Cloudflare, or QNAP change is authorized by Issue #490.

## Technical evidence

### Existing program-specific source family

Workstream A retrieved, preserved, and profiled all seven program datastores:

- Child Care Centers;
- Residential Care Facilities for the Elderly;
- 24-Hour Residential Care for Children;
- Foster Family Agencies;
- Home Care Organization;
- Family Child Care Homes; and
- Adult Residential Facilities.

The controlled snapshot contains **68,527 program-source rows** and 68,526
nonblank unique facility identifiers. One 24-Hour Residential Care for Children
row has no facility identifier. No program datastore has a duplicate nonblank
facility identifier in the evaluated snapshot. The seven resources share an
18-field facility-reference shape, with preserved source-specific differences
in date-field metadata.

These figures describe the bounded program-source snapshot that was successfully
profiled. They do **not** establish statewide completeness, current statewide
facility coverage, source-of-record status, or content freshness.

The program sources provide descriptive facility-type values. The evaluated
24-hour source includes 594 rows labeled `SHORT TERM RESIDENTIAL THERAPEUTIC
PROGRAM` and 3 rows labeled `STRTP - CHILDRENS CRISIS RESIDENTIAL`. Those labels
do not establish a numeric facility-type mapping for code `733`.

### Statewide candidate access and identity

The statewide candidate remains technically inconclusive for these reasons:

- The legacy Community Care Licensing Facilities ZIP followed its approved
  redirect to the approved S3 object path, then returned a sanitized HTTP `403`
  response. It did not provide a valid statewide snapshot.
- The catalog identifies the current statewide ArcGIS layer
  `CDSS_CCL_Facilities/FeatureServer/0` and GIS export endpoints, but that service
  and a corresponding stable CSV or ZIP export were not jointly profiled.
- Because that pair was not profiled, statewide row count, schema, facility-ID
  coverage, pagination, full-download/query equivalence, facility-type domains,
  conflicts, and repeated-retrieval content changes remain unmeasured.
- Multiple same-titled California catalog candidates exist. Their predecessor,
  successor, duplicate, or equivalent relationship remains unresolved.
- Two originally evaluated Family Child Care Homes ArcGIS identities returned
  an application-level `Invalid URL` result.

The successfully profiled Licensed Child Care Centers ArcGIS layer contains
**15 City of Placentia records**. Its maximum-size, smaller-page, object-ID, and
GeoJSON query results reconciled for those 15 records. It is not a statewide
comparison source and is not evidence that the catalog-linked statewide
candidate is complete, equivalent, or current.

### Code `733`

Code `733` remains unresolved. The value appeared only in ordinary datastore
`_id` contexts in the approved technical evidence and appeared zero times in
the evaluated facility-type fields. No evaluated source metadata or official
domain mapped `733` to STRTP or any other descriptive facility type.

The evidence does not establish that `733` is a facility-type code. No renderer
dictionary, canonical mapping, backfill rule, or reviewer-facing label is
approved.

## Governance evidence

### Publisher, program, and source authority

The accessed official catalog evidence identifies the **California Department
of Social Services (CDSS)** as publisher or organization and **Community Care
Licensing Division (CCLD)** as the program label. CHHS and California catalog
surfaces host or aggregate records; those hosting relationships do not by
themselves establish source authority.

Candidate-specific operational system-of-record status, source owner, named
steward, maintainer, update owner, and supersession relationship remain
unresolved. A general catalog role labeled `Data steward` and general CalHHS
publication governance are not candidate-specific attestations.

### Terms, license, and attribution

Current and legacy license evidence conflicts:

- the current experimental California catalog records display `Creative
  Commons Attribution`;
- the legacy CHHS publisher page states `No License Provided`; and
- Data.gov separately reports a generic CC-BY registry value without selecting
  a license version or publisher-approved attribution statement.

The applicable publisher terms, license version, attribution text, automated
access conditions, preservation and caching rights, redistribution terms,
derivative-output conditions, and commercial-use conditions were not resolved.
This report makes no legal conclusion. Explicit publisher and human/legal
resolution is required before adoption can be reconsidered.

### Catalog dates are not content freshness

Catalog creation, modification, harvest, and resource dates are metadata
signals. They do not prove that facility rows, schemas, identifiers, or values
changed. The evaluated sources expose multiple such dates, including legacy
resource dates and later experimental-catalog modification dates, but the
statewide service and matching export were not retrieved together and compared.

Content freshness requires preserved bytes, deterministic hashes, schema/domain
fingerprints, facility-ID sets, row fingerprints, and field-level comparisons
across controlled retrievals. No statewide freshness or refresh-cadence claim is
supported by the current catalog dates.

## Adoption blockers

All of the following are blockers, not implementation tasks authorized by this
report:

1. **Statewide access pair:** the current statewide ArcGIS service and one
   corresponding stable full export have not been jointly retrieved and
   profiled.
2. **Catalog succession:** the relationship among the multiple same-titled
   catalog records, ArcGIS item, layer, exports, and legacy resource family is
   unresolved.
3. **Stable retrieval:** the legacy ZIP returned HTTP `403`, and no replacement
   export contract has been validated for stable, bounded retrieval.
4. **Authority and maintenance:** candidate-specific system-of-record,
   steward, maintainer, update-owner, and supersession status are unresolved.
5. **Terms and license:** the current Creative Commons Attribution label and
   legacy `No License Provided` evidence conflict; applicable terms, version,
   attribution, and allowed-use conditions require explicit resolution.
6. **Coverage and equivalence:** statewide schema, row count, identifier
   integrity, duplicates, omissions, program intersections, field population,
   and download/query equivalence are unmeasured.
7. **Facility-type governance:** code `733` is not established as a
   facility-type mapping, and the current statewide type fields or domains have
   not been profiled.
8. **Freshness and change behavior:** no repeated paired statewide retrievals
   establish byte, schema, row-set, or field-value change behavior or justify a
   refresh cadence.
9. **Conflict and history rules:** the evaluated program and Placentia records
   contain differing nonblank facility values, while current-reference versus
   historical complaint-context precedence, disappearance, tombstone, failure,
   and rollback rules remain unapproved.

## Evidence required before reconsideration

Adoption or supplementation may be reconsidered only after a separately
authorized evaluation supplies all of the following:

- official confirmation of the selected catalog record, ArcGIS item/service,
  full export, publisher, source owner, maintainer, represented operational
  system, and supersession relationship;
- human/legal confirmation of the exact applicable terms, license and version,
  attribution, automated-access conditions, preservation, caching,
  redistribution, derivative-output, and commercial-use conditions;
- approved, sanitized, controlled retrievals of the current statewide ArcGIS
  service and one stable corresponding full export;
- deterministic validation of raw hashes, canonical row hashes,
  schema/domain fingerprints, pagination, stable ordering, facility identifiers,
  row counts, duplicates, omissions, and full-download/query equivalence;
- quantitative statewide-to-program comparison for scope, facility-ID coverage,
  field population, statuses, dates, conflicts, and unexplained disappearances;
- an official code/domain relationship and stable multi-record, cross-version
  evidence before any mapping for `733` is considered;
- at least two controlled statewide observations that distinguish catalog
  metadata changes from byte, schema, row-set, and value changes;
- deterministic offline fixtures and mocks that validate the selected access
  contract without live service dependencies; and
- a separately approved provenance, precedence, conflict, historical-context,
  disappearance, validation-failure, last-accepted-version, and rollback model.

Passing those evidence gates would permit a new decision; it would not by
itself activate a source or authorize production implementation.

## Follow-up mapping without starting other issues

| Issue | Issue #490 evidence to carry forward | Work that remains in the follow-up |
| --- | --- | --- |
| [#482](https://github.com/nicho1ab/RecordsTracker/issues/482) — governed facility identity projection | Existing seven-program profile; statewide candidate inactive; current-reference versus historical complaint-context distinction; conflict, blank, disappearance, and provenance constraints; `733` unresolved. | Select approved field ownership and precedence, preserve raw and historical values, resolve conflicts, and separately authorize any canonical projection, import, backfill, read-model, or reviewer-surface change. |
| [#453](https://github.com/nicho1ab/RecordsTracker/issues/453) — source-to-screen coverage | Bounded 68,527-row program profile; source/version distinctions; identifier, field-population, conflict, facility-type-label, and unresolved-code evidence; no statewide-completeness baseline. | Define deterministic aggregate baselines and release thresholds from the active accepted sources, including a regression state for an unresolved raw `733` value without assuming its label. |
| [#477](https://github.com/nicho1ab/RecordsTracker/issues/477) — operator coverage and refresh dashboard | Candidate inactive; last-accepted-source behavior; HTTP `403`, invalid endpoint, conflict, schema/hash/count, unresolved-code, and validation-state requirements. | Design and implement authorized operator visibility, persistence, permissions, bounded retry actions, and evidence presentation after source-selection governance exists. |
| [#478](https://github.com/nicho1ab/RecordsTracker/issues/478) — scheduled governed refresh | Catalog dates are not content changes; no statewide cadence is justified; validation-before-activation, prior-version retention, disappearance review, and stable access remain required. | Define and implement scheduling, locks, checkpoints, notifications, validated imports, failure retention, tombstones, rollback, and any QNAP procedure only after a source and cadence are separately approved. |

This completion report does not begin, implement, or close any of those
follow-up issues.

## No production activation or runtime change

No production connector, importer, canonical bridge, backfill, reviewer or
operator UI mapping, schedule, schema, migration, database mutation, deployment,
Cloudflare change, or QNAP operation occurred. No statewide raw snapshot was
imported into RecordsTracker. No existing facility or complaint record was
changed.

Specifically, **no QNAP, database, deployment, activation, or production import
occurred**.

The Issue #490 evaluation is ready for integration review with the statewide
candidate inactive and the adoption gate unresolved.
