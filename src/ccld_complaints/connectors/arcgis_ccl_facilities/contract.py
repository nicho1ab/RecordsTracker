from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal

from ccld_complaints.statewide_facility_source_evaluation import canonical_fingerprint

ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID: Final = "arcgis-ccl-facilities-supplement"
LIVE_QUERY_SCOPE: Final = "governed_live_query"
LIVE_QUERY_OBSERVATION_KIND: Final = "live_query"
SNAPSHOT_CONTRACT_VERSION: Final = "1.0.0"

CATALOG_URL: Final = "https://lab.data.ca.gov/dataset/community-care-licensing-facilities"
LICENSES_URL: Final = "https://lab.data.ca.gov/licenses"
ARCGIS_ITEM_ID: Final = "db31b0884a074cff9260facb3f2ade45"
ARCGIS_ITEM_URL: Final = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    "db31b0884a074cff9260facb3f2ade45"
)
ARCGIS_SERVICE_NAME: Final = "CDSS_CCL_Facilities"
ARCGIS_SERVICE_URL: Final = (
    "https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/"
    "CDSS_CCL_Facilities/FeatureServer"
)
ARCGIS_LAYER_ID: Final = 0
ARCGIS_LAYER_NAME: Final = "Master_CCL_County_Intersect_2023"
ARCGIS_LAYER_URL: Final = f"{ARCGIS_SERVICE_URL}/{ARCGIS_LAYER_ID}"
ARCGIS_QUERY_URL: Final = f"{ARCGIS_LAYER_URL}/query"
ARCGIS_PUBLISHER: Final = "California Department of Social Services"
ARCGIS_DATASET_TITLE: Final = "Community Care Licensing Facilities"
ARCGIS_LICENSE_DESIGNATION: Final = "Creative Commons Attribution"

ARCGIS_RAW_FIELDS: Final = (
    "FAC_LATITUDE",
    "FAC_LONGITUDE",
    "FAC_NBR",
    "TYPE",
    "PROGRAM_TYPE",
    "STATUS",
    "CLIENT_SERVED",
    "CAPACITY",
    "NAME",
    "RES_STREET_ADDR",
    "RES_CITY",
    "RES_STATE",
    "RES_ZIP_CODE",
    "FAC_PHONE_NBR",
    "FAC_CO_NBR",
    "COUNTY",
    "FAC_DO_DESC",
    "FAC_TYPE_DESC",
    "ObjectId",
)

ARCGIS_NORMALIZED_FIELD_SOURCES: Final[Mapping[str, str]] = {
    "object_id": "ObjectId",
    "facility_number": "FAC_NBR",
    "source_latitude_raw": "FAC_LATITUDE",
    "source_longitude_raw": "FAC_LONGITUDE",
    "raw_type_code": "TYPE",
    "program_type_source": "PROGRAM_TYPE",
    "raw_status_code": "STATUS",
    "capacity_source": "CAPACITY",
    "facility_name_source": "NAME",
    "street_address_source": "RES_STREET_ADDR",
    "city_source": "RES_CITY",
    "state_source": "RES_STATE",
    "postal_code_source": "RES_ZIP_CODE",
    "telephone_source": "FAC_PHONE_NBR",
    "county_source": "COUNTY",
    "regional_office_source": "FAC_DO_DESC",
    "facility_type_description_source": "FAC_TYPE_DESC",
}

ARCGIS_EXPECTED_FIELD_TYPES: Final[Mapping[str, tuple[str, bool]]] = {
    "FAC_LATITUDE": ("esriFieldTypeString", True),
    "FAC_LONGITUDE": ("esriFieldTypeString", True),
    "FAC_NBR": ("esriFieldTypeInteger", True),
    "TYPE": ("esriFieldTypeInteger", True),
    "PROGRAM_TYPE": ("esriFieldTypeString", True),
    "STATUS": ("esriFieldTypeInteger", True),
    "CLIENT_SERVED": ("esriFieldTypeInteger", True),
    "CAPACITY": ("esriFieldTypeInteger", True),
    "NAME": ("esriFieldTypeString", True),
    "RES_STREET_ADDR": ("esriFieldTypeString", True),
    "RES_CITY": ("esriFieldTypeString", True),
    "RES_STATE": ("esriFieldTypeString", True),
    "RES_ZIP_CODE": ("esriFieldTypeString", True),
    "FAC_PHONE_NBR": ("esriFieldTypeDouble", True),
    "FAC_CO_NBR": ("esriFieldTypeInteger", True),
    "COUNTY": ("esriFieldTypeString", True),
    "FAC_DO_DESC": ("esriFieldTypeString", True),
    "FAC_TYPE_DESC": ("esriFieldTypeString", True),
    "ObjectId": ("esriFieldTypeOID", False),
}

SemanticState = Literal["populated", "null", "blank", "absent", "unavailable", "invalid"]

_UNAVAILABLE_VALUES = frozenset({"n/a", "na", "not available", "unavailable", "unknown"})
_INTEGER_FIELDS = frozenset(
    {"ObjectId", "FAC_NBR", "TYPE", "STATUS", "CLIENT_SERVED", "CAPACITY", "FAC_CO_NBR"}
)
_NUMBER_FIELDS = frozenset({"FAC_PHONE_NBR"})


def provisional_attribution(snapshot_id: str, accessed_date: str) -> str:
    return (
        "Source: California Department of Social Services, \u201cCommunity Care Licensing "
        "Facilities,\u201d California Open Data and ArcGIS item "
        f"{ARCGIS_ITEM_ID}, service {ARCGIS_SERVICE_NAME}, layer 0 "
        f"({ARCGIS_LAYER_NAME}), snapshot {snapshot_id}, accessed {accessed_date}. "
        "RecordsTracker preserves and normalizes this material as a supplementary "
        "current-reference observation. Program-specific facility-reference sources remain "
        "primary. California Open Data identifies the dataset license as Creative Commons "
        "Attribution; the publisher does not currently specify an exact version. RecordsTracker "
        "transformations and reconciliation are not endorsed by CDSS."
    )


def live_snapshot_id(
    *,
    recorded_at: str,
    raw_payload_sha256: str,
    normalized_content_sha256: str,
    schema_fingerprint: str,
    domain_fingerprint: str,
    object_id_set_sha256: str,
    raw_response_set_sha256: str,
) -> str:
    return "arcgis-live-" + canonical_fingerprint(
        {
            "source_family_id": ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
            "observation_kind": LIVE_QUERY_OBSERVATION_KIND,
            "recorded_at": recorded_at,
            "raw_payload_sha256": raw_payload_sha256,
            "normalized_content_sha256": normalized_content_sha256,
            "schema_fingerprint": schema_fingerprint,
            "domain_fingerprint": domain_fingerprint,
            "object_id_set_sha256": object_id_set_sha256,
            "raw_response_set_sha256": raw_response_set_sha256,
        }
    )[:48]


def normalize_arcgis_source_row(
    raw_record: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    return {
        normalized_name: _semantic_value(source_name, raw_record)
        for normalized_name, source_name in ARCGIS_NORMALIZED_FIELD_SOURCES.items()
    }


def validate_arcgis_schema_fields(schema_fields: Sequence[object]) -> list[str]:
    rejections: list[str] = []
    names = [
        str(field.get("name", "")) if isinstance(field, Mapping) else ""
        for field in schema_fields
    ]
    if tuple(names) != ARCGIS_RAW_FIELDS:
        rejections.append("schema field order or allowlist differs from the approved 19 fields")
    for index, field in enumerate(schema_fields, start=1):
        if not isinstance(field, Mapping):
            rejections.append(f"schema field {index} is not an object")
            continue
        if set(field) != {"name", "type", "nullable", "domain"}:
            rejections.append(f"schema field {index} has an unauthorized metadata shape")
        field_name = field.get("name")
        expected = ARCGIS_EXPECTED_FIELD_TYPES.get(str(field_name))
        if expected is not None and (field.get("type"), field.get("nullable")) != expected:
            rejections.append(
                f"schema field {field_name} type or nullability differs from approved metadata"
            )
        if field.get("domain") is not None:
            rejections.append(f"schema field {field_name or index} adds an unapproved domain")
    return rejections


def _semantic_value(source_name: str, raw_record: Mapping[str, Any]) -> Mapping[str, Any]:
    if source_name not in raw_record:
        return {"source_field": source_name, "state": "absent", "value": None}
    value = raw_record[source_name]
    state, normalized = _normalize_source_value(source_name, value)
    return {"source_field": source_name, "state": state, "value": normalized}


def _normalize_source_value(source_name: str, value: Any) -> tuple[SemanticState, Any]:
    if value is None:
        return "null", None
    if isinstance(value, str):
        normalized = " ".join(value.split())
        if not normalized:
            return "blank", ""
        if normalized.casefold() in _UNAVAILABLE_VALUES:
            return "unavailable", normalized
        if source_name in _INTEGER_FIELDS or source_name in _NUMBER_FIELDS:
            return "invalid", value
        return "populated", normalized
    if source_name in _INTEGER_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int):
            return "invalid", value
        return "populated", value
    if source_name in _NUMBER_FIELDS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "invalid", value
        return "populated", value
    return "invalid", value
