from __future__ import annotations

import csv
import io
import json
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from jsonschema import validate as jsonschema_validate

from ccld_complaints.statewide_facility_source_evaluation import (
    canonical_fingerprint,
    canonical_json_bytes,
    parse_csv_bytes,
    rows_from_arcgis_response,
    sanitize_url,
)
from ccld_complaints.utils.hash import sha256_bytes

CONTRACT_VERSION: Final = "build-week-2026.arcgis-shadow-evaluation.v1"
ARCGIS_ITEM_ID: Final = "db31b0884a074cff9260facb3f2ade45"
ARCGIS_SERVICE_PATH: Final = (
    "/XLPEppdz2H9dOiqp/arcgis/rest/services/CDSS_CCL_Facilities/FeatureServer"
)
ARCGIS_LAYER_PATH: Final = f"{ARCGIS_SERVICE_PATH}/0"
ARCGIS_QUERY_PATH: Final = f"{ARCGIS_LAYER_PATH}/query"
ARCGIS_EXPORT_CACHE_PATH_PREFIX: Final = f"{ARCGIS_SERVICE_PATH}/replicafilescache/"
ARCGIS_AZURE_EXPORT_PATH_PREFIX: Final = "/exportfiles-20707-4235/"
ARCGIS_AZURE_EXPORT_PATH: Final = (
    f"{ARCGIS_AZURE_EXPORT_PATH_PREFIX}"
    "CDSS_CCL_Facilities_-6873909777392143700.csv"
)
PROGRAM_RESOURCE_IDS: Final[tuple[str, ...]] = (
    "5bac6551-4d6c-45d6-93b8-e6ded428d98e",
    "6b2f5818-f60d-40b5-bc2a-94f995f9f8b0",
    "87d12c51-d57a-493c-96b7-c7251e32a620",
    "88e9c2db-6594-4dec-a18b-3e23d07f77cc",
    "9a779529-6412-445e-b51e-ecee943e6785",
    "a8615948-c56f-4dba-90f5-5f802490a221",
    "dc24ca45-4c7d-4fdc-b793-3db8fab07699",
)
OUTPUT_TYPES: Final = frozenset(
    {
        "source-inventory",
        "snapshot-manifest",
        "schema-profile",
        "pagination-profile",
        "export-query-equivalence",
        "program-comparison",
        "content-change",
        "decision",
        "validation-summary",
    }
)
STATUS_VALUES: Final = frozenset(
    {"pass", "fail", "warning", "blocked", "inconclusive", "not_applicable"}
)
RECOMMENDATIONS: Final = frozenset({"ADOPT", "SUPPLEMENT", "REJECT", "INCONCLUSIVE"})
SENSITIVE_QUERY_PATTERN: Final = re.compile(
    r"(?:authorization|credential|signature|token|cookie|x-amz-|api[_-]?key)",
    re.IGNORECASE,
)
PROHIBITED_RESPONSE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"x-amz-(?:credential|signature)=", re.IGNORECASE),
    re.compile(r"authorization\s*:\s*bearer\s+", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?:[A-Za-z]:\\Users\\|/Users/|/home/)[^\s\"']+"),
)

FIELD_CANDIDATES: Final[dict[str, tuple[str, ...]]] = {
    "facility_number": ("FAC_NBR", "Facility_Number", "facility_number"),
    "facility_name": ("NAME", "Facility_Name", "facility_name"),
    "facility_type": (
        "FAC_TYPE_DESC",
        "Facility_Type",
        "facility_type",
        "PROGRAM_TYPE",
    ),
    "status": ("STATUS", "Facility_Status", "facility_status"),
    "address": (
        "RES_STREET_ADDR",
        "FAC_ADDR1",
        "FAC_ADDR",
        "Facility_Address",
        "facility_address",
    ),
    "city": ("RES_CITY", "FAC_CITY", "CITY", "Facility_City", "facility_city"),
    "state": ("RES_STATE", "FAC_STATE", "STATE", "Facility_State", "facility_state"),
    "zip": ("RES_ZIP_CODE", "FAC_ZIP", "ZIP", "Facility_Zip", "facility_zip"),
    "county": ("COUNTY_NAME", "COUNTY", "County_Name", "county_name"),
    "capacity": ("CAPACITY", "Facility_Capacity", "facility_capacity"),
    "licensee": ("LICENSEE", "Licensee", "licensee"),
    "administrator": (
        "FAC_ADMIN",
        "FACILITY_ADMINISTRATOR",
        "Facility_Administrator",
        "facility_administrator",
    ),
    "telephone": (
        "FAC_PHONE_NBR",
        "FAC_PHONE",
        "FACILITY_TELEPHONE_NUMBER",
        "Facility_Telephone_Number",
        "facility_telephone_number",
    ),
    "regional_office": (
        "FAC_DO_DESC",
        "REGIONAL_OFFICE",
        "Regional_Office",
        "regional_office",
    ),
    "first_license_date": (
        "FAC_LIC_FIRST_DATE",
        "LICENSE_FIRST_DATE",
        "License_First_Date",
        "license_first_date",
    ),
    "closed_date": ("FAC_CLOSED_DATE", "CLOSED_DATE", "Closed_Date", "closed_date"),
    "source_or_file_date": ("FILE_DATE", "SOURCE_DATE", "File_Date", "file_date"),
}
DATE_FIELDS: Final = frozenset(
    {"first_license_date", "closed_date", "source_or_file_date"}
)


class EndpointPolicyError(ValueError):
    """Raised when a URL falls outside the task's exact public-source allowlist."""


class ProhibitedContentError(ValueError):
    """Raised before retaining a response that contains prohibited request material."""


@dataclass(frozen=True)
class CapturedArtifact:
    endpoint_id: str
    request_url: str
    final_url: str
    retrieved_at: str
    status: int
    media_type: str
    byte_count: int
    sha256: str
    artifact_ref: str
    redirect_chain: tuple[str, ...] = ()
    source_version_metadata: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint_id": self.endpoint_id,
            "request_url": sanitize_url(self.request_url),
            "final_url": sanitize_url(self.final_url),
            "retrieved_at": self.retrieved_at,
            "status": self.status,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "artifact_ref": self.artifact_ref.replace("\\", "/"),
            "redirect_chain": list(self.redirect_chain),
            "source_version_metadata": dict(self.source_version_metadata or {}),
        }


@dataclass(frozen=True)
class ApprovedRedirect:
    transport_url: str = dataclass_field(repr=False)
    recorded_url: str
    terminal: bool


def _normalized_path(path: str) -> str:
    return path.rstrip("/") or "/"


def _is_exact_path(path: str, expected: str) -> bool:
    return _normalized_path(path).casefold() == _normalized_path(expected).casefold()


def _is_approved_csv_export_path(path: str, query: str, prefix: str) -> bool:
    if query or not path.startswith(prefix):
        return False
    final_component = path.removeprefix(prefix)
    return bool(final_component) and "/" not in final_component and final_component.endswith(
        ".csv"
    )


def assert_approved_url(
    url: str, *, allow_opaque_azure_query: bool = False
) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise EndpointPolicyError("Only absolute HTTPS source URLs are approved.")
    if parsed.username or parsed.password or parsed.fragment:
        raise EndpointPolicyError("Credentials and fragments are not approved in source URLs.")
    host = parsed.hostname.casefold()
    path = parsed.path
    opaque_azure_transport = (
        allow_opaque_azure_query
        and host == "stg-arcgisazurecdataprod.az.arcgis.com"
        and path == ARCGIS_AZURE_EXPORT_PATH
        and bool(parsed.query)
    )
    if not opaque_azure_transport:
        for name, _value in parse_qsl(parsed.query, keep_blank_values=True):
            if SENSITIVE_QUERY_PATTERN.search(name):
                raise EndpointPolicyError("Sensitive query parameters are prohibited.")

    approved = False
    if host == "lab.data.ca.gov":
        approved = any(
            _is_exact_path(path, candidate)
            for candidate in (
                "/dataset/community-care-licensing-facilities",
                "/dataset/community-care-licensing-facilities1",
                "/dataset/community-care-licensing-facilities2",
                "/dataset/community-care-licensing-facilities3",
                "/licenses",
            )
        )
    elif host == "gis.data.chhs.ca.gov":
        approved = _is_exact_path(
            path, "/datasets/CDSS::community-care-licensing-facilities"
        ) or path.casefold().startswith(
            f"/api/download/v1/items/{ARCGIS_ITEM_ID}/".casefold()
        )
    elif host == "services.arcgis.com":
        approved = any(
            _is_exact_path(path, candidate)
            for candidate in (ARCGIS_SERVICE_PATH, ARCGIS_LAYER_PATH, ARCGIS_QUERY_PATH)
        ) or _is_approved_csv_export_path(
            path, parsed.query, ARCGIS_EXPORT_CACHE_PATH_PREFIX
        )
    elif host == "stg-arcgisazurecdataprod.az.arcgis.com":
        approved = path == ARCGIS_AZURE_EXPORT_PATH and (
            not parsed.query or opaque_azure_transport
        )
    elif host == "data.chhs.ca.gov":
        approved = _is_exact_path(path, "/dataset/ccl-facilities")
    elif host == "catalog.data.gov":
        approved = _is_exact_path(path, "/dataset/community-care-licensing-facilities")
    elif host == "kb.data.chhs.ca.gov":
        approved = any(
            _is_exact_path(path, candidate)
            for candidate in ("/", "/odp/purpose", "/odp/governance", "/odp/disclosure")
        )
    elif host == "github.com":
        approved = any(
            _is_exact_path(path, candidate)
            for candidate in (
                "/nicho1ab/RecordsTracker/issues/490",
                "/nicho1ab/RecordsTracker/issues/516",
            )
        )
    elif host == "data.ca.gov" and _is_exact_path(
        path, "/api/action/datastore_search"
    ):
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        approved = (
            query.get("resource_id") in PROGRAM_RESOURCE_IDS
            and set(query) <= {"resource_id", "limit", "offset", "sort"}
        )
    if not approved:
        raise EndpointPolicyError(
            f"Source endpoint is outside the approved host/path families: {host}{path}"
        )
    if opaque_azure_transport:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return sanitize_url(url)


def approved_redirect_target(source_url: str, location: str) -> str:
    return approve_redirect(source_url, location).recorded_url


def approve_redirect(
    source_url: str, location: str, *, source_is_terminal: bool = False
) -> ApprovedRedirect:
    if source_is_terminal:
        raise EndpointPolicyError("Further redirect from the approved export is prohibited.")
    destination = urljoin(source_url, location)
    parsed = urlsplit(destination)
    terminal = (
        parsed.hostname is not None
        and parsed.hostname.casefold() == "stg-arcgisazurecdataprod.az.arcgis.com"
        and parsed.path == ARCGIS_AZURE_EXPORT_PATH
    )
    recorded_url = assert_approved_url(
        destination, allow_opaque_azure_query=terminal
    )
    return ApprovedRedirect(
        transport_url=destination,
        recorded_url=recorded_url,
        terminal=terminal,
    )


def assert_response_safe_to_retain(body: bytes, media_type: str) -> None:
    lowered_type = media_type.casefold()
    if not any(token in lowered_type for token in ("json", "text", "xml", "html", "csv")):
        return
    text = body.decode("utf-8", errors="replace")
    for pattern in PROHIBITED_RESPONSE_PATTERNS:
        if pattern.search(text):
            raise ProhibitedContentError(
                "Source response matched a prohibited sensitive-material pattern."
            )


def write_captured_bytes(path: Path, body: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(body)
    stored = path.read_bytes()
    if stored != body:
        raise OSError("Preserved source bytes do not match the retrieved response.")
    return sha256_bytes(stored)


def schema_fingerprint(fields: Sequence[Mapping[str, Any]]) -> str:
    normalized = [
        {
            "name": str(field.get("name", "")),
            "alias": str(field.get("alias", "")),
            "type": str(field.get("type", "")),
            "nullable": field.get("nullable"),
            "length": field.get("length"),
            "domain": field.get("domain"),
        }
        for field in fields
    ]
    return canonical_fingerprint(normalized)


def domain_fingerprint(fields: Sequence[Mapping[str, Any]]) -> str:
    domains = [
        {"name": str(field.get("name", "")), "domain": field.get("domain")}
        for field in fields
    ]
    return canonical_fingerprint(domains)


def _arcgis_editing_info(payload: Mapping[str, Any]) -> dict[str, Any]:
    editing = payload.get("editingInfo")
    if not isinstance(editing, Mapping):
        return {}
    result: dict[str, Any] = {}
    for source_name, output_name in (
        ("lastEditDate", "last_edit"),
        ("schemaLastEditDate", "schema_last_edit"),
        ("dataLastEditDate", "data_last_edit"),
    ):
        value = editing.get(source_name)
        if not isinstance(value, int):
            continue
        result[f"{output_name}_epoch_milliseconds"] = value
        result[f"{output_name}_utc"] = (
            datetime.fromtimestamp(value / 1000, tz=UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    return result


def profile_layer_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_fields = payload.get("fields", [])
    if not isinstance(raw_fields, list):
        raise ValueError("ArcGIS layer metadata fields must be an array.")
    fields = [
        {
            "name": str(field.get("name", "")),
            "alias": str(field.get("alias", "")),
            "type": str(field.get("type", "")),
            "nullable": field.get("nullable"),
            "length": field.get("length"),
            "domain": field.get("domain"),
        }
        for field in raw_fields
        if isinstance(field, Mapping)
    ]
    advanced = payload.get("advancedQueryCapabilities")
    return {
        "service_item_id": str(payload.get("serviceItemId", "")),
        "layer_id": payload.get("id"),
        "name": str(payload.get("name", "")),
        "current_version": payload.get("currentVersion"),
        "type": str(payload.get("type", "")),
        "geometry_type": str(payload.get("geometryType", "")),
        "object_id_field": str(payload.get("objectIdField", "")),
        "global_id_field": str(payload.get("globalIdField", "")),
        "max_record_count": payload.get("maxRecordCount"),
        "capabilities": str(payload.get("capabilities", "")),
        "supported_query_formats": str(payload.get("supportedQueryFormats", "")),
        "supports_pagination": (
            advanced.get("supportsPagination") if isinstance(advanced, Mapping) else None
        ),
        "editing_info": _arcgis_editing_info(payload),
        "fields": fields,
        "schema_fingerprint": schema_fingerprint(fields),
        "domain_fingerprint": domain_fingerprint(fields),
    }


def _normalize_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def resolve_projection_fields(field_names: Sequence[str]) -> dict[str, str | None]:
    available = {_normalize_field_name(field): field for field in field_names}
    resolved: dict[str, str | None] = {}
    for logical, candidates in FIELD_CANDIDATES.items():
        resolved[logical] = next(
            (
                available[_normalize_field_name(candidate)]
                for candidate in candidates
                if _normalize_field_name(candidate) in available
            ),
            None,
        )
    return resolved


def _normalize_date(value: str) -> str:
    stripped = value.strip()
    if re.fullmatch(r"-?[0-9]{11,14}", stripped):
        milliseconds = int(stripped)
        return datetime.fromtimestamp(milliseconds / 1000, tz=UTC).date().isoformat()
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(stripped[:10], pattern).date().isoformat()
        except ValueError:
            continue
    return stripped


def normalize_scalar(value: Any, *, logical_field: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        normalized = str(int(value))
    else:
        normalized = re.sub(r"\s+", " ", str(value)).strip()
    if logical_field in DATE_FIELDS and normalized:
        return _normalize_date(normalized)
    return normalized


def project_row(
    row: Mapping[str, Any], field_mapping: Mapping[str, str | None]
) -> dict[str, str]:
    return {
        logical: normalize_scalar(row.get(source_field), logical_field=logical)
        if source_field is not None
        else ""
        for logical, source_field in field_mapping.items()
    }


def project_rows(
    rows: Sequence[Mapping[str, Any]], field_mapping: Mapping[str, str | None]
) -> list[dict[str, str]]:
    return [project_row(row, field_mapping) for row in rows]


def normalized_row_fingerprint(row: Mapping[str, Any], fields: Sequence[str]) -> str:
    normalized = {
        field: normalize_scalar(row.get(field), logical_field=field) for field in fields
    }
    return canonical_fingerprint(normalized)


def normalized_content_fingerprint(
    rows: Sequence[Mapping[str, Any]], *, identifier_field: str, fields: Sequence[str]
) -> str:
    values = [
        {
            "identifier": normalize_scalar(row.get(identifier_field)),
            "row_fingerprint": normalized_row_fingerprint(row, fields),
        }
        for row in rows
    ]
    values.sort(key=lambda item: (item["identifier"], item["row_fingerprint"]))
    return canonical_fingerprint(values)


def analyze_complete_pagination(
    pages: Sequence[Mapping[str, Any]],
    *,
    object_id_field: str,
    facility_id_field: str,
    expected_object_ids: Sequence[Any],
    maximum_record_count: int,
) -> dict[str, Any]:
    page_counts: list[int] = []
    object_ids: Counter[str] = Counter()
    facility_ids: Counter[str] = Counter()
    malformed_page_indexes: list[int] = []
    missing_facility_id_rows = 0
    rows: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        try:
            page_rows = rows_from_arcgis_response(page)
        except ValueError:
            malformed_page_indexes.append(index)
            continue
        page_counts.append(len(page_rows))
        rows.extend(page_rows)
        for row in page_rows:
            object_id = normalize_scalar(row.get(object_id_field))
            facility_id = normalize_scalar(row.get(facility_id_field))
            if object_id:
                object_ids[object_id] += 1
            if facility_id:
                facility_ids[facility_id] += 1
            else:
                missing_facility_id_rows += 1
    expected = {normalize_scalar(value) for value in expected_object_ids if normalize_scalar(value)}
    observed = set(object_ids)
    duplicate_object_ids = sorted(value for value, count in object_ids.items() if count > 1)
    duplicate_facility_ids = sorted(
        value for value, count in facility_ids.items() if count > 1
    )
    terminal_page_observed = bool(page_counts) and page_counts[-1] == 0
    maximum_respected = all(count <= maximum_record_count for count in page_counts)
    omitted = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    status = (
        "pass"
        if terminal_page_observed
        and maximum_respected
        and not malformed_page_indexes
        and not duplicate_object_ids
        and not omitted
        and not unexpected
        else "fail"
    )
    facility_id_status = (
        "pass"
        if not duplicate_facility_ids and missing_facility_id_rows == 0
        else "warning"
    )
    return {
        "status": status,
        "facility_id_status": facility_id_status,
        "page_counts": page_counts,
        "record_count": len(rows),
        "unique_object_id_count": len(observed),
        "unique_facility_id_count": len(facility_ids),
        "missing_facility_id_row_count": missing_facility_id_rows,
        "duplicate_object_ids": duplicate_object_ids,
        "duplicate_facility_ids": duplicate_facility_ids,
        "omitted_object_ids": omitted,
        "unexpected_object_ids": unexpected,
        "malformed_page_indexes": malformed_page_indexes,
        "terminal_page_observed": terminal_page_observed,
        "maximum_record_count": maximum_record_count,
        "maximum_record_count_respected": maximum_respected,
    }


def classify_duplicate_facility_groups(
    rows: Sequence[Mapping[str, Any]],
    *,
    facility_id_field: str,
    object_id_field: str,
) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        facility_id = normalize_scalar(row.get(facility_id_field))
        if facility_id:
            grouped[facility_id].append(row)

    classifications: Counter[str] = Counter()
    group_details: list[dict[str, Any]] = []
    coordinate_fields = {"FAC_LATITUDE", "FAC_LONGITUDE"}
    for facility_id, group_rows in sorted(grouped.items()):
        if len(group_rows) < 2:
            continue
        candidate_fields = sorted(
            {
                str(name)
                for row in group_rows
                for name in row
                if str(name) != object_id_field
            }
        )
        differing_fields = [
            name
            for name in candidate_fields
            if len({normalize_scalar(row.get(name)) for row in group_rows}) > 1
        ]
        differing_set = set(differing_fields)
        if not differing_fields:
            classification = "object-id-only duplicate"
        elif differing_set <= coordinate_fields:
            classification = "coordinate-difference duplicate"
        elif "COUNTY" in differing_set and differing_set <= coordinate_fields | {"COUNTY"}:
            classification = "coordinate-and-county-conflict duplicate"
        else:
            classification = "unresolved substantive duplicate"
        classifications[classification] += 1
        group_details.append(
            {
                "facility_id_sha256": canonical_fingerprint(facility_id),
                "row_count": len(group_rows),
                "unique_object_id_count": len(
                    {
                        normalize_scalar(row.get(object_id_field))
                        for row in group_rows
                        if normalize_scalar(row.get(object_id_field))
                    }
                ),
                "classification": classification,
                "differing_fields": differing_fields,
                "same_facility_type": all(
                    len({normalize_scalar(row.get(name)) for row in group_rows}) <= 1
                    for name in ("TYPE", "FAC_TYPE_DESC")
                ),
                "same_program": len(
                    {normalize_scalar(row.get("PROGRAM_TYPE")) for row in group_rows}
                )
                <= 1,
                "safe_to_collapse": False,
            }
        )
    return {
        "duplicate_facility_id_count": len(group_details),
        "duplicate_row_count": sum(item["row_count"] for item in group_details),
        "classification_counts": dict(sorted(classifications.items())),
        "same_facility_type_group_count": sum(
            bool(item["same_facility_type"]) for item in group_details
        ),
        "same_program_group_count": sum(bool(item["same_program"]) for item in group_details),
        "safely_collapsible_group_count": 0,
        "groups": group_details,
        "conclusion": (
            "ObjectId remains the source-row identity. Facility ID is a non-unique grouping "
            "key; no duplicate row is collapsed without governed temporal or source evidence."
        ),
    }


def parse_export_bytes(body: bytes) -> tuple[list[str], list[dict[str, str]], dict[str, Any]]:
    if zipfile.is_zipfile(io.BytesIO(body)):
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            csv_names = sorted(
                name for name in archive.namelist() if name.casefold().endswith(".csv")
            )
            if not csv_names:
                raise ValueError("Approved export archive contains no CSV member.")
            selected = max(csv_names, key=lambda name: archive.getinfo(name).file_size)
            csv_bytes = archive.read(selected)
            fields, rows, encoding, warnings = parse_csv_bytes(csv_bytes)
            return fields, rows, {
                "container": "zip",
                "selected_member": selected,
                "member_sha256": sha256_bytes(csv_bytes),
                "encoding": encoding,
                "warnings": warnings,
            }
    fields, rows, encoding, warnings = parse_csv_bytes(body)
    return fields, rows, {
        "container": "csv",
        "selected_member": "",
        "member_sha256": sha256_bytes(body),
        "encoding": encoding,
        "warnings": warnings,
    }


def validate_csv_export_response(body: bytes) -> dict[str, Any]:
    fields, rows, metadata = parse_export_bytes(body)
    if metadata["container"] != "csv":
        raise ValueError("Approved Azure export response must be a direct CSV.")
    mapping = resolve_projection_fields(fields)
    if mapping["facility_number"] is None or not rows:
        raise ValueError(
            "Approved Azure export response lacks nonempty governed CSV content."
        )
    projected = project_rows(rows, mapping)
    return {
        "container": "csv",
        "row_count": len(rows),
        "field_count": len(fields),
        "normalized_content_sha256": normalized_content_fingerprint(
            projected,
            identifier_field="facility_number",
            fields=tuple(FIELD_CANDIDATES),
        ),
    }


def compare_export_query(
    query_rows: Sequence[Mapping[str, Any]],
    export_rows: Sequence[Mapping[str, Any]],
    *,
    query_mapping: Mapping[str, str | None],
    export_mapping: Mapping[str, str | None],
) -> dict[str, Any]:
    query = project_rows(query_rows, query_mapping)
    export = project_rows(export_rows, export_mapping)
    fields = tuple(FIELD_CANDIDATES)

    def index(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            identifier = normalize_scalar(row.get("facility_number"))
            result[identifier].append(normalized_row_fingerprint(row, fields))
        for fingerprints in result.values():
            fingerprints.sort()
        return dict(result)

    query_index = index(query)
    export_index = index(export)
    query_ids = set(query_index) - {""}
    export_ids = set(export_index) - {""}
    changed = sorted(
        identifier
        for identifier in query_ids & export_ids
        if query_index[identifier] != export_index[identifier]
    )
    duplicates_query = sorted(
        identifier
        for identifier, fingerprints in query_index.items()
        if identifier and len(fingerprints) > 1
    )
    duplicates_export = sorted(
        identifier
        for identifier, fingerprints in export_index.items()
        if identifier and len(fingerprints) > 1
    )
    field_differences: Counter[str] = Counter()
    query_rows_by_id: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    export_rows_by_id: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in query:
        query_rows_by_id[row["facility_number"]].append(row)
    for row in export:
        export_rows_by_id[row["facility_number"]].append(row)
    for identifier in query_ids & export_ids:
        for logical in fields:
            query_values = sorted(
                normalize_scalar(row.get(logical), logical_field=logical)
                for row in query_rows_by_id[identifier]
            )
            export_values = sorted(
                normalize_scalar(row.get(logical), logical_field=logical)
                for row in export_rows_by_id[identifier]
            )
            if query_values != export_values:
                field_differences[logical] += 1
    equivalent = query_index == export_index and len(query) == len(export)
    return {
        "status": "pass" if equivalent else "fail",
        "verdict": "equivalent" if equivalent else "not_equivalent",
        "query_row_count": len(query),
        "export_row_count": len(export),
        "query_unique_facility_id_count": len(query_ids),
        "export_unique_facility_id_count": len(export_ids),
        "missing_facility_id_rows_query": len(query_index.get("", [])),
        "missing_facility_id_rows_export": len(export_index.get("", [])),
        "query_only_facility_ids": sorted(query_ids - export_ids),
        "export_only_facility_ids": sorted(export_ids - query_ids),
        "changed_facility_ids": changed,
        "changed_facility_id_count": len(changed),
        "field_difference_counts": dict(sorted(field_differences.items())),
        "duplicate_facility_ids_query": duplicates_query,
        "duplicate_facility_ids_export": duplicates_export,
        "logical_field_order": list(fields),
        "query_field_mapping": dict(query_mapping),
        "export_field_mapping": dict(export_mapping),
        "query_normalized_content_sha256": normalized_content_fingerprint(
            query, identifier_field="facility_number", fields=fields
        ),
        "export_normalized_content_sha256": normalized_content_fingerprint(
            export, identifier_field="facility_number", fields=fields
        ),
    }


def _comparison_value(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def classify_field_difference(logical_field: str, left: str, right: str) -> str:
    if not left or not right:
        return "missing"
    if left == right:
        return "equivalent"
    if _comparison_value(left) == _comparison_value(right):
        return "normalized-format difference"
    if logical_field in DATE_FIELDS:
        return "current-versus-historical difference"
    return "conflicting nonblank value"


def classify_field_value_sets(
    logical_field: str,
    left_rows: Sequence[Mapping[str, str]],
    right_rows: Sequence[Mapping[str, str]],
) -> str:
    left = sorted({row[logical_field] for row in left_rows if row[logical_field]})
    right = sorted({row[logical_field] for row in right_rows if row[logical_field]})
    if not left or not right:
        return "missing"
    if left == right:
        return "equivalent"
    if {_comparison_value(value) for value in left} == {
        _comparison_value(value) for value in right
    }:
        return "normalized-format difference"
    if logical_field in DATE_FIELDS:
        return "current-versus-historical difference"
    return "conflicting nonblank value"


def compare_program_sources(
    arcgis_rows: Sequence[Mapping[str, Any]],
    program_rows: Sequence[Mapping[str, Any]],
    *,
    arcgis_mapping: Mapping[str, str | None],
    program_mapping: Mapping[str, str | None],
) -> dict[str, Any]:
    arcgis = project_rows(arcgis_rows, arcgis_mapping)
    programs = project_rows(program_rows, program_mapping)

    def index(rows: Sequence[Mapping[str, str]]) -> dict[str, list[Mapping[str, str]]]:
        result: dict[str, list[Mapping[str, str]]] = defaultdict(list)
        for row in rows:
            result[row["facility_number"]].append(row)
        return dict(result)

    arcgis_index = index(arcgis)
    program_index = index(programs)
    arcgis_ids = set(arcgis_index) - {""}
    program_ids = set(program_index) - {""}
    shared = sorted(arcgis_ids & program_ids)
    categories: Counter[str] = Counter()
    field_categories: dict[str, Counter[str]] = defaultdict(Counter)
    conflict_samples: list[dict[str, str]] = []
    for identifier in shared:
        left_rows = arcgis_index[identifier]
        right_rows = program_index[identifier]
        for logical in FIELD_CANDIDATES:
            if logical == "facility_number":
                continue
            category = classify_field_value_sets(logical, left_rows, right_rows)
            categories[category] += 1
            field_categories[logical][category] += 1
            if category == "conflicting nonblank value" and len(conflict_samples) < 25:
                conflict_samples.append(
                    {
                        "facility_id_sha256": canonical_fingerprint(identifier),
                        "field": logical,
                        "arcgis_value_sha256": canonical_fingerprint(
                            sorted({row[logical] for row in left_rows if row[logical]})
                        ),
                        "program_value_sha256": canonical_fingerprint(
                            sorted({row[logical] for row in right_rows if row[logical]})
                        ),
                    }
                )
    duplicate_arcgis = sorted(
        identifier for identifier, rows in arcgis_index.items() if identifier and len(rows) > 1
    )
    duplicate_program = sorted(
        identifier for identifier, rows in program_index.items() if identifier and len(rows) > 1
    )
    type_counts_arcgis = Counter(row["facility_type"] for row in arcgis if row["facility_type"])
    type_counts_program = Counter(
        row["facility_type"] for row in programs if row["facility_type"]
    )
    return {
        "arcgis_row_count": len(arcgis),
        "program_row_count": len(programs),
        "arcgis_unique_facility_id_count": len(arcgis_ids),
        "program_unique_facility_id_count": len(program_ids),
        "shared_facility_id_count": len(shared),
        "arcgis_only_facility_id_count": len(arcgis_ids - program_ids),
        "program_only_facility_id_count": len(program_ids - arcgis_ids),
        "missing_facility_id_rows_arcgis": len(arcgis_index.get("", [])),
        "missing_facility_id_rows_program": len(program_index.get("", [])),
        "duplicate_facility_ids_arcgis": duplicate_arcgis,
        "duplicate_facility_ids_program": duplicate_program,
        "row_scope_classification": {
            "source-only": len(arcgis_ids - program_ids),
            "program-only": len(program_ids - arcgis_ids),
            "source-scope difference": len((arcgis_ids - program_ids) | (program_ids - arcgis_ids)),
        },
        "field_difference_counts": [
            {"category": category, "count": count}
            for category, count in sorted(categories.items())
        ],
        "field_difference_counts_by_field": {
            field: dict(sorted(counts.items()))
            for field, counts in sorted(field_categories.items())
        },
        "bounded_conflict_fingerprints": conflict_samples,
        "facility_type_counts_arcgis": [
            {"label": label, "count": count}
            for label, count in sorted(type_counts_arcgis.items())
        ],
        "facility_type_counts_program": [
            {"label": label, "count": count}
            for label, count in sorted(type_counts_program.items())
        ],
    }


def investigate_code_733(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[Mapping[str, Any]],
    *,
    additional_sources: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    sources: dict[str, Sequence[Mapping[str, Any]]] = {"arcgis-layer": rows}
    sources.update(additional_sources or {})
    contexts: list[dict[str, Any]] = []
    for source_id, source_rows in sorted(sources.items()):
        counts: Counter[str] = Counter()
        for row in source_rows:
            for name, value in row.items():
                if normalize_scalar(value) == "733":
                    counts[str(name)] += 1
        contexts.extend(
            {
                "source_id": source_id,
                "field": name,
                "record_count": count,
            }
            for name, count in sorted(counts.items())
        )
    domain_labels: set[str] = set()
    domain_fields: set[str] = set()
    for field in fields:
        domain = field.get("domain")
        if not isinstance(domain, Mapping):
            continue
        coded_values = domain.get("codedValues")
        if not isinstance(coded_values, list):
            continue
        for item in coded_values:
            if not isinstance(item, Mapping) or normalize_scalar(item.get("code")) != "733":
                continue
            domain_fields.add(str(field.get("name", "")))
            label = normalize_scalar(item.get("name"))
            if label:
                domain_labels.add(label)
    verified = len(domain_labels) == 1
    return {
        "status": "verified" if verified else "unresolved",
        "exact_value_contexts": contexts,
        "domain_fields": sorted(domain_fields),
        "domain_labels": sorted(domain_labels),
        "verified_descriptive_label": next(iter(domain_labels)) if verified else None,
        "conclusion": (
            "One official coded-value domain maps raw 733 to one descriptive label."
            if verified
            else (
                "The live ArcGIS layer contains no raw 733 value. Six retained-program "
                "rows contain 733 only in the datastore _id field; no official "
                "facility-type field, domain, or dictionary relationship proves a "
                "descriptive label."
                if contexts
                == [
                    {
                        "source_id": "retained-program-datastores",
                        "field": "_id",
                        "record_count": 6,
                    }
                ]
                else (
                    "No unique official source domain relationship proves a descriptive "
                    "label for raw 733."
                )
            )
        ),
    }


def compare_observations(
    previous_rows: Sequence[Mapping[str, Any]],
    current_rows: Sequence[Mapping[str, Any]],
    *,
    fields: Sequence[str],
    previous_raw_sha256: str,
    current_raw_sha256: str,
    previous_schema_fingerprint: str,
    current_schema_fingerprint: str,
    previous_domain_fingerprint: str,
    current_domain_fingerprint: str,
) -> dict[str, Any]:
    previous_ids = {
        normalize_scalar(row.get("facility_number"))
        for row in previous_rows
        if normalize_scalar(row.get("facility_number"))
    }
    current_ids = {
        normalize_scalar(row.get("facility_number"))
        for row in current_rows
        if normalize_scalar(row.get("facility_number"))
    }
    previous_content = normalized_content_fingerprint(
        previous_rows, identifier_field="facility_number", fields=fields
    )
    current_content = normalized_content_fingerprint(
        current_rows, identifier_field="facility_number", fields=fields
    )
    return {
        "raw_bytes_changed": previous_raw_sha256 != current_raw_sha256,
        "normalized_content_changed": previous_content != current_content,
        "schema_changed": previous_schema_fingerprint != current_schema_fingerprint,
        "domain_changed": previous_domain_fingerprint != current_domain_fingerprint,
        "facility_id_set_changed": previous_ids != current_ids,
        "added_facility_id_count": len(current_ids - previous_ids),
        "missing_facility_id_count": len(previous_ids - current_ids),
        "previous_normalized_content_sha256": previous_content,
        "current_normalized_content_sha256": current_content,
        "observation_conclusion": (
            "No normalized content change was observed during this bounded interval; "
            "this does not establish an update cadence."
            if previous_content == current_content
            else "A normalized content difference was observed during the bounded interval."
        ),
        "cadence_status": "unresolved",
    }


def choose_recommendation(gates: Mapping[str, Any]) -> str:
    if not bool(gates.get("source_access")) or not bool(gates.get("complete_pagination")):
        return "INCONCLUSIVE"
    if bool(gates.get("terms_prohibit_use")) or bool(gates.get("critical_integrity_failure")):
        return "REJECT"
    adopt_gates = (
        "source_identity",
        "export_query_equivalence",
        "schema_and_domain_stability",
        "facility_id_integrity",
        "facility_id_coverage_fit",
        "authority_confirmed",
        "terms_confirmed",
        "rollback_suitable",
    )
    if all(bool(gates.get(name)) for name in adopt_gates):
        return "ADOPT"
    return "SUPPLEMENT"


def decision_payload(
    *,
    recommendation: str,
    source_identity: Mapping[str, Any],
    gates: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    if recommendation not in RECOMMENDATIONS:
        raise ValueError("Recommendation must be ADOPT, SUPPLEMENT, REJECT, or INCONCLUSIVE.")
    if recommendation == "SUPPLEMENT":
        field_ownership = {
            "may_supply_after_separate_supplement_authorization": [
                "facility_name",
                "direct FAC_TYPE_DESC facility-type label",
                "address",
                "city",
                "state",
                "zip",
                "county",
                "capacity",
                "telephone",
                "regional_office",
                "source coordinates",
            ],
            "may_match_but_not_uniquely_own": ["facility_number"],
            "must_not_own": [
                "canonical facility identity",
                "descriptive status without an official code mapping",
                "licensee",
                "administrator",
                "first license date",
                "closed date",
                "source or file date",
                "historical complaint-report identity or facts",
                "reviewer-created state",
                "an unverified descriptive label for raw 733",
            ],
        }
        precedence = (
            "Retained program snapshots remain primary. After separate authorization, an "
            "accepted ArcGIS snapshot may fill an empty current-reference supplement field "
            "but never silently overwrite a conflicting nonblank program value."
        )
    else:
        field_ownership = {
            "may_own_after_separate_cutover": list(FIELD_CANDIDATES),
            "must_not_own": [
                "historical complaint-report identity or facts",
                "reviewer-created state",
                "an unverified descriptive label for raw 733",
            ],
        }
        precedence = (
            "No production precedence changes in Phase A; any later cutover requires "
            "separate authorization and retained complaint-report history."
        )
    return output_envelope(
        "decision",
        {
            "recommendation": recommendation,
            "source_identity": dict(source_identity),
            "gates": dict(gates),
            "field_ownership": field_ownership,
            "precedence": precedence,
            "blank_handling": (
                "Blank, null, absent, invalid, and unavailable remain distinct; an ArcGIS "
                "blank never erases a retained program value."
            ),
            "conflict_preservation": (
                "Conflicting nonblank values retain both originals, source versions, dates, "
                "and status."
            ),
            "disappearance_handling": (
                "A Facility ID or ObjectId disappearance never implies closure or deletion; "
                "retain the prior accepted row and record the disappearance for reconciliation."
            ),
            "current_vs_historical": (
                "ArcGIS is current-reference supplement context only; retained program and "
                "complaint-report values preserve their historical source dates and meanings."
            ),
            "snapshot_validation": (
                "Validate identity, schema/domain fingerprints, complete pagination, Facility IDs, "
                "normalized content, and export/query equivalence before acceptance."
            ),
            "prior_accepted_behavior": (
                "A failed candidate preserves the last accepted source and all immutable evidence."
            ),
            "rollback": (
                "Select a preserved prior accepted snapshot; never reconstruct history from "
                "current rows."
            ),
            "cadence_status": "unresolved",
        },
        observed_at=observed_at,
        status="pass" if recommendation in {"ADOPT", "SUPPLEMENT", "REJECT"} else "inconclusive",
    )


def output_envelope(
    output_type: str,
    data: Mapping[str, Any],
    *,
    observed_at: str,
    status: str = "pass",
    warnings: Sequence[str] = (),
) -> dict[str, Any]:
    if output_type not in OUTPUT_TYPES:
        raise ValueError(f"Unsupported output type: {output_type}")
    if status not in STATUS_VALUES:
        raise ValueError(f"Unsupported output status: {status}")
    return {
        "contract_version": CONTRACT_VERSION,
        "output_type": output_type,
        "observed_at": observed_at,
        "status": status,
        "warnings": list(warnings),
        "data": dict(data),
    }


def load_schema(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Evaluation schema must be a JSON object.")
    return cast(dict[str, Any], parsed)


def validate_output(payload: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    jsonschema_validate(dict(payload), dict(schema))


def write_output_package(
    destination: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    schema: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if destination.exists():
        raise FileExistsError(f"Evaluation output already exists: {destination}")
    staging = destination.with_name(f".{destination.name}.staging")
    if staging.exists():
        raise FileExistsError(f"Evaluation staging path already exists: {staging}")
    for name, payload in payloads.items():
        if Path(name).name != name or not name.endswith(".json"):
            raise ValueError("Evaluation output names must be plain JSON filenames.")
        validate_output(payload, schema)
        serialized = canonical_json_bytes(payload) + b"\n"
        assert_response_safe_to_retain(serialized, "application/json")
    staging.mkdir(parents=True)
    deliverables: list[dict[str, Any]] = []
    try:
        for name, payload in sorted(payloads.items()):
            serialized = canonical_json_bytes(payload) + b"\n"
            path = staging / name
            with path.open("xb") as output:
                output.write(serialized)
            deliverables.append(
                {"name": name, "byte_count": len(serialized), "sha256": sha256_bytes(serialized)}
            )
        staging.replace(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return deliverables


def read_arcgis_rows(page_paths: Sequence[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in page_paths:
        parsed = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(parsed, dict):
            raise ValueError("ArcGIS page must contain a JSON object.")
        rows.extend(rows_from_arcgis_response(parsed))
    return rows


def read_program_rows(page_paths: Sequence[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in page_paths:
        parsed = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(parsed, dict) or not isinstance(parsed.get("result"), Mapping):
            raise ValueError("Program datastore page is missing a result object.")
        records = cast(Mapping[str, Any], parsed["result"]).get("records")
        if not isinstance(records, list):
            raise ValueError("Program datastore page records must be an array.")
        rows.extend(dict(record) for record in records if isinstance(record, Mapping))
    return rows


def write_csv_rows(
    path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
