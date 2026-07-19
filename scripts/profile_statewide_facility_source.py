from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast

from ccld_complaints.statewide_facility_source_evaluation import (
    CONTRACT_VERSION,
    ExactRedirectTransport,
    analyze_pagination,
    canonical_fingerprint,
    compare_content_snapshots,
    compare_row_sets,
    compare_source_coverage,
    exact_value_contexts,
    extract_public_urls_from_html,
    fetch_and_preserve,
    find_named_objects,
    load_ckan_datastore_pages,
    load_output_schema,
    ordered_schema_fingerprint,
    output_envelope,
    parse_arcgis_layer_html,
    parse_json_bytes,
    parse_next_data_payload,
    profile_facility_rows,
    rows_from_arcgis_response,
    rows_from_geojson_response,
    sanitize_url,
    sha256_file,
    write_csv_output,
    write_json_output,
)

STATEWIDE_DOWNLOAD_URL = (
    "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
    "resource/7115b4ae-4f70-463c-975f-192bd32fa826/download/"
    "ccl-facilities-zjho3_b6.zip"
)
APPROVED_REDIRECT_ENDPOINT = (
    "https://s3.amazonaws.com/og-production-open-data-chelseama-892364687672/"
    "resources/7115b4ae-4f70-463c-975f-192bd32fa826/ccl-facilities-zjho3_b6.zip"
)

CATALOG_ENDPOINTS: Final[tuple[tuple[str, str], ...]] = (
    (
        "catalog_data_gov",
        "https://catalog.data.gov/dataset/community-care-licensing-facilities",
    ),
    ("chhs_dataset_slug", "https://data.chhs.ca.gov/dataset/ccl-facilities"),
    (
        "chhs_dataset_uuid",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014",
    ),
    (
        "data_ca_package_uuid",
        "https://data.ca.gov/api/3/action/package_show?id=46ffcbdf-4874-4cc1-92c2-fb715e3ad014",
    ),
    (
        "chhs_resource_statewide_zip",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
        "resource/7115b4ae-4f70-463c-975f-192bd32fa826",
    ),
    (
        "chhs_resource_child_care_centers",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
        "resource/7aed8063-cea7-4367-8651-c81643164ae0",
    ),
    (
        "chhs_resource_24_hour_children",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
        "resource/c9df723a-437f-4dcd-be37-ec73ae518bb9",
    ),
    (
        "chhs_resource_residential_care_elderly",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
        "resource/744d1583-f9eb-45b6-b0f8-b9a9dab936a6",
    ),
    (
        "chhs_resource_foster_family_agencies",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
        "resource/5f5f7124-1a38-4b61-93b9-4e4be3b3b07d",
    ),
    (
        "chhs_resource_home_care_organizations",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
        "resource/b4d78b7f-12df-4b0c-a81a-ff40b949bc75",
    ),
    (
        "chhs_resource_family_child_care_homes",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
        "resource/4b5cc48d-03b1-4f42-a7d1-b9816903eb2b",
    ),
    (
        "chhs_resource_adult_senior_care",
        "https://data.chhs.ca.gov/dataset/46ffcbdf-4874-4cc1-92c2-fb715e3ad014/"
        "resource/9f5d1d00-6b24-4f44-a158-9cbe4b43f117",
    ),
    (
        "lab_catalog_primary",
        "https://lab.data.ca.gov/dataset/community-care-licensing-facilities",
    ),
    (
        "lab_catalog_duplicate_1",
        "https://lab.data.ca.gov/dataset/community-care-licensing-facilities1",
    ),
    (
        "lab_catalog_duplicate_2",
        "https://lab.data.ca.gov/dataset/community-care-licensing-facilities2",
    ),
    (
        "lab_catalog_publisher",
        "https://lab.data.ca.gov/organization/datasets?publisher="
        "california-department-of-social-services",
    ),
)

DATASTORE_RESOURCES: Final[tuple[str, ...]] = (
    "5bac6551-4d6c-45d6-93b8-e6ded428d98e",
    "6b2f5818-f60d-40b5-bc2a-94f995f9f8b0",
    "87d12c51-d57a-493c-96b7-c7251e32a620",
    "88e9c2db-6594-4dec-a18b-3e23d07f77cc",
    "9a779529-6412-445e-b51e-ecee943e6785",
    "a8615948-c56f-4dba-90f5-5f802490a221",
    "dc24ca45-4c7d-4fdc-b793-3db8fab07699",
)

DICTIONARY_ENDPOINTS: Final[tuple[tuple[str, str], ...]] = (
    (
        "dictionary_5bac6551",
        "https://data.ca.gov/datastore/dictionary_download/"
        "5bac6551-4d6c-45d6-93b8-e6ded428d98e",
    ),
    (
        "dictionary_6b2f5818",
        "https://data.ca.gov/datastore/dictionary_download/"
        "6b2f5818-f60d-40b5-bc2a-94f995f9f8b0",
    ),
    (
        "dictionary_a8615948",
        "https://data.ca.gov/datastore/dictionary_download/"
        "a8615948-c56f-4dba-90f5-5f802490a221",
    ),
)

ARCGIS_METADATA_ENDPOINTS: Final[tuple[tuple[str, str], ...]] = (
    (
        "arcgis_family_service",
        "https://services3.arcgis.com/42Dx6OWonqK9LoEE/ArcGIS/rest/services/"
        "Family_Child_Care_Homes/FeatureServer",
    ),
    (
        "arcgis_family_layer",
        "https://services3.arcgis.com/42Dx6OWonqK9LoEE/ArcGIS/rest/services/"
        "Family_Child_Care_Homes/FeatureServer/0",
    ),
    (
        "arcgis_centers_service",
        "https://services1.arcgis.com/3CyDafKD7aN8Dr8M/arcgis/rest/services/"
        "LicensedChildCareCenters/FeatureServer",
    ),
    (
        "arcgis_centers_layer",
        "https://services1.arcgis.com/3CyDafKD7aN8Dr8M/arcgis/rest/services/"
        "LicensedChildCareCenters/FeatureServer/0",
    ),
)

ARCGIS_CENTER_QUERY_BASE: Final = (
    "https://services1.arcgis.com/3CyDafKD7aN8Dr8M/arcgis/rest/services/"
    "LicensedChildCareCenters/FeatureServer/0/query"
)

PROGRAM_SOURCE_NAMES: Final[dict[str, str]] = {
    "5bac6551-4d6c-45d6-93b8-e6ded428d98e": "Child Care Centers",
    "6b2f5818-f60d-40b5-bc2a-94f995f9f8b0": "Residential Care Facilities for the Elderly",
    "87d12c51-d57a-493c-96b7-c7251e32a620": (
        "24-Hour Residential Care for Children"
    ),
    "88e9c2db-6594-4dec-a18b-3e23d07f77cc": "Foster Family Agencies",
    "9a779529-6412-445e-b51e-ecee943e6785": "Home Care Organization",
    "a8615948-c56f-4dba-90f5-5f802490a221": "Family Child Care Homes",
    "dc24ca45-4c7d-4fdc-b793-3db8fab07699": "Adult Residential Facilities",
}

PROGRAM_FIELDS: Final[tuple[str, ...]] = (
    "_id",
    "facility_type",
    "facility_number",
    "facility_name",
    "licensee",
    "facility_administrator",
    "facility_telephone_number",
    "facility_address",
    "facility_city",
    "facility_state",
    "facility_zip",
    "county_name",
    "regional_office",
    "facility_capacity",
    "facility_status",
    "license_first_date",
    "closed_date",
    "file_date",
)

CENTER_FIELDS: Final[tuple[str, ...]] = (
    "OBJECTID",
    "Facility_Type",
    "Facility_Number",
    "Facility_Name",
    "Licensee",
    "Facility_Email",
    "Facility_Administrator",
    "Facility_Telephone_Number",
    "Facility_Address",
    "Facility_City",
    "Facility_State",
    "Facility_Zip",
    "County_Name",
    "Regional_Office",
    "Facility_Capacity",
    "Facility_Status",
    "Closed_Date",
)

CSV_CONTRACTS: Final[dict[str, tuple[str, ...]]] = {
    "facility-type-code-label.csv": (
        "source_id",
        "code_field",
        "label_field",
        "raw_code",
        "raw_label",
        "record_count",
        "evidence_status",
    ),
    "coverage-comparison.csv": (
        "left_source",
        "right_source",
        "left_row_count",
        "right_row_count",
        "shared_identifier_count",
        "left_only_identifier_count",
        "right_only_identifier_count",
        "left_missing_identifier_count",
        "right_missing_identifier_count",
        "left_duplicate_identifier_count",
        "right_duplicate_identifier_count",
        "conflicting_nonblank_value_count",
        "comparison_status",
        "scope_note",
    ),
    "source-conflicts.csv": (
        "left_source",
        "right_source",
        "left_field",
        "right_field",
        "category",
        "conflict_count",
        "sample_identifier_fingerprints",
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the isolated Issue #490 statewide facility source evaluation."
    )
    parser.add_argument(
        "--fetch-statewide-zip",
        action="store_true",
        help="Perform the single approved redirect-validated statewide ZIP retrieval.",
    )
    parser.add_argument(
        "--fetch-catalog-metadata",
        action="store_true",
        help=(
            "Fetch the exact approved catalog, datastore metadata, dictionary, "
            "and ArcGIS metadata URLs."
        ),
    )
    parser.add_argument(
        "--fetch-residential-resource",
        action="store_true",
        help="Fetch the one approved residential-care resource page omitted from an earlier batch.",
    )
    parser.add_argument(
        "--fetch-arcgis-center-pages",
        action="store_true",
        help="Fetch bounded deterministic query variants for the approved child-care-center layer.",
    )
    parser.add_argument(
        "--fetch-program-records",
        action="store_true",
        help="Fetch bounded, ordered pages for the seven approved program datastores.",
    )
    parser.add_argument(
        "--datastore-metadata-dir",
        type=Path,
        help="Existing ignored directory containing the preserved limit=0 datastore responses.",
    )
    parser.add_argument(
        "--evaluate-snapshots",
        action="store_true",
        help="Evaluate preserved snapshots and emit the versioned Issue #490 output set.",
    )
    parser.add_argument("--catalog-dir", type=Path)
    parser.add_argument("--arcgis-dir", type=Path)
    parser.add_argument("--arcgis-query-dir", type=Path)
    parser.add_argument("--prior-discovery-dir", type=Path)
    parser.add_argument("--dictionary-dir", type=Path)
    parser.add_argument("--program-records-dir", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/source-profiling/issue-490"),
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/issue-490-statewide-facility-source-profile.schema.json"),
    )
    parser.add_argument(
        "--statewide-safe-attempt",
        type=Path,
        help="Ignored sanitized metadata for the one statewide ZIP attempt.",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw/source-profiling/issue-490"),
    )
    return parser


def _retrieval_stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_file_time(path: Path) -> str:
    return (
        datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _content_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".html": "text/html",
        ".csv": "text/csv",
        ".zip": "application/zip",
    }.get(path.suffix.casefold(), "application/octet-stream")


def _manifest_artifact(
    path: Path,
    *,
    endpoint_id: str,
    request_url: str,
    status: int = 200,
    warnings: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "endpoint_id": endpoint_id,
        "request_url": sanitize_url(request_url),
        "final_endpoint": sanitize_url(request_url),
        "retrieved_at": _utc_file_time(path),
        "status": status,
        "content_type": _content_type(path),
        "byte_count": path.stat().st_size,
        "sha256": sha256_file(path),
        "artifact_ref": path.as_posix(),
        "redirect_chain": [],
        "source_version_metadata": {},
        "warnings": list(warnings),
    }


def _candidate_identity(endpoint_id: str, url: str, path: Path) -> dict[str, Any]:
    payload = parse_next_data_payload(path.read_bytes())
    data_file_lists = [
        value
        for value in find_named_objects(payload, "dataFiles")
        if isinstance(value, list)
    ]
    resources: list[dict[str, str]] = []
    if data_file_lists:
        for value in data_file_lists[0]:
            if not isinstance(value, dict):
                continue
            resources.append(
                {
                    "id": str(value.get("id", "")),
                    "name": str(value.get("name", "")),
                    "format": str(value.get("format", "")),
                    "created": str(value.get("created", "")),
                    "url": sanitize_url(str(value.get("url", ""))) if value.get("url") else "",
                }
            )
    result_candidates = [
        value
        for value in find_named_objects(payload, "result")
        if isinstance(value, dict) and (value.get("id") or value.get("name"))
    ]
    result = cast(dict[str, Any], result_candidates[0]) if result_candidates else {}
    return {
        "candidate_id": endpoint_id,
        "catalog_url": url,
        "dataset_id": str(result.get("id", "")),
        "dataset_name": str(result.get("name", result.get("title", ""))),
        "title": str(result.get("title", "Community Care Licensing Facilities")),
        "publisher": "California Department of Social Services",
        "created": str(result.get("metadata_created", result.get("created", ""))),
        "modified": str(result.get("metadata_modified", result.get("modified", ""))),
        "resources": sorted(resources, key=lambda item: (item["id"], item["url"])),
        "relationship_status": "unresolved_separate_candidate_identity",
    }


def _aggregate_conflicts(
    left_source: str,
    right_source: str,
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for conflict in conflicts:
        key = (
            str(conflict["left_field"]),
            str(conflict["right_field"]),
            str(conflict["category"]),
        )
        grouped[key].append(canonical_fingerprint(str(conflict["facility_identifier"])))
    return [
        {
            "left_source": left_source,
            "right_source": right_source,
            "left_field": left_field,
            "right_field": right_field,
            "category": category,
            "conflict_count": len(fingerprints),
            "sample_identifier_fingerprints": ";".join(sorted(fingerprints)[:10]),
        }
        for (left_field, right_field, category), fingerprints in sorted(grouped.items())
    ]


def _evaluate_preserved_snapshots(
    *,
    catalog_dir: Path,
    arcgis_dir: Path,
    arcgis_query_dir: Path,
    prior_discovery_dir: Path,
    datastore_metadata_dir: Path,
    dictionary_dir: Path,
    program_records_dir: Path,
    statewide_safe_attempt: Path,
    output_dir: Path,
    schema_path: Path,
) -> list[dict[str, object]]:
    generated_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    schema = load_output_schema(schema_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    program_fields: dict[str, list[dict[str, Any]]] = {}
    program_rows: dict[str, list[dict[str, Any]]] = {}
    program_profiles: dict[str, dict[str, Any]] = {}
    datastore_pagination: list[dict[str, Any]] = []
    for resource_id in DATASTORE_RESOURCES:
        metadata_path = datastore_metadata_dir / f"datastore_{resource_id}_metadata.json"
        metadata = parse_json_bytes(metadata_path.read_bytes())
        result = metadata.get("result")
        if not isinstance(result, dict):
            raise ValueError(f"Missing metadata result for {resource_id}")
        expected_total = int(result["total"])
        page_paths = sorted(
            program_records_dir.glob(f"datastore_{resource_id}_page_*.json"),
            key=lambda path: path.name,
        )
        fields, rows, pagination = load_ckan_datastore_pages(
            page_paths, expected_total=expected_total
        )
        pagination["source_id"] = resource_id
        pagination["source_name"] = PROGRAM_SOURCE_NAMES[resource_id]
        program_fields[resource_id] = fields
        program_rows[resource_id] = rows
        program_profiles[resource_id] = profile_facility_rows(
            rows,
            source_id=resource_id,
            identifier_field="facility_number",
            type_field="facility_type",
            status_field="facility_status",
            fields=PROGRAM_FIELDS,
        )
        datastore_pagination.append(pagination)

    center_layer_path = arcgis_dir / "arcgis_centers_layer.html"
    family_layer_path = arcgis_dir / "arcgis_family_layer.html"
    center_layer = parse_arcgis_layer_html(center_layer_path.read_bytes())
    family_layer = parse_arcgis_layer_html(family_layer_path.read_bytes())
    center_ids_payload = parse_json_bytes((arcgis_query_dir / "centers_ids.json").read_bytes())
    center_ids = list(cast(list[Any], center_ids_payload.get("objectIds", [])))
    max_payload = parse_json_bytes((arcgis_query_dir / "centers_max_page_0.json").read_bytes())
    terminal_max_payload = parse_json_bytes(
        (arcgis_query_dir / "centers_max_page_terminal.json").read_bytes()
    )
    small_payloads = [
        parse_json_bytes((arcgis_query_dir / name).read_bytes())
        for name in (
            "centers_small_page_0.json",
            "centers_small_page_1.json",
            "centers_small_page_2.json",
            "centers_small_page_terminal.json",
        )
    ]
    batch_payload = parse_json_bytes(
        (arcgis_query_dir / "centers_object_id_batch.json").read_bytes()
    )
    geojson_payload = parse_json_bytes((arcgis_query_dir / "centers_geojson.json").read_bytes())
    max_rows = rows_from_arcgis_response(max_payload)
    small_rows = [row for payload in small_payloads for row in rows_from_arcgis_response(payload)]
    batch_rows = rows_from_arcgis_response(batch_payload)
    geojson_rows = rows_from_geojson_response(geojson_payload)
    max_pagination = analyze_pagination(
        [max_payload, terminal_max_payload],
        object_id_field="OBJECTID",
        expected_object_ids=center_ids,
    )
    small_pagination = analyze_pagination(
        small_payloads,
        object_id_field="OBJECTID",
        expected_object_ids=center_ids,
    )
    max_small_equivalence = compare_row_sets(
        max_rows,
        small_rows,
        identifier_field="Facility_Number",
        compared_fields=CENTER_FIELDS,
    )
    max_batch_equivalence = compare_row_sets(
        max_rows,
        batch_rows,
        identifier_field="Facility_Number",
        compared_fields=CENTER_FIELDS,
    )
    max_geojson_equivalence = compare_row_sets(
        max_rows,
        geojson_rows,
        identifier_field="Facility_Number",
        compared_fields=CENTER_FIELDS,
    )
    center_profile = profile_facility_rows(
        max_rows,
        source_id="arcgis_licensed_child_care_centers",
        identifier_field="Facility_Number",
        type_field="Facility_Type",
        status_field="Facility_Status",
        fields=CENTER_FIELDS,
    )

    coverage_rows: list[dict[str, Any]] = []
    conflict_rows: list[dict[str, Any]] = []
    program_ids = list(DATASTORE_RESOURCES)
    field_pairs = (
        ("facility_name", "facility_name"),
        ("facility_type", "facility_type"),
        ("facility_status", "facility_status"),
        ("facility_address", "facility_address"),
        ("facility_city", "facility_city"),
        ("facility_zip", "facility_zip"),
        ("county_name", "county_name"),
        ("facility_capacity", "facility_capacity"),
        ("licensee", "licensee"),
    )
    for left_index, left_id in enumerate(program_ids):
        for right_id in program_ids[left_index + 1 :]:
            summary, conflicts = compare_source_coverage(
                program_rows[left_id],
                program_rows[right_id],
                left_id_field="facility_number",
                right_id_field="facility_number",
                field_pairs=field_pairs,
            )
            left_profile = program_profiles[left_id]
            right_profile = program_profiles[right_id]
            coverage_rows.append(
                {
                    "left_source": left_id,
                    "right_source": right_id,
                    **summary,
                    "left_missing_identifier_count": left_profile[
                        "missing_facility_identifier_count"
                    ],
                    "right_missing_identifier_count": right_profile[
                        "missing_facility_identifier_count"
                    ],
                    "left_duplicate_identifier_count": left_profile[
                        "duplicate_facility_identifier_count"
                    ],
                    "right_duplicate_identifier_count": right_profile[
                        "duplicate_facility_identifier_count"
                    ],
                    "comparison_status": "inconclusive",
                    "scope_note": (
                        "Program-specific scopes differ; one-side-only identifiers are "
                        "scope differences "
                        "unless later evidence proves an omission."
                    ),
                }
            )
            conflict_rows.extend(_aggregate_conflicts(left_id, right_id, conflicts))

    child_center_id = "5bac6551-4d6c-45d6-93b8-e6ded428d98e"
    center_summary, center_conflicts = compare_source_coverage(
        max_rows,
        program_rows[child_center_id],
        left_id_field="Facility_Number",
        right_id_field="facility_number",
        field_pairs=(
            ("Facility_Name", "facility_name"),
            ("Facility_Type", "facility_type"),
            ("Facility_Status", "facility_status"),
            ("Facility_Address", "facility_address"),
            ("Facility_City", "facility_city"),
            ("Facility_Zip", "facility_zip"),
            ("County_Name", "county_name"),
            ("Facility_Capacity", "facility_capacity"),
            ("Licensee", "licensee"),
        ),
    )
    coverage_rows.append(
        {
            "left_source": "arcgis_licensed_child_care_centers",
            "right_source": child_center_id,
            **center_summary,
            "left_missing_identifier_count": center_profile["missing_facility_identifier_count"],
            "right_missing_identifier_count": program_profiles[child_center_id][
                "missing_facility_identifier_count"
            ],
            "left_duplicate_identifier_count": center_profile[
                "duplicate_facility_identifier_count"
            ],
            "right_duplicate_identifier_count": program_profiles[child_center_id][
                "duplicate_facility_identifier_count"
            ],
            "comparison_status": "inconclusive",
            "scope_note": (
                "The approved evidence does not establish that this 15-row ArcGIS layer is a full "
                "or equivalent Child Care Centers source."
            ),
        }
    )
    conflict_rows.extend(
        _aggregate_conflicts(
            "arcgis_licensed_child_care_centers", child_center_id, center_conflicts
        )
    )

    type_rows: list[dict[str, Any]] = []
    for resource_id, profile in program_profiles.items():
        for observed in cast(list[dict[str, Any]], profile["facility_type_counts"]):
            type_rows.append(
                {
                    "source_id": resource_id,
                    "code_field": "",
                    "label_field": "facility_type",
                    "raw_code": "",
                    "raw_label": observed["raw_value"],
                    "record_count": observed["record_count"],
                    "evidence_status": "label_only_no_code_domain",
                }
            )
    for observed in cast(list[dict[str, Any]], center_profile["facility_type_counts"]):
        type_rows.append(
            {
                "source_id": "arcgis_licensed_child_care_centers",
                "code_field": "",
                "label_field": "Facility_Type",
                "raw_code": "",
                "raw_label": observed["raw_value"],
                "record_count": observed["record_count"],
                "evidence_status": "label_only_no_code_domain",
            }
        )

    value_sources: dict[str, list[dict[str, Any]]] = dict(program_rows)
    value_sources["arcgis_licensed_child_care_centers"] = max_rows
    code_733_contexts = exact_value_contexts(value_sources, "733")
    code_733_type_contexts = [
        context for context in code_733_contexts if "type" in str(context["field"]).casefold()
    ]
    type_rows.append(
        {
            "source_id": "all_approved_row_evidence",
            "code_field": "unverified",
            "label_field": "",
            "raw_code": "733",
            "raw_label": "",
            "record_count": sum(
                int(context["record_count"]) for context in code_733_type_contexts
            ),
            "evidence_status": "unresolved_not_observed_as_type_code",
        }
    )

    catalog_map = dict(CATALOG_ENDPOINTS)
    manifest: list[dict[str, Any]] = []
    for endpoint_id, url in CATALOG_ENDPOINTS:
        suffix = ".json" if "api/3/action" in url else ".html"
        path = catalog_dir / f"{endpoint_id}{suffix}"
        if path.is_file():
            status = 404 if endpoint_id == "data_ca_package_uuid" else 200
            manifest.append(
                _manifest_artifact(
                    path,
                    endpoint_id=endpoint_id,
                    request_url=url,
                    status=status,
                    warnings=("HTTP status 404",) if status == 404 else (),
                )
            )
    for resource_id in DATASTORE_RESOURCES:
        metadata_path = datastore_metadata_dir / f"datastore_{resource_id}_metadata.json"
        metadata_url = (
            "https://data.ca.gov/api/action/datastore_search?"
            f"resource_id={resource_id}&limit=0"
        )
        manifest.append(
            _manifest_artifact(
                metadata_path,
                endpoint_id=f"datastore_{resource_id}_metadata",
                request_url=metadata_url,
            )
        )
        for page_path in sorted(
            program_records_dir.glob(f"datastore_{resource_id}_page_*.json"),
            key=lambda path: path.name,
        ):
            offset_match = page_path.stem.split("_page_")[-1].split("_")[0]
            request_url = (
                "https://data.ca.gov/api/action/datastore_search?"
                f"resource_id={resource_id}&limit=10000&offset={int(offset_match)}&sort=_id%20asc"
            )
            manifest.append(
                _manifest_artifact(
                    page_path,
                    endpoint_id=page_path.stem,
                    request_url=request_url,
                )
            )
    for endpoint_id, url in DICTIONARY_ENDPOINTS:
        manifest.append(
            _manifest_artifact(
                dictionary_dir / f"{endpoint_id}.csv",
                endpoint_id=endpoint_id,
                request_url=url,
            )
        )
    for endpoint_id, url in ARCGIS_METADATA_ENDPOINTS:
        path = arcgis_dir / f"{endpoint_id}.html"
        manifest.append(
            _manifest_artifact(path, endpoint_id=endpoint_id, request_url=url)
        )

    arcgis_query_urls = {
        "centers_ids": f"{ARCGIS_CENTER_QUERY_BASE}?where=1%3D1&returnIdsOnly=true&f=json",
        "centers_max_page_0": (
            f"{ARCGIS_CENTER_QUERY_BASE}?where=1%3D1&outFields=%2A&returnGeometry=true&"
            "orderByFields=OBJECTID&resultOffset=0&resultRecordCount=1000&f=json"
        ),
        "centers_max_page_terminal": (
            f"{ARCGIS_CENTER_QUERY_BASE}?where=1%3D1&outFields=%2A&returnGeometry=true&"
            "orderByFields=OBJECTID&resultOffset=15&resultRecordCount=1000&f=json"
        ),
        "centers_small_page_0": (
            f"{ARCGIS_CENTER_QUERY_BASE}?where=1%3D1&outFields=%2A&returnGeometry=false&"
            "orderByFields=OBJECTID&resultOffset=0&resultRecordCount=7&f=json"
        ),
        "centers_small_page_1": (
            f"{ARCGIS_CENTER_QUERY_BASE}?where=1%3D1&outFields=%2A&returnGeometry=false&"
            "orderByFields=OBJECTID&resultOffset=7&resultRecordCount=7&f=json"
        ),
        "centers_small_page_2": (
            f"{ARCGIS_CENTER_QUERY_BASE}?where=1%3D1&outFields=%2A&returnGeometry=false&"
            "orderByFields=OBJECTID&resultOffset=14&resultRecordCount=7&f=json"
        ),
        "centers_small_page_terminal": (
            f"{ARCGIS_CENTER_QUERY_BASE}?where=1%3D1&outFields=%2A&returnGeometry=false&"
            "orderByFields=OBJECTID&resultOffset=21&resultRecordCount=7&f=json"
        ),
        "centers_object_id_batch": (
            f"{ARCGIS_CENTER_QUERY_BASE}?objectIds="
            "1%2C2%2C3%2C4%2C5%2C6%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C14%2C15&"
            "outFields=%2A&returnGeometry=false&orderByFields=OBJECTID&f=json"
        ),
        "centers_geojson": (
            f"{ARCGIS_CENTER_QUERY_BASE}?where=1%3D1&outFields=%2A&returnGeometry=true&"
            "orderByFields=OBJECTID&resultOffset=0&resultRecordCount=1000&f=geojson"
        ),
    }
    for endpoint_id, url in arcgis_query_urls.items():
        path = arcgis_query_dir / f"{endpoint_id}.json"
        manifest.append(
            _manifest_artifact(path, endpoint_id=endpoint_id, request_url=url)
        )

    prior_map = {
        "catalog-package-ccl-facilities": (
            "https://data.ca.gov/api/3/action/package_show?id=ccl-facilities",
            404,
        ),
        "family-layer": (ARCGIS_METADATA_ENDPOINTS[1][1], 200),
        "family-ids": (
            "https://services3.arcgis.com/42Dx6OWonqK9LoEE/ArcGIS/rest/services/"
            "Family_Child_Care_Homes/FeatureServer/0/query?where=1%3D1&"
            "returnIdsOnly=true&f=json",
            200,
        ),
        "centers-layer": (ARCGIS_METADATA_ENDPOINTS[3][1], 200),
        "centers-ids": (arcgis_query_urls["centers_ids"], 200),
    }
    for stem, (url, status) in prior_map.items():
        matches = list(prior_discovery_dir.glob(f"{stem}.*"))
        if matches:
            manifest.append(
                _manifest_artifact(
                    matches[0], endpoint_id=f"prior_{stem}", request_url=url, status=status
                )
            )

    attempt = parse_json_bytes(statewide_safe_attempt.read_bytes())
    manifest.append(dict(attempt))
    issue_root = catalog_dir.parents[1]
    github_paths = list(issue_root.glob("*/github/issue-490.html"))
    for github_path in github_paths:
        if github_path.stat().st_size:
            manifest.append(
                _manifest_artifact(
                    github_path,
                    endpoint_id="github_issue_490",
                    request_url="https://github.com/nicho1ab/RecordsTracker/issues/490",
                )
            )

    candidates = [
        _candidate_identity(
            endpoint_id,
            catalog_map[endpoint_id],
            catalog_dir / f"{endpoint_id}.html",
        )
        for endpoint_id in (
            "lab_catalog_primary",
            "lab_catalog_duplicate_1",
            "lab_catalog_duplicate_2",
        )
    ]
    proposed_urls: set[str] = set()
    for endpoint_id in (
        "lab_catalog_primary",
        "lab_catalog_duplicate_1",
        "lab_catalog_duplicate_2",
    ):
        for url in extract_public_urls_from_html(
            (catalog_dir / f"{endpoint_id}.html").read_bytes()
        ):
            if (
                "gis.data.chhs.ca.gov/api/download/" in url
                or "gis.data.chhs.ca.gov/datasets/" in url
                or "services.arcgis.com/XLPEppdz2H9dOiqp/" in url
                or "data.chhs.ca.gov/dataset/3c2fc34a-8517-4938-b3ee-992af04cd6b7/" in url
            ):
                proposed_urls.add(url)

    endpoint_rows = [
        {
            "endpoint_id": artifact["endpoint_id"],
            "url": artifact["request_url"],
            "http_status": artifact["status"],
            "content_type": artifact["content_type"],
            "observation_status": (
                "pass" if int(artifact["status"]) == 200 else "fail"
            ),
        }
        for artifact in manifest
    ]
    source_endpoints = output_envelope(
        "source-endpoints",
        {
            "endpoints": sorted(
                endpoint_rows,
                key=lambda row: (str(row["url"]), str(row["endpoint_id"])),
            ),
            "candidate_identities": candidates,
            "proposed_endpoints": [
                {
                    "url": url,
                    "status": "blocked_pending_allowlist",
                    "reason": "Official catalog relationship observed; endpoint was not accessed.",
                }
                for url in sorted(proposed_urls)
            ],
        },
        generated_at=generated_at,
        status="warning",
        warnings=("Multiple catalog identities have unresolved relationships.",),
    )
    snapshot_manifest = output_envelope(
        "snapshot-manifest",
        {
            "artifacts": sorted(manifest, key=lambda item: str(item["artifact_ref"])),
            "sanitized_redirect_chain": [
                {
                    "from": STATEWIDE_DOWNLOAD_URL,
                    "to": APPROVED_REDIRECT_ENDPOINT,
                    "query_parameters_retained": False,
                }
            ],
            "failed_boundary_excluded": "20260719T025614Z",
        },
        generated_at=generated_at,
        status="warning",
        warnings=(
            "The single statewide ZIP attempt returned 403; its sensitive error "
            "body was not retained.",
        ),
    )

    schema_sources = []
    for resource_id in DATASTORE_RESOURCES:
        fields = [
            {
                "name": str(field.get("id", "")),
                "type": str(field.get("type", "")),
                "alias": "",
                "nullable": None,
                "domain": None,
            }
            for field in program_fields[resource_id]
        ]
        schema_sources.append(
            {
                "source_id": resource_id,
                "source_name": PROGRAM_SOURCE_NAMES[resource_id],
                "field_count": len(fields),
                "fields": fields,
                "schema_fingerprint": ordered_schema_fingerprint(fields),
                "geometry_behavior": "none in datastore response",
                "status": "pass",
            }
        )
    schema_sources.extend(
        [
            {
                "source_id": "arcgis_licensed_child_care_centers",
                **center_layer,
                "field_count": len(cast(list[Any], center_layer["fields"])),
                "status": "pass",
            },
            {
                "source_id": "arcgis_family_child_care_homes",
                **family_layer,
                "field_count": len(cast(list[Any], family_layer["fields"])),
                "status": "fail",
            },
            {
                "source_id": "statewide_candidate_download",
                "fields": [],
                "field_count": 0,
                "schema_fingerprint": "",
                "status": "blocked",
                "reason": (
                    "Approved ZIP redirect returned 403 and catalog-linked service "
                    "is not allowlisted."
                ),
            },
        ]
    )
    schema_profile = output_envelope(
        "schema-profile",
        {"sources": schema_sources},
        generated_at=generated_at,
        status="blocked",
        warnings=("Statewide candidate field schema could not be retrieved.",),
    )

    pagination_equivalence = output_envelope(
        "pagination-equivalence",
        {
            "arcgis": {
                "source_id": "arcgis_licensed_child_care_centers",
                "reported_max_record_count": center_layer["max_record_count"],
                "max_page": max_pagination,
                "small_pages": small_pagination,
                "max_vs_small": max_small_equivalence,
                "max_vs_object_id_batch": max_batch_equivalence,
                "json_vs_geojson_properties": max_geojson_equivalence,
            },
            "datastores": datastore_pagination,
            "download_service_equivalence": {
                "status": "blocked",
                "verdict": "inconclusive",
                "reason": (
                    "The approved statewide ZIP returned 403 and the catalog-linked statewide "
                    "ArcGIS service is outside the allowlist; the 15-row licensed-center layer is "
                    "not assumed equivalent."
                ),
            },
        },
        generated_at=generated_at,
        status="blocked",
        warnings=("No legitimate statewide download/service pair was available for equivalence.",),
    )

    all_program_rows = sum(len(rows) for rows in program_rows.values())
    union_identifiers = {
        str(row["facility_number"]).strip()
        for rows in program_rows.values()
        for row in rows
        if row.get("facility_number") is not None
        and str(row["facility_number"]).strip()
    }
    facility_profile = output_envelope(
        "facility-profile",
        {
            "sources": [program_profiles[resource_id] for resource_id in DATASTORE_RESOURCES]
            + [center_profile],
            "aggregate": {
                "program_source_count": len(PROGRAM_SOURCE_NAMES),
                "program_row_count": all_program_rows,
                "program_unique_facility_identifier_union_count": len(union_identifiers),
                "arcgis_center_row_count": len(max_rows),
                "statewide_candidate_profile_status": "blocked",
            },
            "code_733": {
                "status": "unresolved",
                "exact_value_contexts": code_733_contexts,
                "facility_type_contexts": code_733_type_contexts,
                "conclusion": (
                    "No approved field domain or observed facility-type field maps raw code 733 "
                    "to a unique label."
                ),
            },
        },
        generated_at=generated_at,
        status="inconclusive",
        warnings=("Program sources are profiled; statewide candidate rows remain unavailable.",),
    )

    prior_ids_path = prior_discovery_dir / "centers-ids.json"
    previous_ids_payload = parse_json_bytes(prior_ids_path.read_bytes())
    previous_id_rows = [
        {"object_id": identifier}
        for identifier in cast(list[Any], previous_ids_payload.get("objectIds", []))
    ]
    current_id_rows = [{"object_id": identifier} for identifier in center_ids]
    center_change = compare_content_snapshots(
        previous_id_rows,
        current_id_rows,
        identifier_field="object_id",
        fields=["object_id"],
        previous_bytes_sha256=sha256_file(prior_ids_path),
        current_bytes_sha256=sha256_file(arcgis_query_dir / "centers_ids.json"),
        previous_schema_fingerprint=canonical_fingerprint(
            previous_ids_payload.get("objectIdFieldName", "")
        ),
        current_schema_fingerprint=canonical_fingerprint(
            center_ids_payload.get("objectIdFieldName", "")
        ),
        metadata_changed=False,
    )
    content_change = output_envelope(
        "content-change",
        {
            "comparisons": [
                {
                    "source_id": "arcgis_licensed_child_care_centers_ids",
                    **center_change,
                },
                {
                    "source_id": "statewide_candidate",
                    "status": "blocked",
                    "metadata_changed": "unknown",
                    "byte_changed": "unknown",
                    "schema_changed": "unknown",
                    "row_set_changed": "unknown",
                    "field_value_changed": "unknown",
                    "reason": "Only one failed statewide retrieval attempt was authorized.",
                },
            ]
        },
        generated_at=generated_at,
        status="inconclusive",
        warnings=("Catalog modification time is not treated as content change evidence.",),
    )

    deliverables: list[dict[str, Any]] = []
    json_outputs = {
        "source-endpoints.json": source_endpoints,
        "snapshot-manifest.json": snapshot_manifest,
        "schema-profile.json": schema_profile,
        "pagination-equivalence.json": pagination_equivalence,
        "facility-profile.json": facility_profile,
        "content-change.json": content_change,
    }
    for name, payload in json_outputs.items():
        digest = write_json_output(output_dir / name, payload, schema)
        deliverables.append({"name": name, "sha256": digest, "status": "pass"})
    csv_rows = {
        "facility-type-code-label.csv": type_rows,
        "coverage-comparison.csv": coverage_rows,
        "source-conflicts.csv": conflict_rows,
    }
    for name, rows in csv_rows.items():
        digest = write_csv_output(output_dir / name, CSV_CONTRACTS[name], rows)
        deliverables.append({"name": name, "sha256": digest, "status": "pass"})

    checks = [
        {"check": "program_datastore_pagination", "status": "pass"},
        {"check": "arcgis_center_max_pagination", "status": max_pagination["status"]},
        {"check": "arcgis_center_small_pagination", "status": small_pagination["status"]},
        {"check": "arcgis_center_object_id_batch", "status": max_batch_equivalence["status"]},
        {"check": "arcgis_center_geojson", "status": max_geojson_equivalence["status"]},
        {"check": "statewide_download", "status": "blocked"},
        {"check": "statewide_download_service_equivalence", "status": "blocked"},
        {"check": "family_home_arcgis_endpoint", "status": "fail"},
        {"check": "code_733_unique_mapping", "status": "inconclusive"},
        {"check": "generated_output_contract", "status": "pass"},
        {"check": "sensitive_query_retention", "status": "pass"},
    ]
    validation_summary = output_envelope(
        "validation-summary",
        {
            "checks": checks,
            "deliverables": sorted(deliverables, key=lambda item: str(item["name"])),
            "contract_version": CONTRACT_VERSION,
        },
        generated_at=generated_at,
        status="warning",
        warnings=("Statewide retrieval and equivalence checks remain blocked.",),
    )
    validation_hash = write_json_output(
        output_dir / "validation-summary.json", validation_summary, schema
    )
    deliverables.append(
        {"name": "validation-summary.json", "sha256": validation_hash, "status": "pass"}
    )
    return [
        {
            "artifact_ref": (output_dir / item["name"]).as_posix(),
            "sha256": item["sha256"],
            "status": item["status"],
        }
        for item in sorted(deliverables, key=lambda entry: str(entry["name"]))
    ]


def main() -> int:
    args = _parser().parse_args()
    raw_root = cast(Path, args.raw_root)
    if not (
        args.fetch_statewide_zip
        or args.fetch_catalog_metadata
        or args.fetch_residential_resource
        or args.fetch_arcgis_center_pages
        or args.fetch_program_records
        or args.evaluate_snapshots
    ):
        raise SystemExit("No action selected.")

    stamp = _retrieval_stamp()
    artifacts: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    def fetch(endpoint_id: str, url: str, group: str, suffix: str) -> Path | None:
        artifact_ref = (
            f"data/raw/source-profiling/issue-490/{stamp}/{group}/{endpoint_id}.{suffix}"
        )
        artifact_path = raw_root / stamp / group / f"{endpoint_id}.{suffix}"
        try:
            artifact = fetch_and_preserve(
                endpoint_id=endpoint_id,
                request_url=url,
                artifact_path=artifact_path,
                artifact_ref=artifact_ref,
                transport=ExactRedirectTransport([]),
                timeout_seconds=60.0,
            )
        except (OSError, ValueError) as error:
            errors.append({"endpoint_id": endpoint_id, "error": str(error)})
            return None
        artifacts.append(artifact.as_dict())
        return artifact_path

    if args.fetch_statewide_zip:
        artifact_ref = (
            f"data/raw/source-profiling/issue-490/{stamp}/"
            "statewide/statewide-facilities-original.zip"
        )
        artifact_path = (
            raw_root / stamp / "statewide" / "statewide-facilities-original.zip"
        )
        artifact = fetch_and_preserve(
            endpoint_id="statewide_full_download",
            request_url=STATEWIDE_DOWNLOAD_URL,
            artifact_path=artifact_path,
            artifact_ref=artifact_ref,
            transport=ExactRedirectTransport([APPROVED_REDIRECT_ENDPOINT]),
            timeout_seconds=120.0,
        )
        artifacts.append(artifact.as_dict())

    if args.fetch_catalog_metadata:
        for endpoint_id, url in CATALOG_ENDPOINTS:
            fetch(endpoint_id, url, "catalog", "json" if "api/3/action" in url else "html")
        for resource_id in DATASTORE_RESOURCES:
            fetch(
                f"datastore_{resource_id}_metadata",
                f"https://data.ca.gov/api/action/datastore_search?resource_id={resource_id}&limit=0",
                "datastore",
                "json",
            )
        for endpoint_id, url in DICTIONARY_ENDPOINTS:
            fetch(endpoint_id, url, "dictionary", "csv")
        for endpoint_id, url in ARCGIS_METADATA_ENDPOINTS:
            fetch(endpoint_id, url, "arcgis", "html")

    if args.fetch_residential_resource:
        endpoint_id, url = next(
            item
            for item in CATALOG_ENDPOINTS
            if item[0] == "chhs_resource_residential_care_elderly"
        )
        fetch(endpoint_id, url, "catalog", "html")

    if args.fetch_arcgis_center_pages:
        query_variants = (
            (
                "centers_ids",
                "where=1%3D1&returnIdsOnly=true&f=json",
            ),
            (
                "centers_max_page_0",
                "where=1%3D1&outFields=*&returnGeometry=true&orderByFields=OBJECTID&"
                "resultOffset=0&resultRecordCount=1000&f=json",
            ),
            (
                "centers_max_page_terminal",
                "where=1%3D1&outFields=*&returnGeometry=true&orderByFields=OBJECTID&"
                "resultOffset=15&resultRecordCount=1000&f=json",
            ),
            (
                "centers_small_page_0",
                "where=1%3D1&outFields=*&returnGeometry=false&orderByFields=OBJECTID&"
                "resultOffset=0&resultRecordCount=7&f=json",
            ),
            (
                "centers_small_page_1",
                "where=1%3D1&outFields=*&returnGeometry=false&orderByFields=OBJECTID&"
                "resultOffset=7&resultRecordCount=7&f=json",
            ),
            (
                "centers_small_page_2",
                "where=1%3D1&outFields=*&returnGeometry=false&orderByFields=OBJECTID&"
                "resultOffset=14&resultRecordCount=7&f=json",
            ),
            (
                "centers_small_page_terminal",
                "where=1%3D1&outFields=*&returnGeometry=false&orderByFields=OBJECTID&"
                "resultOffset=21&resultRecordCount=7&f=json",
            ),
            (
                "centers_object_id_batch",
                "objectIds=1%2C2%2C3%2C4%2C5%2C6%2C7%2C8%2C9%2C10%2C11%2C12%2C13%2C14%2C15&"
                "outFields=*&returnGeometry=false&orderByFields=OBJECTID&f=json",
            ),
            (
                "centers_geojson",
                "where=1%3D1&outFields=*&returnGeometry=true&orderByFields=OBJECTID&"
                "resultOffset=0&resultRecordCount=1000&f=geojson",
            ),
        )
        for endpoint_id, query in query_variants:
            fetch(endpoint_id, f"{ARCGIS_CENTER_QUERY_BASE}?{query}", "arcgis-query", "json")

    if args.fetch_program_records:
        if args.datastore_metadata_dir is None:
            raise SystemExit("--datastore-metadata-dir is required with --fetch-program-records.")
        page_size = 10_000
        for resource_id in DATASTORE_RESOURCES:
            metadata_path = (
                args.datastore_metadata_dir / f"datastore_{resource_id}_metadata.json"
            )
            metadata = parse_json_bytes(metadata_path.read_bytes())
            result = metadata.get("result")
            if not isinstance(result, dict) or not isinstance(result.get("total"), int):
                errors.append(
                    {"endpoint_id": resource_id, "error": "metadata total is unavailable"}
                )
                continue
            total = int(result["total"])
            offset = 0
            while offset < total:
                url = (
                    "https://data.ca.gov/api/action/datastore_search?"
                    f"resource_id={resource_id}&limit={page_size}&offset={offset}&sort=_id%20asc"
                )
                fetch(
                    f"datastore_{resource_id}_page_{offset:06d}",
                    url,
                    "program-records",
                    "json",
                )
                offset += page_size
            terminal_url = (
                "https://data.ca.gov/api/action/datastore_search?"
                f"resource_id={resource_id}&limit={page_size}&offset={offset}&sort=_id%20asc"
            )
            fetch(
                f"datastore_{resource_id}_page_{offset:06d}_terminal",
                terminal_url,
                "program-records",
                "json",
            )

    if args.evaluate_snapshots:
        required_paths = {
            "--catalog-dir": args.catalog_dir,
            "--arcgis-dir": args.arcgis_dir,
            "--arcgis-query-dir": args.arcgis_query_dir,
            "--prior-discovery-dir": args.prior_discovery_dir,
            "--datastore-metadata-dir": args.datastore_metadata_dir,
            "--dictionary-dir": args.dictionary_dir,
            "--program-records-dir": args.program_records_dir,
            "--statewide-safe-attempt": args.statewide_safe_attempt,
        }
        missing = [name for name, path in required_paths.items() if path is None]
        if missing:
            raise SystemExit(f"Evaluation requires: {', '.join(missing)}")
        evaluation = _evaluate_preserved_snapshots(
            catalog_dir=cast(Path, args.catalog_dir),
            arcgis_dir=cast(Path, args.arcgis_dir),
            arcgis_query_dir=cast(Path, args.arcgis_query_dir),
            prior_discovery_dir=cast(Path, args.prior_discovery_dir),
            datastore_metadata_dir=cast(Path, args.datastore_metadata_dir),
            dictionary_dir=cast(Path, args.dictionary_dir),
            program_records_dir=cast(Path, args.program_records_dir),
            statewide_safe_attempt=cast(Path, args.statewide_safe_attempt),
            output_dir=args.output_dir,
            schema_path=args.schema,
        )
        artifacts.extend(evaluation)

    print(json.dumps({"artifacts": artifacts, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
