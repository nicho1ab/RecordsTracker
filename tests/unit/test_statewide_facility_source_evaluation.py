from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from ccld_complaints.statewide_facility_source_evaluation import (
    CONTRACT_VERSION,
    HttpResponse,
    analyze_pagination,
    assert_safe_output,
    compare_content_snapshots,
    compare_row_sets,
    compare_source_coverage,
    exact_value_contexts,
    extract_zip_members,
    fetch_and_preserve,
    inventory_code_labels,
    load_output_schema,
    ordered_schema_fingerprint,
    output_envelope,
    parse_csv_bytes,
    parse_json_bytes,
    profile_facility_rows,
    safe_endpoint_identity,
    sanitize_url,
    value_state,
    write_csv_output,
    write_json_output,
)
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_DIR = Path("tests/fixtures/source_profiling/issue_490")
SCHEMA_PATH = Path("schemas/issue-490-statewide-facility-source-profile.schema.json")


class FakeTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse:
        self.calls.append((url, timeout_seconds))
        return self.response


def _json_fixture(name: str) -> dict[str, object]:
    return parse_json_bytes((FIXTURE_DIR / name).read_bytes())


def _page_rows(*names: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in names:
        payload = _json_fixture(name)
        for feature in payload["features"]:  # type: ignore[index,union-attr]
            rows.append(dict(feature["attributes"]))  # type: ignore[index]
    return rows


def test_fetch_preserves_original_bytes_before_parsing_and_hashes_stored_bytes(
    tmp_path: Path,
) -> None:
    content = b'{"raw":true}\n'
    response = HttpResponse(
        request_url="https://public.example.test/source",
        final_url="https://public.example.test/source",
        status=200,
        content_type="application/json",
        body=content,
    )
    transport = FakeTransport(response)
    path = tmp_path / "raw" / "response.json"

    artifact = fetch_and_preserve(
        endpoint_id="synthetic",
        request_url=response.request_url,
        artifact_path=path,
        artifact_ref="data/raw/source-profiling/issue-490/synthetic/response.json",
        transport=transport,
        retrieved_at="2026-07-19T00:00:00Z",
    )

    assert path.read_bytes() == content
    assert artifact.sha256 == sha256_bytes(content)
    assert artifact.byte_count == len(content)
    assert artifact.artifact_ref.startswith("data/raw/")
    assert transport.calls == [(response.request_url, 60.0)]
    assert parse_json_bytes(path.read_bytes()) == {"raw": True}


def test_snapshot_never_overwrites_prior_bytes(tmp_path: Path) -> None:
    path = tmp_path / "existing.json"
    path.write_bytes(b"prior")
    transport = FakeTransport(
        HttpResponse(
            request_url="https://public.example.test/source",
            final_url="https://public.example.test/source",
            status=200,
            content_type="application/json",
            body=b"replacement",
        )
    )

    with pytest.raises(FileExistsError):
        fetch_and_preserve(
            endpoint_id="synthetic",
            request_url="https://public.example.test/source",
            artifact_path=path,
            artifact_ref="data/raw/existing.json",
            transport=transport,
        )

    assert path.read_bytes() == b"prior"


def test_endpoint_identity_and_sensitive_query_sanitization_are_deterministic() -> None:
    url = (
        "https://S3.AMAZONAWS.COM:443/example/object.zip?"
        "X-Amz-Credential=private&X-Amz-Signature=private&layers=0#fragment"
    )

    assert safe_endpoint_identity(url) == "https://s3.amazonaws.com/example/object.zip"
    assert sanitize_url(url) == "https://S3.AMAZONAWS.COM:443/example/object.zip?layers=0"


def test_schema_fingerprint_includes_order_types_and_changed_domain() -> None:
    layer = _json_fixture("layer.json")
    changed = _json_fixture("layer-changed-domain.json")
    fields = layer["fields"]  # type: ignore[index]

    fingerprint = ordered_schema_fingerprint(fields)  # type: ignore[arg-type]

    assert fingerprint == ordered_schema_fingerprint(fields)  # type: ignore[arg-type]
    assert fingerprint != ordered_schema_fingerprint(list(reversed(fields)))  # type: ignore[arg-type]
    assert fingerprint != ordered_schema_fingerprint(changed["fields"])  # type: ignore[arg-type,index]


def test_pagination_covers_each_object_once_and_observes_terminal_page() -> None:
    pages = [
        _json_fixture("page-0.json"),
        _json_fixture("page-1.json"),
        _json_fixture("page-terminal.json"),
    ]

    result = analyze_pagination(pages, object_id_field="OBJECTID", expected_object_ids=[1, 2, 3])

    assert result["status"] == "pass"
    assert result["page_counts"] == [2, 1, 0]
    assert result["unique_object_id_count"] == 3
    assert result["terminal_page_observed"] is True


@pytest.mark.parametrize(
    ("pages", "expected_ids", "failure_key"),
    [
        (("page-0.json", "page-0.json", "page-terminal.json"), [1, 2], "duplicate_object_ids"),
        (("page-0.json", "page-terminal.json"), [1, 2, 3], "omitted_object_ids"),
    ],
)
def test_pagination_detects_duplicate_and_omitted_pages(
    pages: tuple[str, ...], expected_ids: list[int], failure_key: str
) -> None:
    result = analyze_pagination(
        [_json_fixture(name) for name in pages],
        object_id_field="OBJECTID",
        expected_object_ids=expected_ids,
    )

    assert result["status"] == "fail"
    assert result[failure_key]


def test_equivalence_uses_identifiers_and_row_fingerprints_not_counts_only() -> None:
    baseline = _page_rows("page-0.json")
    same_count_changed = _page_rows("page-equal-count-changed.json")
    fields = [
        "OBJECTID",
        "facility_number",
        "facility_type_code",
        "facility_type_label",
        "status",
    ]

    result = compare_row_sets(
        baseline,
        same_count_changed,
        identifier_field="facility_number",
        compared_fields=fields,
    )

    assert result["left_row_count"] == result["right_row_count"] == 2
    assert result["verdict"] == "not_equivalent"
    assert result["left_only_identifiers"] == ["100002"]
    assert result["right_only_identifiers"] == ["100004"]
    assert result["changed_identifiers"] == ["100001"]


def test_equivalence_fails_omission_duplication_value_and_schema_mismatch() -> None:
    rows = _page_rows("page-0.json", "page-1.json")
    fields = ["facility_number", "status"]

    omitted = compare_row_sets(
        rows,
        rows[:-1],
        identifier_field="facility_number",
        compared_fields=fields,
    )
    duplicated = compare_row_sets(
        rows,
        [*rows, rows[0]],
        identifier_field="facility_number",
        compared_fields=fields,
    )
    changed_rows = [dict(row) for row in rows]
    changed_rows[0]["status"] = "CLOSED"
    changed = compare_row_sets(
        rows,
        changed_rows,
        identifier_field="facility_number",
        compared_fields=fields,
    )
    schema = compare_row_sets(
        rows,
        rows,
        identifier_field="facility_number",
        compared_fields=fields,
        left_schema=["facility_number", "status"],
        right_schema=["status", "facility_number"],
    )

    assert omitted["status"] == "fail"
    assert duplicated["duplicate_identifiers_right"] == ["100001"]
    assert changed["changed_identifiers"] == ["100001"]
    assert schema["schema_match"] is False


def test_code_label_inventory_preserves_raw_code_and_does_not_assume_733() -> None:
    rows = _page_rows("page-0.json", "page-1.json")
    rows.append(
        {
            "facility_number": "100004",
            "facility_type_code": 733,
            "facility_type_label": "",
        }
    )

    inventory = inventory_code_labels(
        rows,
        code_field="facility_type_code",
        label_field="facility_type_label",
        source_id="synthetic",
    )
    code_733 = [entry for entry in inventory if entry["raw_code"] == "733"]

    assert code_733 == [
        {
            "source_id": "synthetic",
            "code_field": "facility_type_code",
            "label_field": "facility_type_label",
            "raw_code": "733",
            "raw_label": "",
            "record_count": 1,
            "evidence_status": "unresolved",
        }
    ]


def test_cross_source_states_and_conflicts_remain_distinct() -> None:
    assert value_state(present=False, value=None) == "absent"
    assert value_state(present=True, value=None) == "null"
    assert value_state(present=True, value=" ") == "blank"
    assert value_state(present=True, value="not-a-number", validator=str.isdigit) == "invalid"
    assert value_state(present=True, value="12", validator=str.isdigit) == "populated"

    left = [
        {"id": "1", "name": "Synthetic One", "county": "Alpha"},
        {"id": "2", "name": "Synthetic Two", "county": ""},
    ]
    right = [
        {"facility_id": "1", "facility_name": "Synthetic One Changed", "county_name": "Alpha"},
        {"facility_id": "3", "facility_name": "Synthetic Scope Only", "county_name": "Beta"},
    ]

    summary, conflicts = compare_source_coverage(
        left,
        right,
        left_id_field="id",
        right_id_field="facility_id",
        field_pairs=(("name", "facility_name"), ("county", "county_name")),
    )

    assert summary == {
        "left_row_count": 2,
        "right_row_count": 2,
        "shared_identifier_count": 1,
        "left_only_identifier_count": 1,
        "right_only_identifier_count": 1,
        "conflicting_nonblank_value_count": 1,
    }
    assert conflicts[0]["category"] == "conflicting_nonblank"
    assert "Synthetic One" not in json.dumps(conflicts)


def test_profile_retains_null_blank_invalid_and_date_observations() -> None:
    fields, rows, encoding, warnings = parse_csv_bytes((FIXTURE_DIR / "download.csv").read_bytes())

    profile = profile_facility_rows(
        rows,
        source_id="synthetic",
        identifier_field="facility_number",
        type_field="facility_type_label",
        status_field="status",
        fields=fields,
    )

    assert encoding == "utf-8-sig"
    assert warnings == []
    assert profile["row_count"] == 3
    assert profile["missing_facility_identifier_count"] == 0
    assert profile["status_counts"] == [
        {"raw_value": "CLOSED", "record_count": 1},
        {"raw_value": "INACTIVE", "record_count": 1},
        {"raw_value": "LICENSED", "record_count": 1},
    ]
    assert profile["date_formats"]["closed_date"] == {"ISO-like": 1}


def test_exact_value_contexts_do_not_treat_733_as_a_type_without_field_evidence() -> None:
    sources = {
        "source-a": [{"facility_number": "733", "facility_type": "Synthetic Center"}],
        "source-b": [{"facility_number": "100001", "facility_type": "733"}],
    }

    contexts = exact_value_contexts(sources, "733")

    assert contexts == [
        {"source_id": "source-a", "field": "facility_number", "record_count": 1},
        {"source_id": "source-b", "field": "facility_type", "record_count": 1},
    ]


def test_repeated_content_comparison_separates_metadata_bytes_schema_rows_and_values() -> None:
    previous = [{"id": "1", "status": "LICENSED"}]
    current = [{"id": "1", "status": "CLOSED"}]

    result = compare_content_snapshots(
        previous,
        current,
        identifier_field="id",
        fields=["id", "status"],
        previous_bytes_sha256="a",
        current_bytes_sha256="b",
        previous_schema_fingerprint="schema",
        current_schema_fingerprint="schema",
        metadata_changed=True,
    )

    assert result["metadata_changed"] is True
    assert result["byte_changed"] is True
    assert result["schema_changed"] is False
    assert result["row_set_changed"] is False
    assert result["field_value_changed"] is True


def test_all_json_output_types_validate_and_write_deterministically(tmp_path: Path) -> None:
    schema = load_output_schema(SCHEMA_PATH)
    data_by_type: dict[str, dict[str, object]] = {
        "source-endpoints": {
            "endpoints": [],
            "candidate_identities": [],
            "proposed_endpoints": [],
        },
        "snapshot-manifest": {"artifacts": [], "sanitized_redirect_chain": []},
        "schema-profile": {"sources": []},
        "pagination-equivalence": {
            "arcgis": {},
            "datastores": [],
            "download_service_equivalence": {},
        },
        "facility-profile": {"sources": [], "aggregate": {}, "code_733": {}},
        "content-change": {"comparisons": []},
        "validation-summary": {"checks": [], "deliverables": []},
    }
    for output_type, data in data_by_type.items():
        payload = output_envelope(
            output_type,
            data,
            generated_at="2026-07-19T00:00:00Z",
        )
        first_path = tmp_path / "first" / f"{output_type}.json"
        second_path = tmp_path / "second" / f"{output_type}.json"
        first_hash = write_json_output(first_path, payload, schema)
        second_hash = write_json_output(second_path, payload, schema)
        assert first_hash == second_hash
        assert first_path.read_bytes() == second_path.read_bytes()
        assert json.loads(first_path.read_text(encoding="utf-8"))["contract_version"] == (
            CONTRACT_VERSION
        )


def test_output_contract_rejects_unversioned_or_unknown_status() -> None:
    schema = load_output_schema(SCHEMA_PATH)
    payload = output_envelope(
        "schema-profile", {"sources": []}, generated_at="2026-07-19T00:00:00Z"
    )
    payload["contract_version"] = "unknown"

    with pytest.raises(ValidationError):
        write_json_output(Path("unused.json"), payload, schema)
    with pytest.raises(ValueError, match="Unsupported finite status"):
        output_envelope(
            "schema-profile",
            {"sources": []},
            generated_at="2026-07-19T00:00:00Z",
            status="maybe",
        )


def test_csv_output_is_stably_ordered_and_rejects_secret_like_or_personal_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "safe.csv"
    digest = write_csv_output(
        path,
        ["source_id", "status"],
        [
            {"source_id": "b", "status": "warning"},
            {"source_id": "a", "status": "pass"},
        ],
    )

    assert path.read_text(encoding="utf-8") == (
        "source_id,status\na,pass\nb,warning\n"
    )
    assert digest == sha256_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="secret-like"):
        assert_safe_output("X-Amz-Signature=not-safe")
    with pytest.raises(ValueError, match="personal path"):
        assert_safe_output("C:\\Users\\someone\\source.json")


def test_failure_fixture_covers_bounded_live_boundary_without_a_network_call() -> None:
    scenarios = _json_fixture("failure-scenarios.json")

    assert scenarios["redirect"]["status"] == 302  # type: ignore[index]
    assert scenarios["rate_limit"]["status"] == 429  # type: ignore[index]
    assert scenarios["timeout"] == {"kind": "timeout"}
    assert scenarios["malformed_response"] == "{not-json"
    assert scenarios["unsupported_format"]["status"] == 400  # type: ignore[index]
    with pytest.raises(json.JSONDecodeError):
        parse_json_bytes(str(scenarios["malformed_response"]).encode("utf-8"))


def test_fixture_hash_uses_git_normalized_lf_bytes() -> None:
    content = (FIXTURE_DIR / "download.csv").read_bytes()

    assert b"\r\n" not in content
    assert sha256_bytes(content) == (
        "20092b7a7f762e8e1021c9abdc78802b175872aa6f9ae086321db4b1bbf41476"
    )


def test_zip_member_hashes_are_original_member_bytes() -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("b.csv", b"b\n2\n")
        archive.writestr("a.csv", b"a\n1\n")

    members = extract_zip_members(buffer.getvalue())

    assert [member["name"] for member in members] == ["a.csv", "b.csv"]
    assert members[0]["sha256"] == sha256_bytes(b"a\n1\n")
