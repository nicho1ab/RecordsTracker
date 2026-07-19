from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from ccld_complaints.arcgis_facility_source_evaluation import (
    ARCGIS_ITEM_ID,
    CONTRACT_VERSION,
    EndpointPolicyError,
    ProhibitedContentError,
    analyze_complete_pagination,
    approve_redirect,
    approved_redirect_target,
    assert_approved_url,
    assert_response_safe_to_retain,
    choose_recommendation,
    classify_duplicate_facility_groups,
    classify_field_value_sets,
    compare_export_query,
    compare_observations,
    compare_program_sources,
    decision_payload,
    domain_fingerprint,
    investigate_code_733,
    load_schema,
    normalize_scalar,
    output_envelope,
    parse_export_bytes,
    profile_layer_metadata,
    project_rows,
    resolve_projection_fields,
    schema_fingerprint,
    validate_csv_export_response,
    validate_output,
    write_captured_bytes,
    write_output_package,
)
from ccld_complaints.statewide_facility_source_evaluation import rows_from_arcgis_response
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_DIR = Path("tests/fixtures/source_profiling/build_week_arcgis")
SCHEMA_PATH = Path("schemas/build-week-2026-arcgis-shadow-evaluation.schema.json")


def _json(name: str) -> dict[str, object]:
    parsed = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _query_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in ("page-0.json", "page-1.json"):
        rows.extend(rows_from_arcgis_response(_json(name)))
    return rows


def _program_rows() -> tuple[list[str], list[dict[str, str]]]:
    fields, rows, _metadata = parse_export_bytes((FIXTURE_DIR / "program-source.csv").read_bytes())
    return fields, rows


def test_service_and_layer_metadata_resolve_exact_identity_and_capabilities() -> None:
    service = _json("service.json")
    layer = _json("layer.json")

    profile = profile_layer_metadata(layer)

    assert service["serviceItemId"] == ARCGIS_ITEM_ID
    assert profile["service_item_id"] == ARCGIS_ITEM_ID
    assert profile["layer_id"] == 0
    assert profile["object_id_field"] == "OBJECTID"
    assert profile["max_record_count"] == 2
    assert profile["supports_pagination"] is True
    assert profile["schema_fingerprint"]
    assert profile["domain_fingerprint"]


def test_endpoint_policy_accepts_only_exact_approved_public_families() -> None:
    approved = (
        "https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/"
        "CDSS_CCL_Facilities/FeatureServer/0/query?where=1%3D1&f=json"
    )
    assert assert_approved_url(approved) == approved
    assert assert_approved_url(
        "https://gis.data.chhs.ca.gov/api/download/v1/items/"
        f"{ARCGIS_ITEM_ID}/csv?layers=0"
    ).endswith("/csv?layers=0")
    assert assert_approved_url(
        "https://data.ca.gov/api/action/datastore_search?"
        "resource_id=5bac6551-4d6c-45d6-93b8-e6ded428d98e&limit=2&offset=0"
    )

    with pytest.raises(EndpointPolicyError, match="outside"):
        assert_approved_url("https://example.test/not-approved")
    with pytest.raises(EndpointPolicyError, match="Sensitive"):
        assert_approved_url(f"{approved}&token=not-allowed")


def test_redirect_policy_rejects_unsupported_host_and_path() -> None:
    source = (
        "https://gis.data.chhs.ca.gov/api/download/v1/items/"
        f"{ARCGIS_ITEM_ID}/csv?layers=0"
    )
    assert approved_redirect_target(source, f"/{source.split('/', 3)[3]}") == source
    approved_cache = (
        "https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/"
        "CDSS_CCL_Facilities/FeatureServer/replicafilescache/"
        "CDSS_CCL_Facilities_-6873909777392143700.csv"
    )
    assert approved_redirect_target(source, approved_cache) == approved_cache

    with pytest.raises(EndpointPolicyError):
        approved_redirect_target(source, "https://storage.example.test/file.zip")
    with pytest.raises(EndpointPolicyError):
        approved_redirect_target(source, "https://gis.data.chhs.ca.gov/private/file.zip")
    with pytest.raises(EndpointPolicyError):
        approved_redirect_target(source, f"{approved_cache}.zip")
    with pytest.raises(EndpointPolicyError):
        approved_redirect_target(source, f"{approved_cache}?download=true")
    with pytest.raises(EndpointPolicyError):
        approved_redirect_target(approved_cache, "https://services.arcgis.com/other.csv")


def test_azure_export_redirect_policy_is_exact_and_terminal() -> None:
    approved_cache = (
        "https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/"
        "CDSS_CCL_Facilities/FeatureServer/replicafilescache/"
        "CDSS_CCL_Facilities_-6873909777392143700.csv"
    )
    approved_azure = (
        "https://stg-arcgisazurecdataprod.az.arcgis.com/exportfiles-20707-4235/"
        "CDSS_CCL_Facilities_-6873909777392143700.csv"
    )
    assert approved_redirect_target(approved_cache, approved_azure) == approved_azure

    rejected = (
        f"{approved_azure}.zip",
        "https://stg-arcgisazurecdataprod.az.arcgis.com/other/export.csv",
        "https://other.az.arcgis.com/exportfiles-20707-4235/export.csv",
        (
            "https://stg-arcgisazurecdataprod.az.arcgis.com/"
            "exportfiles-20707-4235/nested/export.csv"
        ),
    )
    for destination in rejected:
        with pytest.raises(EndpointPolicyError):
            approved_redirect_target(approved_cache, destination)

    with pytest.raises(EndpointPolicyError):
        approved_redirect_target(approved_azure, "https://services.arcgis.com/other.csv")


def test_opaque_azure_query_is_process_local_and_recorded_only_as_sanitized(
    capsys: pytest.CaptureFixture[str],
) -> None:
    approved_cache = (
        "https://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/"
        "CDSS_CCL_Facilities/FeatureServer/replicafilescache/"
        "CDSS_CCL_Facilities_-6873909777392143700.csv"
    )
    approved_azure = (
        "https://stg-arcgisazurecdataprod.az.arcgis.com/exportfiles-20707-4235/"
        "CDSS_CCL_Facilities_-6873909777392143700.csv"
    )
    opaque_marker = "opaque-process-local-material"
    transport_url = f"{approved_azure}?{opaque_marker}"

    approved = approve_redirect(approved_cache, transport_url)

    assert approved.transport_url == transport_url
    assert approved.recorded_url == approved_azure
    assert approved.terminal is True
    assert opaque_marker not in repr(approved)
    assert opaque_marker not in json.dumps(
        {"redirect_chain": [approved.recorded_url], "final_url": approved.recorded_url}
    )
    assert "?" not in approved.recorded_url

    with pytest.raises(EndpointPolicyError) as caller_supplied:
        assert_approved_url(transport_url)
    assert opaque_marker not in str(caller_supplied.value)

    wrong_destinations = (
        f"https://other.az.arcgis.com/exportfiles-20707-4235/export.csv?{opaque_marker}",
        (
            "https://stg-arcgisazurecdataprod.az.arcgis.com/other/"
            f"CDSS_CCL_Facilities_-6873909777392143700.csv?{opaque_marker}"
        ),
        (
            "https://stg-arcgisazurecdataprod.az.arcgis.com/exportfiles-20707-4235/"
            f"other.csv?{opaque_marker}"
        ),
    )
    for destination in wrong_destinations:
        with pytest.raises(EndpointPolicyError) as rejected:
            approve_redirect(approved_cache, destination)
        assert opaque_marker not in str(rejected.value)

    with pytest.raises(EndpointPolicyError) as fragment:
        approve_redirect(approved_cache, f"{transport_url}#{opaque_marker}")
    assert opaque_marker not in str(fragment.value)

    with pytest.raises(EndpointPolicyError) as further_redirect:
        approve_redirect(transport_url, approved_azure, source_is_terminal=True)
    assert opaque_marker not in str(further_redirect.value)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_raw_response_is_written_exclusively_and_hashed_before_parsing(tmp_path: Path) -> None:
    body = b'{"public":true}\n'
    target = tmp_path / "raw" / "response.json"

    digest = write_captured_bytes(target, body)

    assert target.read_bytes() == body
    assert digest == sha256_bytes(body)
    with pytest.raises(FileExistsError):
        write_captured_bytes(target, b"replacement")
    assert target.read_bytes() == body


def test_complete_pagination_proves_terminal_page_and_maximum_boundary() -> None:
    pages = [_json("page-0.json"), _json("page-1.json"), _json("page-terminal.json")]

    result = analyze_complete_pagination(
        pages,
        object_id_field="OBJECTID",
        facility_id_field="FAC_NBR",
        expected_object_ids=[1, 2, 3],
        maximum_record_count=2,
    )

    assert result["status"] == "pass"
    assert result["page_counts"] == [2, 1, 0]
    assert result["record_count"] == 3
    assert result["unique_facility_id_count"] == 3
    assert result["terminal_page_observed"] is True
    assert result["maximum_record_count_respected"] is True


def test_pagination_detects_duplicate_and_missing_facility_ids() -> None:
    first = _json("page-0.json")
    second = _json("page-1.json")
    second_rows = rows_from_arcgis_response(second)
    second_rows[0]["FAC_NBR"] = "100002"
    second["features"] = [{"attributes": second_rows[0]}]
    duplicate = analyze_complete_pagination(
        [first, second, _json("page-terminal.json")],
        object_id_field="OBJECTID",
        facility_id_field="FAC_NBR",
        expected_object_ids=[1, 2, 3],
        maximum_record_count=2,
    )
    assert duplicate["status"] == "pass"
    assert duplicate["facility_id_status"] == "warning"
    assert duplicate["duplicate_facility_ids"] == ["100002"]

    second_rows[0]["FAC_NBR"] = ""
    second["features"] = [{"attributes": second_rows[0]}]
    missing = analyze_complete_pagination(
        [first, second, _json("page-terminal.json")],
        object_id_field="OBJECTID",
        facility_id_field="FAC_NBR",
        expected_object_ids=[1, 2, 3],
        maximum_record_count=2,
    )
    assert missing["status"] == "pass"
    assert missing["facility_id_status"] == "warning"
    assert missing["missing_facility_id_row_count"] == 1


def test_pagination_rejects_missing_terminal_page_and_malformed_feature() -> None:
    no_terminal = analyze_complete_pagination(
        [_json("page-0.json"), _json("page-1.json")],
        object_id_field="OBJECTID",
        facility_id_field="FAC_NBR",
        expected_object_ids=[1, 2, 3],
        maximum_record_count=2,
    )
    malformed = analyze_complete_pagination(
        [{"features": [{"geometry": {}}]}, _json("page-terminal.json")],
        object_id_field="OBJECTID",
        facility_id_field="FAC_NBR",
        expected_object_ids=[],
        maximum_record_count=2,
    )

    assert no_terminal["status"] == "fail"
    assert no_terminal["terminal_page_observed"] is False
    assert malformed["status"] == "fail"
    assert malformed["malformed_page_indexes"] == [0]
    with pytest.raises(json.JSONDecodeError):
        json.loads((FIXTURE_DIR / "malformed-response.json").read_text(encoding="utf-8"))


def test_schema_and_domain_drift_have_separate_fingerprints() -> None:
    current = profile_layer_metadata(_json("layer.json"))
    changed = profile_layer_metadata(_json("layer-domain-drift.json"))

    assert current["schema_fingerprint"] != changed["schema_fingerprint"]
    assert current["domain_fingerprint"] != changed["domain_fingerprint"]
    assert schema_fingerprint(_json("layer.json")["fields"]) == current["schema_fingerprint"]  # type: ignore[arg-type,index]
    assert domain_fingerprint(_json("layer.json")["fields"]) == current["domain_fingerprint"]  # type: ignore[arg-type,index]


def test_layer_profile_normalizes_arcgis_editing_timestamps() -> None:
    layer = _json("layer.json")
    layer["currentVersion"] = 12
    layer["editingInfo"] = {
        "lastEditDate": 1784152772803,
        "schemaLastEditDate": 1784152772803,
        "dataLastEditDate": 1784152657049,
    }

    profile = profile_layer_metadata(layer)

    assert profile["current_version"] == 12
    assert profile["editing_info"] == {
        "last_edit_epoch_milliseconds": 1784152772803,
        "last_edit_utc": "2026-07-15T21:59:32.803Z",
        "schema_last_edit_epoch_milliseconds": 1784152772803,
        "schema_last_edit_utc": "2026-07-15T21:59:32.803Z",
        "data_last_edit_epoch_milliseconds": 1784152657049,
        "data_last_edit_utc": "2026-07-15T21:57:37.049Z",
    }


def test_live_arcgis_residence_and_phone_fields_resolve_to_governed_projection() -> None:
    mapping = resolve_projection_fields(
        ["RES_STREET_ADDR", "RES_CITY", "RES_STATE", "RES_ZIP_CODE", "FAC_PHONE_NBR"]
    )

    assert mapping["address"] == "RES_STREET_ADDR"
    assert mapping["city"] == "RES_CITY"
    assert mapping["state"] == "RES_STATE"
    assert mapping["zip"] == "RES_ZIP_CODE"
    assert mapping["telephone"] == "FAC_PHONE_NBR"


def test_query_and_export_are_semantically_equivalent_after_date_normalization() -> None:
    query_rows = _query_rows()
    export_fields, export_rows, export_metadata = parse_export_bytes(
        (FIXTURE_DIR / "export.csv").read_bytes()
    )
    query_mapping = resolve_projection_fields(list(query_rows[0]))
    export_mapping = resolve_projection_fields(export_fields)

    result = compare_export_query(
        query_rows,
        export_rows,
        query_mapping=query_mapping,
        export_mapping=export_mapping,
    )

    assert result["status"] == "pass"
    assert result["verdict"] == "equivalent"
    assert result["query_row_count"] == result["export_row_count"] == 3
    assert result["query_normalized_content_sha256"] == result[
        "export_normalized_content_sha256"
    ]
    assert export_metadata["container"] == "csv"


def test_export_response_is_validated_before_retention() -> None:
    metadata = validate_csv_export_response((FIXTURE_DIR / "export.csv").read_bytes())

    assert metadata["container"] == "csv"
    assert metadata["row_count"] == 3
    assert metadata["normalized_content_sha256"]
    with pytest.raises(ValueError, match="governed CSV"):
        validate_csv_export_response(b"<html><body>not a CSV export</body></html>")


def test_object_id_batch_equivalence_uses_ids_and_row_fingerprints() -> None:
    query_rows = _query_rows()
    mapping = resolve_projection_fields(list(query_rows[0]))

    result = compare_export_query(
        query_rows,
        list(reversed(query_rows)),
        query_mapping=mapping,
        export_mapping=mapping,
    )

    assert result["status"] == "pass"
    assert result["query_unique_facility_id_count"] == 3


def test_export_equivalence_preserves_matching_duplicate_row_sets() -> None:
    query_rows = _query_rows()
    duplicate_rows = [*query_rows, {**query_rows[0], "OBJECTID": 99}]
    mapping = resolve_projection_fields(list(query_rows[0]))

    result = compare_export_query(
        duplicate_rows,
        list(reversed(duplicate_rows)),
        query_mapping=mapping,
        export_mapping=mapping,
    )

    assert result["status"] == "pass"
    assert result["duplicate_facility_ids_query"] == ["100001"]
    assert result["duplicate_facility_ids_export"] == ["100001"]


def test_export_query_mismatch_detects_changed_values_and_id_set() -> None:
    query_rows = _query_rows()
    fields, rows, _metadata = parse_export_bytes((FIXTURE_DIR / "export-mismatch.csv").read_bytes())
    result = compare_export_query(
        query_rows,
        rows,
        query_mapping=resolve_projection_fields(list(query_rows[0])),
        export_mapping=resolve_projection_fields(fields),
    )

    assert result["status"] == "fail"
    assert result["query_only_facility_ids"] == ["100003"]
    assert result["export_only_facility_ids"] == ["100004"]
    assert result["changed_facility_ids"] == ["100001"]


def test_program_comparison_preserves_conflicts_scope_and_disappearance() -> None:
    query_rows = _query_rows()
    program_fields, program_rows = _program_rows()
    result = compare_program_sources(
        query_rows,
        program_rows,
        arcgis_mapping=resolve_projection_fields(list(query_rows[0])),
        program_mapping=resolve_projection_fields(program_fields),
    )

    assert result["shared_facility_id_count"] == 2
    assert result["arcgis_only_facility_id_count"] == 1
    assert result["program_only_facility_id_count"] == 1
    assert result["row_scope_classification"] == {
        "source-only": 1,
        "program-only": 1,
        "source-scope difference": 2,
    }
    assert result["field_difference_counts_by_field"]["status"][
        "conflicting nonblank value"
    ] == 1
    assert result["bounded_conflict_fingerprints"]
    assert "100002" not in json.dumps(result["bounded_conflict_fingerprints"])


def test_program_comparison_does_not_choose_first_duplicate_value() -> None:
    assert (
        classify_field_value_sets(
            "status",
            [{"status": "LICENSED"}, {"status": "CLOSED"}],
            [{"status": "LICENSED"}],
        )
        == "conflicting nonblank value"
    )


def test_duplicate_facility_groups_preserve_every_source_row() -> None:
    rows = [
        {
            "ObjectId": 1,
            "FAC_NBR": 100,
            "TYPE": 740,
            "PROGRAM_TYPE": "A",
            "COUNTY": "X",
            "FAC_LATITUDE": "1",
            "FAC_LONGITUDE": "2",
        },
        {
            "ObjectId": 2,
            "FAC_NBR": 100,
            "TYPE": 740,
            "PROGRAM_TYPE": "A",
            "COUNTY": "X",
            "FAC_LATITUDE": "1",
            "FAC_LONGITUDE": "2",
        },
        {
            "ObjectId": 3,
            "FAC_NBR": 200,
            "TYPE": 735,
            "PROGRAM_TYPE": "B",
            "COUNTY": "Y",
            "FAC_LATITUDE": "3",
            "FAC_LONGITUDE": "4",
        },
        {
            "ObjectId": 4,
            "FAC_NBR": 200,
            "TYPE": 735,
            "PROGRAM_TYPE": "B",
            "COUNTY": "Y",
            "FAC_LATITUDE": "5",
            "FAC_LONGITUDE": "6",
        },
        {
            "ObjectId": 5,
            "FAC_NBR": 300,
            "TYPE": 860,
            "PROGRAM_TYPE": "C",
            "COUNTY": "Y",
            "FAC_LATITUDE": "7",
            "FAC_LONGITUDE": "8",
        },
        {
            "ObjectId": 6,
            "FAC_NBR": 300,
            "TYPE": 860,
            "PROGRAM_TYPE": "C",
            "COUNTY": "Z",
            "FAC_LATITUDE": "9",
            "FAC_LONGITUDE": "10",
        },
    ]

    result = classify_duplicate_facility_groups(
        rows, facility_id_field="FAC_NBR", object_id_field="ObjectId"
    )

    assert result["duplicate_facility_id_count"] == 3
    assert result["duplicate_row_count"] == 6
    assert result["classification_counts"] == {
        "coordinate-and-county-conflict duplicate": 1,
        "coordinate-difference duplicate": 1,
        "object-id-only duplicate": 1,
    }
    assert result["same_facility_type_group_count"] == 3
    assert result["same_program_group_count"] == 3
    assert result["safely_collapsible_group_count"] == 0


def test_code_733_remains_unresolved_without_official_domain_relationship() -> None:
    layer = _json("layer.json")
    rows = _query_rows()
    rows.append({"OBJECTID": 733, "FAC_NBR": "100733", "FAC_TYPE_DESC": ""})

    result = investigate_code_733(rows, layer["fields"])  # type: ignore[arg-type,index]

    assert result["status"] == "unresolved"
    assert result["verified_descriptive_label"] is None
    assert result["exact_value_contexts"] == [
        {"source_id": "arcgis-layer", "field": "OBJECTID", "record_count": 1}
    ]


def test_code_733_is_not_misclassified_from_program_datastore_row_id() -> None:
    layer = _json("layer.json")
    result = investigate_code_733(
        _query_rows(),
        layer["fields"],  # type: ignore[arg-type,index]
        additional_sources={"retained-program-datastores": [{"_id": 733}] * 6},
    )

    assert result["status"] == "unresolved"
    assert result["verified_descriptive_label"] is None
    assert result["exact_value_contexts"] == [
        {
            "source_id": "retained-program-datastores",
            "field": "_id",
            "record_count": 6,
        }
    ]
    assert "datastore _id" in result["conclusion"]


def test_content_observations_distinguish_bytes_schema_domains_rows_and_values() -> None:
    fields = tuple(resolve_projection_fields(list(_query_rows()[0])))
    mapping = resolve_projection_fields(list(_query_rows()[0]))
    previous = project_rows(_query_rows(), mapping)
    current = [dict(row) for row in previous]
    current[0]["status"] = "CLOSED"

    result = compare_observations(
        previous,
        current,
        fields=fields,
        previous_raw_sha256="a",
        current_raw_sha256="b",
        previous_schema_fingerprint="schema-a",
        current_schema_fingerprint="schema-a",
        previous_domain_fingerprint="domain-a",
        current_domain_fingerprint="domain-a",
    )

    assert result["raw_bytes_changed"] is True
    assert result["normalized_content_changed"] is True
    assert result["schema_changed"] is False
    assert result["domain_changed"] is False
    assert result["facility_id_set_changed"] is False
    assert result["cadence_status"] == "unresolved"


def test_content_observation_detects_changed_facility_id_set() -> None:
    mapping = resolve_projection_fields(list(_query_rows()[0]))
    previous = project_rows(_query_rows(), mapping)
    current = [dict(row) for row in previous[1:]]
    fields = tuple(mapping)

    result = compare_observations(
        previous,
        current,
        fields=fields,
        previous_raw_sha256="same",
        current_raw_sha256="same",
        previous_schema_fingerprint="same",
        current_schema_fingerprint="same",
        previous_domain_fingerprint="same",
        current_domain_fingerprint="same",
    )

    assert result["facility_id_set_changed"] is True
    assert result["missing_facility_id_count"] == 1


def test_prohibited_response_is_rejected_before_retention() -> None:
    with pytest.raises(ProhibitedContentError, match="prohibited"):
        assert_response_safe_to_retain(
            (FIXTURE_DIR / "prohibited-response.txt").read_bytes(), "text/plain"
        )
    assert_response_safe_to_retain(b'{"public":true}', "application/json")


def test_recommendation_is_exact_and_gate_driven() -> None:
    adopt = {
        "source_access": True,
        "complete_pagination": True,
        "source_identity": True,
        "export_query_equivalence": True,
        "schema_and_domain_stability": True,
        "facility_id_integrity": True,
        "facility_id_coverage_fit": True,
        "authority_confirmed": True,
        "terms_confirmed": True,
        "rollback_suitable": True,
    }
    assert choose_recommendation(adopt) == "ADOPT"
    assert choose_recommendation({**adopt, "terms_confirmed": False}) == "SUPPLEMENT"
    assert choose_recommendation({**adopt, "terms_prohibit_use": True}) == "REJECT"
    assert choose_recommendation({**adopt, "complete_pagination": False}) == "INCONCLUSIVE"
    supplement = decision_payload(
        recommendation="SUPPLEMENT",
        source_identity={"item_id": ARCGIS_ITEM_ID},
        gates={**adopt, "terms_confirmed": False},
        observed_at="2026-07-19T00:00:00Z",
    )
    ownership = supplement["data"]["field_ownership"]
    assert "canonical facility identity" in ownership["must_not_own"]
    assert ownership["may_match_but_not_uniquely_own"] == ["facility_number"]


def test_every_output_validates_and_package_is_deterministic(tmp_path: Path) -> None:
    schema = load_schema(SCHEMA_PATH)
    observed_at = "2026-07-19T00:00:00Z"
    source_identity = {"item_id": ARCGIS_ITEM_ID, "layer_id": 0}
    gates = {"source_access": True, "complete_pagination": True}
    payloads = {
        "source-inventory.json": output_envelope(
            "source-inventory",
            {
                "catalog_records": [],
                "source_identity": source_identity,
                "endpoint_inventory": [],
                "redirect_outcomes": [],
            },
            observed_at=observed_at,
        ),
        "snapshot-manifest.json": output_envelope(
            "snapshot-manifest",
            {"artifacts": [], "retention_boundary": "ignored"},
            observed_at=observed_at,
        ),
        "schema-profile.json": output_envelope(
            "schema-profile",
            {"layer": {}, "field_mapping": {}, "code_733": {}},
            observed_at=observed_at,
        ),
        "pagination-profile.json": output_envelope(
            "pagination-profile",
            {"pagination": {}, "object_id_batch_equivalence": {}},
            observed_at=observed_at,
        ),
        "export-query-equivalence.json": output_envelope(
            "export-query-equivalence",
            {"equivalence": {}, "export_container": {}},
            observed_at=observed_at,
        ),
        "program-comparison.json": output_envelope(
            "program-comparison",
            {"comparison": {}, "program_sources": []},
            observed_at=observed_at,
        ),
        "content-change.json": output_envelope(
            "content-change",
            {"observations": [], "comparison": {}},
            observed_at=observed_at,
        ),
        "decision.json": decision_payload(
            recommendation="SUPPLEMENT",
            source_identity=source_identity,
            gates=gates,
            observed_at=observed_at,
        ),
        "validation-summary.json": output_envelope(
            "validation-summary",
            {"checks": [], "generated_outputs": [], "privacy_scan": "pass"},
            observed_at=observed_at,
        ),
    }
    for payload in payloads.values():
        validate_output(payload, schema)
        assert payload["contract_version"] == CONTRACT_VERSION

    first = write_output_package(tmp_path / "first", payloads, schema)
    second = write_output_package(tmp_path / "second", payloads, schema)

    assert first == second
    for name in payloads:
        assert (tmp_path / "first" / name).read_bytes() == (
            tmp_path / "second" / name
        ).read_bytes()


def test_invalid_output_contract_is_rejected_before_write(tmp_path: Path) -> None:
    schema = load_schema(SCHEMA_PATH)
    payload = output_envelope(
        "source-inventory",
        {
            "catalog_records": [],
            "source_identity": {},
            "endpoint_inventory": [],
            "redirect_outcomes": [],
        },
        observed_at="2026-07-19T00:00:00Z",
    )
    payload["contract_version"] = "unsupported"

    with pytest.raises(ValidationError):
        validate_output(payload, schema)
    assert not (tmp_path / "package").exists()


def test_failed_package_write_retains_prior_evidence(tmp_path: Path) -> None:
    prior = tmp_path / "prior"
    prior.mkdir()
    prior_file = prior / "decision.json"
    prior_file.write_text('{"recommendation":"SUPPLEMENT"}\n', encoding="utf-8")
    prior_hash = sha256_bytes(prior_file.read_bytes())
    schema = load_schema(SCHEMA_PATH)

    invalid = output_envelope(
        "schema-profile",
        {"layer": {}},
        observed_at="2026-07-19T00:00:00Z",
    )
    with pytest.raises(ValidationError):
        write_output_package(tmp_path / "failed-new", {"schema-profile.json": invalid}, schema)

    assert sha256_bytes(prior_file.read_bytes()) == prior_hash
    assert not (tmp_path / "failed-new").exists()


def test_normalize_scalar_preserves_ids_and_normalizes_dates() -> None:
    assert normalize_scalar("00123", logical_field="facility_number") == "00123"
    assert normalize_scalar(10.0, logical_field="capacity") == "10"
    assert normalize_scalar("01/02/2024", logical_field="closed_date") == "2024-01-02"
