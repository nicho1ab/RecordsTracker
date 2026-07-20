# Issue #518 live query connector evidence

## Scope and decision boundary

This evidence covers the bounded query-only connector and controlled
nonproduction lifecycle gate authorized by Andrew's Issue #518 comment. It does
not authorize or prove production activation, cross-source precedence,
canonical reconciliation, reviewer display, backfill, scheduling, operator
mutation, deployment, QNAP/Cloudflare work, production PostgreSQL mutation, or
Hosted acceptance.

Program-specific facility-reference sources remain primary. ArcGIS remains a
separately versioned supplementary current-reference observation.

## Governed live retrieval

On 2026-07-20 the connector performed only approved unauthenticated `GET`
requests to the exact catalog, license, item, service, layer, and layer-query
identities. It followed no redirect and emitted no export, replica, cache,
Azure, generated-file, signed, or opaque request. Original responses and the
complete source-record payload are retained only in the Git-ignored directory:

`data/raw/source-profiling/issue-518-live-query/20260720T215435Z/`

The tracked evidence intentionally contains no facility rows.

| Evidence | Verified value |
|---|---:|
| Snapshot ID | `arcgis-live-90001e1fc700d91e2a39317e6495b431bc2572c043403acc` |
| Manifest SHA-256 | `67e6d6aafc25ed675cb4d16839c3182e6b99527ddfddf5b01fd183a6e8004e24` |
| Original-response set SHA-256 | `ad1463c7be1a00b228f55f9810ff0cfc9c64c3e2efa7939cf2e25f68940a1677` |
| Lifecycle source-record payload SHA-256 | `f01eadccb8a70792f12cefeef15340d1730db53255e75ba0bc3c4a2443976541` |
| Normalized-content SHA-256 | `3a60190995ac2382cd557a46884f3c2057792366b4ed03ff90aa3fb5a031f746` |
| Schema fingerprint | `e934a338d78e7ffb77bab673682f78566b678c9fe3a503d36acb5deb0b99613e` |
| Domain fingerprint | `661d51aa67306bb1fca01997e80dfc3ba2043edb88b1af117724d0f824c60dd5` |
| ObjectId-set SHA-256 | `fc5b9ad47b097c31ee9ab3dbc4e686f8ca69616cd41baf89b8162cf247567c45` |
| Original response artifacts | 37 |
| Nonempty pages at 1,000 rows | 30 |
| Empty terminal page offset | 30,000 |
| Returned rows | 29,871 |
| Unique ObjectIds | 29,871 |
| Unique nonblank facility numbers | 29,714 |
| Excess rows in duplicate facility-number groups | 157 |

The returned ObjectId set exactly matched the ID-only response. Page rows were
strictly increasing by `ObjectId`; no ObjectId was duplicated or omitted. The
empty page at offset 30,000 completed pagination. The query returned no raw
`TYPE=733` row in this observation; fictional regressions still prove that a
future raw `733` is preserved without a label.

## Schema correction found during live validation

The connector's first controlled run stopped before any row query because six
synthetic PR #545 type assumptions did not match the official layer metadata.
The retained official metadata establishes `FAC_LATITUDE` and `FAC_LONGITUDE`
as strings; `FAC_NBR`, `CLIENT_SERVED`, and `FAC_CO_NBR` as integers; and
`FAC_PHONE_NBR` as a double. The shared source-specific contract and wholly
fictional fixtures were corrected to those observed source types. No assertion
was weakened: the connector still rejects any type, nullability, field-order,
field-set, or domain drift from that exact boundary.

## Controlled lifecycle evidence

The live manifest was staged into a disposable PostgreSQL 16 container bound
only to loopback. Tests created a random temporary schema, retained a prior
accepted fictional snapshot, inserted all 29,871 live source rows with
snapshot-plus-`ObjectId` identity, validated and accepted the candidate,
promoted its complete pointer, and rolled back to the exact prior snapshot.
The live snapshot remained accepted history after rollback. An unrelated
reviewer-state sentinel remained byte-for-byte unchanged. The temporary schema
was dropped by the test fixture.

The focused PostgreSQL module result was `3 passed`. Mocked connector and
lifecycle regressions additionally prove candidate rejection, partial evidence
retention without manifest emission, redirect and request-policy refusal,
schema/domain drift refusal, duplicate/omitted/reordered row refusal,
nonproduction-scope enforcement, raw-only fields, semantic states, and
provisional-attribution preservation.

## Attribution retained

Every live manifest stores Andrew's provisional attribution, exact catalog URL,
access date, publisher, item/service/layer identities, license designation and
unknown version, retrieval metadata, hashes, transformations, and provenance.
This records a product-owner risk decision for public-interest use; it is not a
legal conclusion and does not claim that a license version was established.
