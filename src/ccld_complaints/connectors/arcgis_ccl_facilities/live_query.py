from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ccld_complaints.connectors.arcgis_ccl_facilities.contract import (
    ARCGIS_DATASET_TITLE,
    ARCGIS_ITEM_ID,
    ARCGIS_ITEM_URL,
    ARCGIS_LAYER_ID,
    ARCGIS_LAYER_NAME,
    ARCGIS_LAYER_URL,
    ARCGIS_LICENSE_DESIGNATION,
    ARCGIS_PUBLISHER,
    ARCGIS_QUERY_URL,
    ARCGIS_RAW_FIELDS,
    ARCGIS_SERVICE_NAME,
    ARCGIS_SERVICE_URL,
    ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
    CATALOG_URL,
    LICENSES_URL,
    LIVE_QUERY_OBSERVATION_KIND,
    LIVE_QUERY_SCOPE,
    SNAPSHOT_CONTRACT_VERSION,
    live_snapshot_id,
    normalize_arcgis_source_row,
    provisional_attribution,
    validate_arcgis_schema_fields,
)
from ccld_complaints.statewide_facility_source_evaluation import (
    FetchTransport,
    HttpResponse,
    SnapshotArtifact,
    canonical_fingerprint,
    canonical_json_bytes,
    fetch_and_preserve,
    parse_json_bytes,
    safe_endpoint_identity,
)
from ccld_complaints.utils.hash import sha256_bytes

MAX_PAGE_SIZE: Final = 1_000
DEFAULT_TIMEOUT_SECONDS: Final = 60.0
EVIDENCE_RELATIVE_ROOT: Final = Path(
    "data/raw/source-profiling/issue-518-live-query"
)
_JSON_MEDIA_TYPES = frozenset({"application/json", "text/json", "text/plain"})
_HTML_MEDIA_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_METADATA_ENDPOINTS = frozenset({ARCGIS_ITEM_URL, ARCGIS_SERVICE_URL, ARCGIS_LAYER_URL})
_STATIC_ENDPOINTS = frozenset({CATALOG_URL, LICENSES_URL})
_SOURCE_IDENTITY = {
    "item_id": ARCGIS_ITEM_ID,
    "service_name": ARCGIS_SERVICE_NAME,
    "layer_id": ARCGIS_LAYER_ID,
    "layer_name": ARCGIS_LAYER_NAME,
    "item_url": ARCGIS_ITEM_URL,
    "service_url": ARCGIS_SERVICE_URL,
    "layer_url": ARCGIS_LAYER_URL,
    "query_url": ARCGIS_QUERY_URL,
}
_CATALOG_IDENTITY = {
    "catalog_url": CATALOG_URL,
    "licenses_url": LICENSES_URL,
    "publisher": ARCGIS_PUBLISHER,
    "dataset_title": ARCGIS_DATASET_TITLE,
    "license_designation": ARCGIS_LICENSE_DESIGNATION,
    "license_version": None,
}


class LiveArcGisConnectorError(ValueError):
    """Raised when the governed live-query connector must reject a request or candidate."""


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(  # type: ignore[no-untyped-def]
        self, request, response, code, message, headers, new_url
    ):
        raise LiveArcGisConnectorError("Redirects are prohibited for the ArcGIS connector.")


class NoRedirectGetTransport:
    """Execute one unauthenticated GET without cookies, credentials, or redirects."""

    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse:
        validate_governed_request(url)
        opener = build_opener(_RejectRedirectHandler())
        request = Request(url, method="GET")
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except HTTPError as error:
            body = error.read()
            return HttpResponse(
                request_url=url,
                final_url=error.geturl(),
                status=error.code,
                content_type=error.headers.get_content_type(),
                body=body,
            )
        with response:
            body = response.read()
            return HttpResponse(
                request_url=url,
                final_url=response.geturl(),
                status=response.status,
                content_type=response.headers.get_content_type(),
                body=body,
            )


@dataclass(frozen=True)
class LiveQueryCapture:
    evidence_directory: Path
    manifest_path: Path
    snapshot_id: str
    row_count: int
    unique_object_id_count: int
    unique_facility_number_count: int
    duplicate_facility_number_count: int
    nonempty_page_count: int
    terminal_offset: int
    raw_response_set_sha256: str
    normalized_content_sha256: str
    schema_fingerprint: str
    domain_fingerprint: str


def capture_live_arcgis_query_snapshot(
    repository_root: Path,
    *,
    page_size: int = MAX_PAGE_SIZE,
    transport: FetchTransport | None = None,
    accessed_at: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> LiveQueryCapture:
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise LiveArcGisConnectorError("page_size must be between 1 and 1000.")
    recorded_at = accessed_at or _utc_now()
    run_id = _run_id(recorded_at)
    evidence_directory = repository_root.resolve() / EVIDENCE_RELATIVE_ROOT / run_id
    evidence_directory.mkdir(parents=True, exist_ok=False)
    return _capture_snapshot(
        evidence_directory,
        page_size=page_size,
        transport=transport or NoRedirectGetTransport(),
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
    )


def validate_governed_request(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise LiveArcGisConnectorError(
            "ArcGIS requests require an approved HTTPS identity without credentials or fragments."
        )
    endpoint = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if len({name for name, _value in pairs}) != len(pairs):
        raise LiveArcGisConnectorError("Duplicate query parameters are prohibited.")
    params = dict(pairs)

    if endpoint in _STATIC_ENDPOINTS:
        if params:
            raise LiveArcGisConnectorError("Catalog and license requests do not accept parameters.")
        return
    if endpoint in _METADATA_ENDPOINTS:
        if set(params) != {"f"} or params["f"] not in {"json", "pjson"}:
            raise LiveArcGisConnectorError(
                "ArcGIS metadata requests allow only f=json or f=pjson."
            )
        return
    if endpoint != ARCGIS_QUERY_URL:
        raise LiveArcGisConnectorError("Request endpoint is outside the approved ArcGIS allowlist.")

    if params == {"where": "1=1", "returnIdsOnly": "true", "f": "json"}:
        return
    required_page_parameters = {
        "where",
        "outFields",
        "returnGeometry",
        "orderByFields",
        "resultOffset",
        "resultRecordCount",
        "f",
    }
    if set(params) != required_page_parameters:
        raise LiveArcGisConnectorError("ArcGIS page request parameters differ from the allowlist.")
    if (
        params["where"] != "1=1"
        or params["outFields"] != ",".join(ARCGIS_RAW_FIELDS)
        or params["returnGeometry"] != "false"
        or params["orderByFields"] != "ObjectId ASC"
        or params["f"] != "json"
    ):
        raise LiveArcGisConnectorError("ArcGIS page request contains an unapproved value.")
    offset = _bounded_integer(params["resultOffset"], name="resultOffset", minimum=0)
    count = _bounded_integer(
        params["resultRecordCount"],
        name="resultRecordCount",
        minimum=1,
    )
    if offset < 0 or count > MAX_PAGE_SIZE:
        raise LiveArcGisConnectorError("ArcGIS page bounds are outside the approved range.")


def _capture_snapshot(
    evidence_directory: Path,
    *,
    page_size: int,
    transport: FetchTransport,
    recorded_at: str,
    timeout_seconds: float,
) -> LiveQueryCapture:
    artifacts: list[SnapshotArtifact] = []
    catalog_artifact = _fetch_artifact(
        evidence_directory,
        endpoint_id="catalog",
        request_url=CATALOG_URL,
        artifact_name="catalog.html",
        transport=transport,
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
        expected_media_types=_HTML_MEDIA_TYPES,
    )
    artifacts.append(catalog_artifact)
    licenses_artifact = _fetch_artifact(
        evidence_directory,
        endpoint_id="licenses",
        request_url=LICENSES_URL,
        artifact_name="licenses.html",
        transport=transport,
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
        expected_media_types=_HTML_MEDIA_TYPES,
    )
    artifacts.append(licenses_artifact)

    item, item_artifact = _fetch_json_metadata(
        evidence_directory,
        endpoint_id="arcgis_item",
        endpoint=ARCGIS_ITEM_URL,
        artifact_name="arcgis-item.json",
        transport=transport,
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
    )
    service, service_artifact = _fetch_json_metadata(
        evidence_directory,
        endpoint_id="arcgis_service",
        endpoint=ARCGIS_SERVICE_URL,
        artifact_name="arcgis-service.json",
        transport=transport,
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
    )
    layer, layer_artifact = _fetch_json_metadata(
        evidence_directory,
        endpoint_id="arcgis_layer",
        endpoint=ARCGIS_LAYER_URL,
        artifact_name="arcgis-layer.json",
        transport=transport,
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
    )
    artifacts.extend((item_artifact, service_artifact, layer_artifact))
    _validate_source_identity(item=item, service=service, layer=layer)
    schema_fields = _approved_schema_fields(layer)
    schema_fingerprint = canonical_fingerprint(schema_fields)
    domain_fingerprint = canonical_fingerprint(
        [{"name": field["name"], "domain": field["domain"]} for field in schema_fields]
    )

    ids_url = _query_url((
        ("where", "1=1"),
        ("returnIdsOnly", "true"),
        ("f", "json"),
    ))
    ids_payload, ids_artifact = _fetch_json(
        evidence_directory,
        endpoint_id="object_ids",
        request_url=ids_url,
        artifact_name="object-ids.json",
        transport=transport,
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
    )
    artifacts.append(ids_artifact)
    object_ids = _object_ids(ids_payload)
    expected_id_set = set(object_ids)
    object_id_set_sha256 = canonical_fingerprint(sorted(expected_id_set))

    rows: list[dict[str, Any]] = []
    page_evidence: list[dict[str, Any]] = []
    previous_object_id: int | None = None
    offset = 0
    terminal_offset = 0
    while True:
        page_url = _query_url((
            ("where", "1=1"),
            ("outFields", ",".join(ARCGIS_RAW_FIELDS)),
            ("returnGeometry", "false"),
            ("orderByFields", "ObjectId ASC"),
            ("resultOffset", str(offset)),
            ("resultRecordCount", str(page_size)),
            ("f", "json"),
        ))
        page_name = f"page-{len(page_evidence):05d}-offset-{offset:06d}.json"
        page_payload, page_artifact = _fetch_json(
            evidence_directory,
            endpoint_id="query_page",
            request_url=page_url,
            artifact_name=page_name,
            transport=transport,
            recorded_at=recorded_at,
            timeout_seconds=timeout_seconds,
        )
        artifacts.append(page_artifact)
        page_rows = _page_rows(page_payload)
        page_ids: list[int] = []
        for row in page_rows:
            object_id = _object_id(row)
            if object_id not in expected_id_set:
                raise LiveArcGisConnectorError(
                    "ArcGIS page returned an ObjectId outside the ID-only response."
                )
            if previous_object_id is not None and object_id <= previous_object_id:
                raise LiveArcGisConnectorError(
                    "ArcGIS page rows are duplicated or not ordered by ObjectId ASC."
                )
            previous_object_id = object_id
            page_ids.append(object_id)
            rows.append(row)
            if len(rows) > len(expected_id_set):
                raise LiveArcGisConnectorError(
                    "ArcGIS page row count exceeds the reconciled ID-only boundary."
                )
        page_evidence.append(
            {
                "artifact_ref": page_artifact.artifact_ref,
                "offset": offset,
                "row_count": len(page_rows),
                "first_object_id": page_ids[0] if page_ids else None,
                "last_object_id": page_ids[-1] if page_ids else None,
                "sha256": page_artifact.sha256,
            }
        )
        if not page_rows:
            terminal_offset = offset
            break
        offset += page_size

    returned_ids = [_object_id(row) for row in rows]
    if len(returned_ids) != len(set(returned_ids)):
        raise LiveArcGisConnectorError("ArcGIS query pages contain duplicate ObjectId values.")
    returned_id_set = set(returned_ids)
    if returned_id_set != expected_id_set:
        omitted = len(expected_id_set - returned_id_set)
        unexpected = len(returned_id_set - expected_id_set)
        raise LiveArcGisConnectorError(
            "ArcGIS query pages do not reconcile with the ID-only response "
            f"(omitted={omitted}, unexpected={unexpected})."
        )

    normalized_rows = []
    facility_numbers: Counter[str] = Counter()
    warnings: list[str] = []
    for row in rows:
        normalized = normalize_arcgis_source_row(row)
        invalid_fields = sorted(
            field
            for field, value in normalized.items()
            if isinstance(value, Mapping) and value.get("state") == "invalid"
        )
        if invalid_fields:
            raise LiveArcGisConnectorError(
                "ArcGIS row contains invalid approved values: " + ", ".join(invalid_fields)
            )
        object_id = _object_id(row)
        facility_number = row.get("FAC_NBR")
        if isinstance(facility_number, str) and facility_number.strip():
            facility_numbers[" ".join(facility_number.split())] += 1
        elif isinstance(facility_number, int) and not isinstance(facility_number, bool):
            facility_numbers[str(facility_number)] += 1
        if row.get("TYPE") == 733:
            warnings.append(f"ObjectId {object_id} retains unresolved raw TYPE value 733")
        normalized_rows.append(
            {
                "source_object_id": object_id,
                "row_fingerprint": canonical_fingerprint(normalized),
            }
        )
    normalized_content_sha256 = canonical_fingerprint(normalized_rows)

    raw_payload = {"source_kind": LIVE_QUERY_SCOPE, "records": rows}
    raw_payload_bytes = canonical_json_bytes(raw_payload) + b"\n"
    raw_payload_ref = "lifecycle-source-records.json"
    _write_exclusive(evidence_directory / raw_payload_ref, raw_payload_bytes)
    raw_payload_sha256 = sha256_bytes(raw_payload_bytes)
    raw_response_set_sha256 = canonical_fingerprint(
        [
            {"artifact_ref": artifact.artifact_ref, "sha256": artifact.sha256}
            for artifact in artifacts
        ]
    )
    snapshot_id = live_snapshot_id(
        recorded_at=recorded_at,
        raw_payload_sha256=raw_payload_sha256,
        normalized_content_sha256=normalized_content_sha256,
        schema_fingerprint=schema_fingerprint,
        domain_fingerprint=domain_fingerprint,
        object_id_set_sha256=object_id_set_sha256,
        raw_response_set_sha256=raw_response_set_sha256,
    )
    duplicate_facility_number_count = sum(
        count - 1 for count in facility_numbers.values() if count > 1
    )
    manifest = {
        "contract_version": SNAPSHOT_CONTRACT_VERSION,
        "evidence_kind": LIVE_QUERY_SCOPE,
        "source_family_id": ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
        "observation_kind": LIVE_QUERY_OBSERVATION_KIND,
        "snapshot_id": snapshot_id,
        "recorded_at": recorded_at,
        "accessed_date": recorded_at[:10],
        "catalog_identity": dict(_CATALOG_IDENTITY),
        "source_identity": dict(_SOURCE_IDENTITY),
        "provisional_attribution": provisional_attribution(snapshot_id, recorded_at[:10]),
        "raw_payload_ref": raw_payload_ref,
        "raw_payload_sha256": raw_payload_sha256,
        "normalized_content_sha256": normalized_content_sha256,
        "schema_fingerprint": schema_fingerprint,
        "domain_fingerprint": domain_fingerprint,
        "schema_fields": schema_fields,
        "retrieval_artifacts": [artifact.as_dict() for artifact in artifacts],
        "raw_response_set_sha256": raw_response_set_sha256,
        "id_evidence": {
            "artifact_ref": ids_artifact.artifact_ref,
            "count": len(object_ids),
            "object_id_field": "ObjectId",
            "object_id_set_sha256": object_id_set_sha256,
            "minimum_object_id": min(object_ids) if object_ids else None,
            "maximum_object_id": max(object_ids) if object_ids else None,
        },
        "page_evidence": {
            "page_size": page_size,
            "nonempty_page_count": len(page_evidence) - 1,
            "terminal_offset": terminal_offset,
            "terminal_page_ref": page_evidence[-1]["artifact_ref"],
            "pages": page_evidence,
        },
        "validation": {
            "status": "validated",
            "row_count": len(rows),
            "unique_object_id_count": len(returned_id_set),
            "unique_facility_number_count": len(facility_numbers),
            "duplicate_facility_number_count": duplicate_facility_number_count,
            "id_reconciliation": "exact",
            "empty_terminal_page": True,
            "deterministic_object_id_order": True,
            "approved_raw_field_count": len(ARCGIS_RAW_FIELDS),
            "warnings": sorted(set(warnings)),
            "raw_733_label_invented": False,
            "canonical_or_reviewer_fields_written": False,
        },
    }
    manifest_path = evidence_directory / "snapshot-manifest.json"
    _write_exclusive(manifest_path, canonical_json_bytes(manifest) + b"\n")
    return LiveQueryCapture(
        evidence_directory=evidence_directory,
        manifest_path=manifest_path,
        snapshot_id=snapshot_id,
        row_count=len(rows),
        unique_object_id_count=len(returned_id_set),
        unique_facility_number_count=len(facility_numbers),
        duplicate_facility_number_count=duplicate_facility_number_count,
        nonempty_page_count=len(page_evidence) - 1,
        terminal_offset=terminal_offset,
        raw_response_set_sha256=raw_response_set_sha256,
        normalized_content_sha256=normalized_content_sha256,
        schema_fingerprint=schema_fingerprint,
        domain_fingerprint=domain_fingerprint,
    )


def _fetch_json_metadata(
    evidence_directory: Path,
    *,
    endpoint_id: str,
    endpoint: str,
    artifact_name: str,
    transport: FetchTransport,
    recorded_at: str,
    timeout_seconds: float,
) -> tuple[dict[str, Any], SnapshotArtifact]:
    return _fetch_json(
        evidence_directory,
        endpoint_id=endpoint_id,
        request_url=f"{endpoint}?f=json",
        artifact_name=artifact_name,
        transport=transport,
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
    )


def _fetch_json(
    evidence_directory: Path,
    *,
    endpoint_id: str,
    request_url: str,
    artifact_name: str,
    transport: FetchTransport,
    recorded_at: str,
    timeout_seconds: float,
) -> tuple[dict[str, Any], SnapshotArtifact]:
    artifact = _fetch_artifact(
        evidence_directory,
        endpoint_id=endpoint_id,
        request_url=request_url,
        artifact_name=artifact_name,
        transport=transport,
        recorded_at=recorded_at,
        timeout_seconds=timeout_seconds,
        expected_media_types=_JSON_MEDIA_TYPES,
    )
    payload = parse_json_bytes((evidence_directory / artifact_name).read_bytes())
    if "error" in payload:
        raise LiveArcGisConnectorError(f"ArcGIS {endpoint_id} response contains an error object.")
    return payload, artifact


def _fetch_artifact(
    evidence_directory: Path,
    *,
    endpoint_id: str,
    request_url: str,
    artifact_name: str,
    transport: FetchTransport,
    recorded_at: str,
    timeout_seconds: float,
    expected_media_types: frozenset[str],
) -> SnapshotArtifact:
    validate_governed_request(request_url)
    artifact = fetch_and_preserve(
        endpoint_id=endpoint_id,
        request_url=request_url,
        artifact_path=evidence_directory / artifact_name,
        artifact_ref=artifact_name,
        transport=transport,
        retrieved_at=recorded_at,
        timeout_seconds=timeout_seconds,
    )
    if artifact.status < 200 or artifact.status >= 300:
        raise LiveArcGisConnectorError(f"ArcGIS {endpoint_id} returned HTTP {artifact.status}.")
    if artifact.redirect_chain or artifact.final_endpoint != safe_endpoint_identity(request_url):
        raise LiveArcGisConnectorError(f"ArcGIS {endpoint_id} attempted a redirect.")
    if artifact.content_type.casefold() not in expected_media_types:
        raise LiveArcGisConnectorError(
            f"ArcGIS {endpoint_id} returned unapproved media type {artifact.content_type}."
        )
    if artifact.byte_count == 0:
        raise LiveArcGisConnectorError(f"ArcGIS {endpoint_id} returned an empty response.")
    return artifact


def _validate_source_identity(
    *,
    item: Mapping[str, Any],
    service: Mapping[str, Any],
    layer: Mapping[str, Any],
) -> None:
    if item.get("id") != ARCGIS_ITEM_ID:
        raise LiveArcGisConnectorError("ArcGIS item identity does not match the approval.")
    if item.get("url") != ARCGIS_SERVICE_URL:
        raise LiveArcGisConnectorError("ArcGIS item does not identify the approved service URL.")
    layers = service.get("layers")
    if not isinstance(layers, list) or not any(
        isinstance(value, Mapping)
        and value.get("id") == ARCGIS_LAYER_ID
        and value.get("name") == ARCGIS_LAYER_NAME
        for value in layers
    ):
        raise LiveArcGisConnectorError("ArcGIS service does not identify the approved layer.")
    if (
        layer.get("id") != ARCGIS_LAYER_ID
        or layer.get("name") != ARCGIS_LAYER_NAME
        or layer.get("objectIdField") != "ObjectId"
    ):
        raise LiveArcGisConnectorError("ArcGIS layer identity differs from the approval.")


def _approved_schema_fields(layer: Mapping[str, Any]) -> list[dict[str, Any]]:
    fields = layer.get("fields")
    if not isinstance(fields, list):
        raise LiveArcGisConnectorError("ArcGIS layer metadata omits its field schema.")
    approved_fields = []
    for field in fields:
        if not isinstance(field, Mapping):
            raise LiveArcGisConnectorError("ArcGIS layer field metadata is not an object.")
        approved_fields.append(
            {
                "name": field.get("name"),
                "type": field.get("type"),
                "nullable": field.get("nullable"),
                "domain": field.get("domain"),
            }
        )
    rejections = validate_arcgis_schema_fields(approved_fields)
    if rejections:
        raise LiveArcGisConnectorError("; ".join(rejections))
    return approved_fields


def _object_ids(payload: Mapping[str, Any]) -> list[int]:
    if payload.get("objectIdFieldName") != "ObjectId":
        raise LiveArcGisConnectorError("ID response identifies an unexpected ObjectId field.")
    values = payload.get("objectIds")
    if not isinstance(values, list):
        raise LiveArcGisConnectorError("ID response omits its ObjectId array.")
    object_ids = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise LiveArcGisConnectorError("ID response contains a non-integer ObjectId.")
        object_ids.append(value)
    if len(object_ids) != len(set(object_ids)):
        raise LiveArcGisConnectorError("ID response contains duplicate ObjectId values.")
    return object_ids


def _page_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    features = payload.get("features")
    if not isinstance(features, list):
        raise LiveArcGisConnectorError("ArcGIS page response omits its features array.")
    rows: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, Mapping) or set(feature) != {"attributes"}:
            raise LiveArcGisConnectorError(
                "ArcGIS page features must contain attributes only; geometry is prohibited."
            )
        attributes = feature.get("attributes")
        if not isinstance(attributes, Mapping):
            raise LiveArcGisConnectorError("ArcGIS feature attributes are not an object.")
        if set(attributes) != set(ARCGIS_RAW_FIELDS):
            raise LiveArcGisConnectorError(
                "ArcGIS feature attributes differ from the approved 19-field boundary."
            )
        rows.append(dict(attributes))
    return rows


def _object_id(row: Mapping[str, Any]) -> int:
    value = row.get("ObjectId")
    if isinstance(value, bool) or not isinstance(value, int):
        raise LiveArcGisConnectorError("ArcGIS row has no valid ObjectId identity.")
    return value


def _query_url(parameters: Sequence[tuple[str, str]]) -> str:
    url = f"{ARCGIS_QUERY_URL}?{urlencode(parameters)}"
    validate_governed_request(url)
    return url


def _bounded_integer(value: str, *, name: str, minimum: int) -> int:
    if not value.isascii() or not value.isdecimal():
        raise LiveArcGisConnectorError(f"{name} must be a base-10 integer.")
    parsed = int(value)
    if parsed < minimum:
        raise LiveArcGisConnectorError(f"{name} is below the approved minimum.")
    return parsed


def _write_exclusive(path: Path, content: bytes) -> None:
    with path.open("xb") as output:
        output.write(content)
    if path.read_bytes() != content:
        raise OSError(f"Stored evidence bytes do not match for {path.name}.")


def _run_id(recorded_at: str) -> str:
    try:
        value = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise LiveArcGisConnectorError("accessed_at must be an ISO-8601 timestamp.") from error
    if value.tzinfo is None:
        raise LiveArcGisConnectorError("accessed_at must include a timezone.")
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
