# Issue #490 governance source qualification

## Scope and no-approval boundary

This Workstream B report qualifies the public-source identity, publisher and
system representation, terms, authority, and use constraints of the candidate
Community Care Licensing Facilities source family. It is advisory. It does not
activate a source, approve an implementation, establish a production precedence
rule, or claim legal review.

Evidence was accessed with unauthenticated read-only GET requests from
2026-07-19 02:58 UTC through 2026-07-19 03:20 UTC. Redirects were disabled. The
legacy CHHS dataset UUID redirected only to the allowlisted dataset slug; no
other redirect was followed. The eight later-approved experimental catalog and
CalHHS knowledge-base URLs all returned HTTP 200 without redirects. No browser,
account session, credential, private source, raw statewide snapshot, S3 object,
or data store was used.

The source candidate cannot yet be described as one verified ArcGIS-backed
statewide system. The catalog surfaces identify a statewide, program-specific
CSV resource family published under the California Department of Social
Services (CDSS) and Community Care Licensing Division (CCLD). The experimental
California catalog also directly links two same-titled records to ArcGIS item
`db31b0884a074cff9260facb3f2ade45` and layer
`CDSS_CCL_Facilities/FeatureServer/0`. Those linked ArcGIS endpoints were not
allowlisted and were not accessed. The originally allowlisted ArcGIS surfaces
remain a separate and conflicting identity trail: two return an `Invalid URL`
page, and the other service describes licensed child care centers in the City
of Placentia in June 2023. The new link establishes a candidate lineage to
profile; it does not prove equivalence, system-of-record status, statewide row
coverage, or freshness.

## Candidate identities and relationships

| Surface | Identifier or title | Publishing or maintaining label shown | Relationship supported by the surface | Evidence status and limitation |
| --- | --- | --- | --- | --- |
| Federal catalog harvest | `Community Care Licensing Facilities`; identifier `c5cb7a9e-e99a-4f7a-b183-60bc4799a7c8` | Publisher `California Department of Social Services`; contact `Community Care Licensing Division` | Lists the CHHS resource pages and downloads as distributions | Direct for the harvest; linked for the CHHS resources. It is an aggregator and does not itself prove operational source-of-record status. |
| CHHS catalog dataset | Slug `ccl-facilities`; legacy package UUID `46ffcbdf-4874-4cc1-92c2-fb715e3ad014` | Department `California Department of Social Services`; program `Community Care Licensing Division`; hosted by the California Health and Human Services Open Data Portal | Parent of seven program CSV resources and an all-resource ZIP among eleven listed resources | Direct for catalog organization and resource linkage. No owner, maintainer, steward, or source-of-record label was found. |
| Experimental program-resource record | `community-care-licensing-facilities`; created 2025-01-11 | Organization `California Department of Social Services`; contact labeled `Data steward` with an organizational CDSS open-data address | Re-presents the seven legacy program CSVs and all-resource ZIP, using the same CHHS resource/download identities | Direct current catalog lineage and a role-labeled contact. It does not name an individual steward or prove the resource contents changed when the experimental page changed. |
| Experimental ArcGIS-backed records | `community-care-licensing-facilities1` and `community-care-licensing-facilities2`; created 2026-03-31 and 2026-06-25 | Organization `California Department of Social Services`; `Data steward` link is empty on both records | Both link to the same CalHHS Geoportal dataset, ArcGIS item `db31b0884a074cff9260facb3f2ade45`, and layer `CDSS_CCL_Facilities/FeatureServer/0`; they expose multiple download formats and separate CHHS ZIP resources | Direct catalog-to-ArcGIS candidate lineage. The duplicate same-title records, differing creation/resource dates, and unaccessed item/service leave version, supersession, and content equivalence unresolved. |
| Experimental CDSS organization index | Publisher filter `california-department-of-social-services` | `California Department of Social Services`; organization website `https://www.cdss.ca.gov/` | Lists eleven CDSS datasets and at least four same-titled Community Care Licensing Facilities entries | Direct publisher evidence and direct catalog multiplicity. The fourth dataset endpoint was not allowlisted. |
| CalHHS Open Data Handbook | Purpose, governance, and disclosure pages | General CalHHS publication governance; Knowledge Base maintained by the Center for Data Insights and Innovation | Defines general department data-steward, review, approval, quality, disclosure, rights, and publication responsibilities | Direct general governance evidence, not a dataset-specific attestation, license, approval record, or maintainer assignment. |
| All-resource ZIP | Resource `7115b4ae-4f70-463c-975f-192bd32fa826` | Inherits the CHHS dataset context | Labels itself `All resource data` and its source as the parent dataset | Direct for resource identity; bytes and contents were not accessed or profiled. |
| Program CSV resources | `7aed8063-cea7-4367-8651-c81643164ae0`, `744d1583-f9eb-45b6-b0f8-b9a9dab936a6`, `c9df723a-437f-4dcd-be37-ec73ae518bb9`, `5f5f7124-1a38-4b61-93b9-4e4be3b3b07d`, `b4d78b7f-12df-4b0c-a81a-ff40b949bc75`, `4b5cc48d-03b1-4f42-a7d1-b9816903eb2b`, and `9f5d1d00-6b24-4f44-a158-9cbe4b43f117` | Inherit the CHHS dataset context | Child Care Centers; Residential Care Facilities for the Elderly; 24-Hour Residential Care for Children; Foster Family Agencies; Home Care Organization; Family Child Care Homes; and Adult Residential Facilities | Direct for resource names, IDs, formats, and catalog dates. Coverage, row identity, and content equivalence are unavailable pending Workstream A. |
| Family Child Care Homes ArcGIS service and layer | `Family_Child_Care_Homes/FeatureServer` and layer `0` | No publisher or owner label was available | Both allowlisted URLs rendered `Invalid URL` | Direct failure observation. No dataset, item, service, or layer relationship can be qualified from these endpoints. |
| Licensed Child Care Centers ArcGIS service | `LicensedChildCareCenters/FeatureServer`; item ID `d5b2a88a29ff4bebb72a8a2e247ae669` | No owner or publisher label; layer copyright text names CDSS | Service description says licensed child care centers in the City of Placentia, June 2023; layer `ChildCareFacilities` is ID `0` | Direct. This is not evidence of the catalog dataset's statewide scope or equivalence. Item metadata was not allowlisted. |
| CCLD program page | `Community Care Licensing Division` | California Department of Social Services / CCLD | Describes CCLD's regulatory mission and links its programs and public tools | Direct for agency context; it does not call the candidate dataset a source of record or guarantee its scope or currency. |
| CCLD public application | `Community Care Facility search` / county-site disclaimer | CCLD within CDSS | Says the application provides public access to information about facilities licensed by the Division | Direct for represented public-application purpose. It calls the information an initial inquiry and disclaims accuracy, completeness, and adequacy. It does not establish equivalence to the candidate dataset. |

The catalog host, publishing department, program, resources, and ArcGIS tenant
must therefore remain separate concepts. CHHS and the experimental California
portal host catalog records; CDSS is the publisher/organization label; CCLD is
the program label; the seven CSVs and ZIP are legacy catalog resources; and two
experimental records link a different resource family to a CalHHS Geoportal
item and `CDSS_CCL_Facilities` layer. A current catalog record labels its contact
role `Data steward`, but no accessed evidence names the dataset's steward,
maintainer, operational system of record, or update owner. The CalHHS handbook
defines a `dataset` generally as the master, primary, or original authoritative
collection and assigns publication responsibilities to departmental data
stewards; it does not state that any particular CCLD catalog record is that
master collection or identify which same-titled record supersedes another.

## Official evidence register

All access times are UTC. Evidence classifications mean: **direct** when the
claim appears on the accessed surface, **linked** when one allowlisted surface
describes another, **conflicting** when official surfaces differ, and
**unavailable** when the required evidence was absent or the endpoint failed.

| Access time | Exact URL | Evidence observed | Status and limitation |
| --- | --- | --- | --- |
| 2026-07-19 02:58:07 | https://catalog.data.gov/dataset/community-care-licensing-facilities | Data.gov title; CDSS publisher; CCLD contact; public access level; issued `2024-10-01T22:56:17.302361`; modified `2025-11-06T23:26:08.051889`; catalog checked 2026-02-26; eleven distributions; generic CC-BY registry URL | Direct harvest metadata. The harvest date is not a content date, and the license field conflicts with CHHS. |
| 2026-07-19 02:58:08 | https://data.chhs.ca.gov/dataset/ccl-facilities | Department CDSS; program CCLD; geographic granularity `Statewide`; temporal coverage `Data as of 05252025`; frequency `Other`; last updated 2025-11-06; seven program CSVs plus other resources; `No License Provided`; terms limitation | Direct catalog evidence. It does not prove complete statewide coverage, row currency, or ArcGIS backing. |
| 2026-07-19 02:58:08 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014 | HTTP 302 to the allowlisted slug URL above | Direct relationship evidence; redirect was not followed automatically. |
| 2026-07-19 03:00:42 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/7115b4ae-4f70-463c-975f-192bd32fa826 | `All resource data`; ZIP; created 2025-01-10; data and metadata last updated 2025-11-06 | Direct metadata only; ZIP bytes were not accessed. |
| 2026-07-19 03:00:43 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/7aed8063-cea7-4367-8651-c81643164ae0 | `Child Care Centers`; CSV; 3.6 MiB; created 2024-10-02; data and metadata last updated 2025-05-27 | Direct metadata only. |
| 2026-07-19 03:00:43 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/744d1583-f9eb-45b6-b0f8-b9a9dab936a6 | `Residential Care Facilities for the Elderly`; CSV; 2.2 MiB; created 2024-10-01; data and metadata last updated 2025-05-27 | Direct metadata only. |
| 2026-07-19 03:00:44 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/c9df723a-437f-4dcd-be37-ec73ae518bb9 | `24-Hour Residential Care for Children`; CSV; 369.2 KiB; created 2024-10-02; data and metadata last updated 2025-05-27 | Direct metadata only. |
| 2026-07-19 03:00:44 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/5f5f7124-1a38-4b61-93b9-4e4be3b3b07d | `Foster Family Agencies`; CSV; 147.7 KiB; created 2024-10-01; data and metadata last updated 2025-05-27 | Direct metadata only. |
| 2026-07-19 03:00:44 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/b4d78b7f-12df-4b0c-a81a-ff40b949bc75 | `Home Care Organization`; CSV; 629.9 KiB; created 2025-01-09; data and metadata last updated 2025-05-27 | Direct metadata only. |
| 2026-07-19 03:00:45 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/4b5cc48d-03b1-4f42-a7d1-b9816903eb2b | `Family Child Care Homes`; CSV; 3.3 MiB; created 2024-10-02; data and metadata last updated 2025-05-27 | Direct metadata only. |
| 2026-07-19 03:00:45 | https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/9f5d1d00-6b24-4f44-a158-9cbe4b43f117 | `Adult Residential Facilities`; CSV; 1.8 MiB; created 2024-10-02; data and metadata last updated 2025-05-27 | Direct metadata only. |
| 2026-07-19 03:04:59 | https://data.ca.gov/api/3/action/package_show?id=ccl-facilities | JSON `Not Found` response | Direct access failure; no replacement API was accessed. |
| 2026-07-19 03:04:59 | https://data.ca.gov/api/3/action/package_show?id=46ffcbdf-4874-4cc1-92c2-fb715e3ad014 | JSON `Not Found` response | Direct access failure; no replacement API was accessed. |
| 2026-07-19 02:58:08 | https://data.ca.gov/about | State portal purpose; defines open data as public data from routine state business activities and excludes private/confidential individual data | Direct general portal context, not a dataset-specific permission, accuracy, or completeness statement. |
| 2026-07-19 02:58:08 | https://data.ca.gov/terms-of-use | HTTP 404 | Unavailable. It cannot establish applicable terms. |
| 2026-07-19 03:02:08 | https://www.cdss.ca.gov/inforesources/community-care-licensing | CCLD regulatory mission, programs, public tools, and CDSS copyright | Direct agency context; no dataset ownership, stewardship, or source-of-record statement. |
| 2026-07-19 03:02:09 | https://www.ccld.dss.ca.gov/carefacilitysearch/ | Public facility-search shell returned HTTP 200 | Direct access behavior; the returned page exposed no useful dataset metadata. |
| 2026-07-19 03:02:09 | https://www.ccld.dss.ca.gov/countysite/ | CCLD public-application disclaimer: initial inquiry only; no accuracy, completeness, or adequacy guarantee | Direct disclaimer evidence. Unnecessary named-contact content was not retained or reproduced. |
| 2026-07-19 03:02:09 | https://opendefinition.org/licenses/cc-by/ | Registry describes CC BY as permitting redistribution and reuse with appropriate credit and lists multiple versions | Linked license-registry context, not publisher evidence and not proof that a particular version applies. |
| 2026-07-19 03:01:01 | https://services3.arcgis.com/42Dx6OWonqK9LoEE/ArcGIS/rest/services/Family_Child_Care_Homes/FeatureServer | HTTP 200 page containing `Invalid URL` | Direct failure; service metadata unavailable. |
| 2026-07-19 03:01:02 | https://services3.arcgis.com/42Dx6OWonqK9LoEE/ArcGIS/rest/services/Family_Child_Care_Homes/FeatureServer/0 | HTTP 200 page containing `Invalid URL` | Direct failure; layer metadata unavailable. |
| 2026-07-19 03:01:02 | https://services1.arcgis.com/3CyDafKD7aN8Dr8M/arcgis/rest/services/LicensedChildCareCenters/FeatureServer | City of Placentia, June 2023 service; item ID `d5b2a88a29ff4bebb72a8a2e247ae669`; layer 0; maximum record count 1000; JSON query format | Direct metadata. It is not evidence of the statewide catalog dataset. |
| 2026-07-19 03:01:02 | https://services1.arcgis.com/3CyDafKD7aN8Dr8M/arcgis/rest/services/LicensedChildCareCenters/FeatureServer/0 | `ChildCareFacilities`; point layer; CDSS copyright text; `OBJECTID`; fields for facility identity and current-reference-like attributes; data/schema edit dates in June 2023 | Direct metadata. No field domain or code-to-label mapping was shown, and row data was not queried. |
| 2026-07-19 03:19:15 | https://lab.data.ca.gov/dataset/community-care-licensing-facilities | Experimental catalog record; CDSS organization; `Data steward` contact role; Creative Commons Attribution label; created 2025-01-11; page last updated 2026-07-18; legacy resources retain May/November 2025 dates | Direct current catalog evidence. It re-presents the legacy resource family; page modification is not content change. |
| 2026-07-19 03:19:16 | https://lab.data.ca.gov/dataset/community-care-licensing-facilities1 | Experimental catalog record; CDSS organization; Creative Commons Attribution label; created 2026-03-31; ArcGIS item/download family; ArcGIS service link; three CHHS ZIP links dated 2026-06-24 | Direct catalog-to-ArcGIS lineage. Steward link is empty; linked resource and ArcGIS endpoints were not accessed. |
| 2026-07-19 03:19:16 | https://lab.data.ca.gov/dataset/community-care-licensing-facilities2 | Experimental catalog record; CDSS organization; Creative Commons Attribution label; created 2026-06-25; same ArcGIS item and service as the preceding record; one separately identified CHHS ZIP | Direct catalog-to-ArcGIS lineage. Steward link is empty; relationship to the preceding record and legacy family is unresolved. |
| 2026-07-19 03:19:16 | https://lab.data.ca.gov/organization/datasets?publisher=california-department-of-social-services | CDSS organization description; eleven datasets; at least four same-title Community Care Licensing Facilities records; publisher and format labels | Direct publisher/catalog evidence. The fourth record was outside the allowlist and was not accessed. |
| 2026-07-19 03:19:17 | https://kb.data.chhs.ca.gov/ | CalHHS Data Knowledge Base purpose and maintenance; Open Data Handbook contact and revision context | Direct handbook provenance. Center for Data Insights and Innovation maintenance applies to the Knowledge Base, not the candidate dataset. |
| 2026-07-19 03:19:18 | https://kb.data.chhs.ca.gov/odp/purpose | Open Data Handbook purpose; general definitions of dataset, data table, and publishable state data | Direct general governance. Its `dataset` definition is not a dataset-specific source-of-record declaration. |
| 2026-07-19 03:19:18 | https://kb.data.chhs.ca.gov/odp/governance | Department review/approval model; data-steward quality, currency, metadata, and data-dictionary responsibilities; legal and executive review; publication levels | Direct general process evidence. No candidate-specific approval form, level, steward, or quality attestation was accessed. |
| 2026-07-19 03:19:18 | https://kb.data.chhs.ca.gov/odp/disclosure | Privacy, disclosure, ownership-rights, additional-disclaimer, and inaccurate-data considerations | Direct general risk evidence. It cautions that published data can be inaccurate and that third-party rights may require permission/disclaimers; it is not a dataset-specific restriction or grant. |

The five project issues were also read at their exact public URLs, including the
rendered comment areas; no public comments were present at access time:

- https://github.com/nicho1ab/RecordsTracker/issues/490 — accessed 2026-07-19
  02:58:05 UTC; defines the evaluation and says the candidate is unprofiled and
  unapproved.
- https://github.com/nicho1ab/RecordsTracker/issues/482 — accessed 2026-07-19
  02:58:05 UTC; requires a later governed facility identity projection.
- https://github.com/nicho1ab/RecordsTracker/issues/453 — accessed 2026-07-19
  02:58:06 UTC; requires later aggregate-only source-to-screen coverage.
- https://github.com/nicho1ab/RecordsTracker/issues/477 — accessed 2026-07-19
  02:58:06 UTC; defines later operator coverage and refresh visibility.
- https://github.com/nicho1ab/RecordsTracker/issues/478 — accessed 2026-07-19
  02:58:07 UTC; defines later scheduled validation, retention, and recovery.

## Terms, license, attribution, and access

The permitted-use gate is unresolved:

- The CHHS dataset page directly says `No License Provided` and says use is
  subject to CHHS Terms of Use and file-specific copyright/proprietary notices.
  Its actual `Terms of Use` link resolves in the page to
  `https://data.chhs.ca.gov/pages/terms`, which was not allowlisted and was not
  accessed.
- The allowlisted `https://data.ca.gov/terms-of-use` returned 404 and therefore
  supplies no terms.
- Data.gov's harvested metadata separately supplies the generic license value
  `http://www.opendefinition.org/licenses/cc-by`. The allowlisted HTTPS registry
  page explains the attribution condition but lists several CC BY versions. The
  publisher did not identify a version or attribution statement on the accessed
  CHHS page.
- The three current experimental California catalog records directly display
  `License: Creative Commons Attribution` alongside CDSS as the organization.
  That is stronger publisher-catalog evidence than the federal harvest, but the
  catalog's `/licenses` explanation and version-specific license text were not
  allowlisted. The current label therefore does not erase or silently reconcile
  the legacy direct-publisher `No License Provided` record.
- The CHHS page also rendered Office of the Patient Advocate terms language.
  Nothing accessed ties that program-specific language to the CCLD dataset, so
  it is conflicting or unscoped page content rather than an applicable rule.
- The CDSS program page links separate Conditions of Use, notice, and privacy
  pages that were not allowlisted. The CCLD public application supplies a strong
  no-warranty/no-completeness disclaimer, but that is not a license grant for
  the dataset.

Absence of an observed prohibition is not permission. Redistribution, caching,
preservation, derivative works, automated access, rate limits, commercial use,
and required attribution cannot be approved from this record. Controlled raw
preservation, minimized fixtures, hashes, profiling, and aggregate reports may
be technically consistent with the project, but their legal and terms
compatibility requires review of the applicable publisher terms and notices.

If human review confirms that Creative Commons Attribution governs the selected
record and resource, any later use must preserve at least the displayed dataset
title, CDSS publisher, exact catalog/resource URL, access and source-version
dates, the exact approved license name/version/link, and an indication of any
approved transformation. Attribution must travel with preserved raw snapshots,
derived datasets, exports, documentation, and public displays at the tier
approved for each output. These are conditional controls; this report does not
select a license version or declare the license conflict resolved.

## Authority, scope, currency, and historical-use limits

- **Authority:** CDSS publisher/organization and CCLD program labels are verified
  across legacy, federal-harvest, and experimental catalog surfaces. The
  experimental legacy-resource record also labels an organizational contact as
  `Data steward`; the ArcGIS-backed records have empty steward links. General
  CalHHS governance requires departmental data-steward, legal, and executive
  publication review, but no candidate-specific approval record, steward name,
  maintainer, source-of-record attestation, or authoritative-use statement was
  accessed. Repository inventory wording is not evidence and is reserved for
  later integration.
- **Scope:** The CHHS catalog directly labels geographic granularity as
  `Statewide`, but organizes the legacy downloads into named programs. The
  experimental ArcGIS-backed records use statewide-looking CDSS/CCLD labels and
  multiple geospatial formats, but the linked layer was not accessed and its row
  extent was not profiled. Neither trail establishes that every CCLD program,
  licensed facility, inactive facility, or historical facility is included.
- **Currency:** `Data as of 05252025`, resource update dates, dataset modification
  dates, experimental page dates, catalog harvest checks, and ArcGIS edit dates
  are distinct metadata. The experimental pages all say last updated 2026-07-18,
  while their listed files carry May/November 2025, March 2026, June 24, or June
  25 dates. None proves current row content. The Placentia ArcGIS service's June
  2023 dates cannot qualify the candidate's statewide currency.
- **Completeness:** The public application expressly disclaims completeness and
  adequacy. No accessed catalog statement gives a completeness guarantee.
- **Identity:** The experimental pages link two records to one ArcGIS item and
  layer while the publisher index lists at least four same-title records. That
  supports a candidate lineage and simultaneously creates a catalog-identity
  and supersession question. Facility/license number uniqueness, stable
  normalization, leading-zero behavior, duplicates, and change history require
  Workstream A.
- **Current versus historical use:** Catalog fields appear suitable for
  evaluation as current-reference attributes, while complaint-report values are
  historically source-reported context. No accessed surface supplies effective-
  date rules that would permit the catalog to rewrite complaint history.
- **Inactive, closed, and disappeared rows:** A `Closed_Date` field appears on
  the Placentia layer, but no accessed evidence defines catalog status values or
  what later omission means. Missing can represent closure, scope change,
  temporary omission, identifier change, validation failure, or deletion; none
  may be selected without evidence.
- **Complaint history:** The candidate facility resources do not establish
  complaint coverage or complaint-history completeness.

## Facility type and code `733`

Code `733` remains an unexplained raw value. The allowlisted legacy and
experimental CHHS/California catalog metadata does not publish a code/domain
relationship. The accessible Placentia layer exposes `Facility_Type` as a
nullable string, shows no type-ID field value or coded domain, and supplies no
`733` mapping. The Family Child Care Homes ArcGIS layer metadata was unavailable,
and the newly linked `CDSS_CCL_Facilities` layer was not allowlisted or accessed.
No validated Workstream A code/label inventory exists.

There is therefore no evidence-supported mapping from `733` to STRTP or any
other label, no proof that it is a facility-type code, and no basis for a
renderer dictionary. A later decision requires an official field domain or code
list plus stable multi-record and cross-version technical evidence.

## Public data, privacy, preservation, and no-secret findings

The catalog marks access as public, and the California Open Data page describes
the portal's open-data scope as excluding private/confidential individual data.
The CalHHS handbook further requires publication review for privacy, security,
confidentiality, intellectual-property rights, and mosaic-effect risk, and warns
that publicly released data can still be inaccurate. That supports cautious
public-source handling, not unrestricted reuse or a dataset-specific quality
attestation. Public facility data can still be sensitive; only necessary
aggregate, identifier, and fingerprint evidence should enter reports and
fixtures. No source narrative, person-level contact list, credential, cookie,
private header, private URL, secret, signed query, or personal path was retained.
No raw statewide bytes or S3 object were downloaded.

Any later preservation must keep original bytes, access metadata, source URL,
hash, and version linkage; minimize fixtures; and keep generated/raw outputs in
approved ignored locations. These are project safeguards, not findings that the
publisher permits every preservation or redistribution use.

## Proposed endpoints requiring separate approval

The accessed pages identified material URLs outside the allowlist. They were
recorded but not accessed:

- Publisher terms and privacy:
  `https://data.chhs.ca.gov/pages/terms`,
  `https://data.chhs.ca.gov/pages/privacy`,
  `https://data.chhs.ca.gov/about`,
  `https://lab.data.ca.gov/licenses`,
  `https://www.ca.gov/use/`,
  `https://www.ca.gov/privacy-policy/`,
  `https://www.cdss.ca.gov/Conditions-of-Use`,
  `https://www.cdss.ca.gov/Notice-on-Collection`, and
  `https://www.cdss.ca.gov/Privacy-Policy`.
- Publisher homepage variant embedded in catalog metadata:
  `https://cdss.ca.gov/inforesources/community-care-licensing`; related official
  program links:
  `https://www.cdss.ca.gov/inforesources/cdss-programs/community-care-licensing/ccld-data`
  and
  `https://www.cdss.ca.gov/inforesources/community-care-licensing/facility-search-welcome`.
- License metadata and version text:
  `http://www.opendefinition.org/licenses/cc-by`,
  `http://creativecommons.org/licenses/by/4.0/legalcode`,
  `http://creativecommons.org/licenses/by/3.0/legalcode`,
  `http://creativecommons.org/licenses/by/2.5/legalcode`,
  `http://creativecommons.org/licenses/by/2.0/legalcode`, and
  `http://creativecommons.org/licenses/by/1.0/legalcode`.
- Catalog metadata and API help:
  `https://data.chhs.ca.gov/metadata_download/ccl-facilities` and
  `https://data.ca.gov/api/3/action/help_show?name=package_show`.
- Additional same-title catalog record identified by the CDSS publisher index:
  `https://lab.data.ca.gov/dataset/community-care-licensing-facilities3`.
- Current Geoportal and ArcGIS lineage identified by both experimental
  ArcGIS-backed records:
  `https://gis.data.chhs.ca.gov/datasets/CDSS::community-care-licensing-facilities`
  and
  `https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/CDSS_CCL_Facilities/FeatureServer/0`.
- ArcGIS item downloads for item `db31b0884a074cff9260facb3f2ade45`:
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/csv?layers=0`,
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/shapefile?layers=0`,
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/geojson?layers=0`,
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/kml?layers=0`,
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/filegdb?layers=0`,
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/featureCollection?layers=0`,
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/excel?layers=0`,
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/geoPackage?layers=0`, and
  `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/sqlite?layers=0`.
- Additional CHHS ZIP resources linked by the experimental ArcGIS-backed
  records:
  `https://data.chhs.ca.gov/dataset/3c2fc34a-8517-4938-b3ee-992af04cd6b7/resource/fe582a07-4581-4b88-8e7a-3219556c940b/download/community-care-licensing-facilities-3dwuwehp.zip`,
  `https://data.chhs.ca.gov/dataset/3c2fc34a-8517-4938-b3ee-992af04cd6b7/resource/d7612a66-3de0-4471-bc4f-4af8a3372b06/download/community-care-licensing-facilities-dum7_hoc.zip`,
  `https://data.chhs.ca.gov/dataset/3c2fc34a-8517-4938-b3ee-992af04cd6b7/resource/fd220144-b75d-4be5-928b-7366319a5810/download/community-care-licensing-facilities-6h3sxzph.zip`, and
  `https://data.chhs.ca.gov/dataset/0082f535-a36c-4c9f-b31b-85eca86408ec/resource/e8a5ece0-0cb9-4901-9b2c-92020fbd37a6/download/0082f535-a36c-4c9f-b31b-85eca86408ec-deleted-2r734pck.zip`.
- Workstream A's stopped handoff identified, but did not access, the redirect
  target path
  `https://s3.amazonaws.com/og-production-open-data-chelseama-892364687672/resources/7115b4ae-4f70-463c-975f-192bd32fa826/ccl-facilities-zjho3_b6.zip`.
  Any source-generated signed query remains intentionally unrecorded and requires
  separate technical authorization; Workstream B did not access the object.
- Resource downloads:
  `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/7115b4ae-4f70-463c-975f-192bd32fa826/download/ccl-facilities-zjho3_b6.zip`,
  `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/7aed8063-cea7-4367-8651-c81643164ae0/download/tmpwya01y9s.csv`,
  `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/744d1583-f9eb-45b6-b0f8-b9a9dab936a6/download/tmpacjmwy9v.csv`,
  `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/c9df723a-437f-4dcd-be37-ec73ae518bb9/download/tmp8fw7esa8.csv`,
  `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/5f5f7124-1a38-4b61-93b9-4e4be3b3b07d/download/tmpsbmchusr.csv`,
  `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/b4d78b7f-12df-4b0c-a81a-ff40b949bc75/download/tmpbgsqj_4n.csv`,
  `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/4b5cc48d-03b1-4f42-a7d1-b9816903eb2b/download/tmpghf_prqt.csv`, and
  `https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/resource/9f5d1d00-6b24-4f44-a158-9cbe4b43f117/download/tmpx8kml5z4.csv`.
  The temporary filenames are observed links, not stable endpoint evidence.
- Data dictionaries and datastore descriptions identified by Data.gov:
  `https://data.ca.gov/datastore/dictionary_download/a8615948-c56f-4dba-90f5-5f802490a221`,
  `https://data.ca.gov/datastore/dictionary_download/6b2f5818-f60d-40b5-bc2a-94f995f9f8b0`,
  `https://data.ca.gov/datastore/dictionary_download/5bac6551-4d6c-45d6-93b8-e6ded428d98e`,
  `https://data.ca.gov/api/action/datastore_search?resource_id=5bac6551-4d6c-45d6-93b8-e6ded428d98e&limit=0`,
  `https://data.ca.gov/api/action/datastore_search?resource_id=6b2f5818-f60d-40b5-bc2a-94f995f9f8b0&limit=0`,
  `https://data.ca.gov/api/action/datastore_search?resource_id=87d12c51-d57a-493c-96b7-c7251e32a620&limit=0`,
  `https://data.ca.gov/api/action/datastore_search?resource_id=88e9c2db-6594-4dec-a18b-3e23d07f77cc&limit=0`,
  `https://data.ca.gov/api/action/datastore_search?resource_id=9a779529-6412-445e-b51e-ecee943e6785&limit=0`,
  `https://data.ca.gov/api/action/datastore_search?resource_id=a8615948-c56f-4dba-90f5-5f802490a221&limit=0`, and
  `https://data.ca.gov/api/action/datastore_search?resource_id=dc24ca45-4c7d-4fdc-b793-3db8fab07699&limit=0`.
- ArcGIS metadata and operations:
  `https://services1.arcgis.com/3CyDafKD7aN8Dr8M/arcgis/rest/services/LicensedChildCareCenters/FeatureServer?f=pjson`,
  `https://services1.arcgis.com/3CyDafKD7aN8Dr8M/arcgis/rest/services/LicensedChildCareCenters/FeatureServer/0?f=pjson`,
  `https://services1.arcgis.com/3CyDafKD7aN8Dr8M/arcgis/rest/services/LicensedChildCareCenters/FeatureServer/0/query`,
  `http://www.arcgis.com/apps/mapviewer/index.html?url=https://services1.arcgis.com/3CyDafKD7aN8Dr8M/ArcGIS/rest/services/LicensedChildCareCenters/FeatureServer&source=sd`,
  `http://www.arcgis.com/apps/mapviewer/index.html?url=https://services1.arcgis.com/3CyDafKD7aN8Dr8M/ArcGIS/rest/services/LicensedChildCareCenters/FeatureServer/0&source=sd`,
  `http://resources.arcgis.com/en/help/arcgis-rest-api/`, and item metadata for
  `d5b2a88a29ff4bebb72a8a2e247ae669`. The accessed page did not provide an item
  metadata URL, so an exact item endpoint must be approved rather than guessed.

## Unresolved human, legal, and governance review

1. Publisher or named data-steward confirmation of dataset owner, maintainer,
   update responsibility, represented operational system, which same-title
   catalog record is current, and which ArcGIS item/service supersedes the
   invalid and geographically limited services originally supplied.
2. Human/legal review of the exact applicable CHHS/CDSS terms, the CHHS-versus-
   Data.gov license conflict, license version, attribution text, automated
   access, caching, preservation, redistribution, derived output, and commercial
   use.
3. Workstream A validation of reproducible retrieval, byte and canonical hashes,
   schema and domain fingerprints, pagination/full-download equivalence, row and
   identifier coverage, duplicates, omissions, conflicts, dates, and code
   labels.
4. Later integration reconciliation of the repository's existing
   `authoritative` inventory language with this unqualified candidate status.
5. Later #482 governance approval for field ownership, precedence, conflict,
   disappearance, and historical-display behavior. No such rule is approved
   here.
