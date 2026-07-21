from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from ccld_complaints.connectors.ccld_transparency_api.connector import (
    HttpArtifactResponse,
    PreservedArtifact,
    TransparencyApiConnector,
    TransparencyApiConnectorError,
    parse_bulk_csv,
    parse_detail_response,
    parse_report_list,
    report_helper_url,
    select_report_item,
    validate_governed_url,
    validate_report_helper_response,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import (
    BASE_URL,
    EXPORT_IDS,
    RCFE_EXPORT_ID,
    RCFE_HEADERS,
    STANDARD_HEADERS,
    expected_headers,
    normalize_bulk_row,
    preserve_prior_populated_values,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ccld_transparency_api"


class _FixtureTransport:
    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses
        self.requested_urls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> HttpArtifactResponse:
        assert timeout_seconds > 0
        self.requested_urls.append(url)
        media_type, body = self.responses[url]
        return HttpArtifactResponse(
            request_url=url,
            final_url=url,
            status=200,
            headers=(
                ("Content-Type", media_type),
                ("Content-Disposition", 'attachment; filename="source.csv"'),
                ("X-Public-Response-Metadata", "retained-public-metadata"),
            ),
            body=body,
        )


def test_exact_versioned_headers_cover_all_seven_exports() -> None:
    assert len(STANDARD_HEADERS) == 31
    assert len(RCFE_HEADERS) == 38
    assert RCFE_HEADERS[-1] == (
        "Complaint Info- Date, #Sub A, # Inc A, # Uns A, # Unf A, # TypeA, # TypeB ..."
    )
    for export_id in EXPORT_IDS:
        expected = RCFE_HEADERS if export_id == RCFE_EXPORT_ID else STANDARD_HEADERS
        assert expected_headers(export_id) == expected
        parsed = parse_bulk_csv(
            _csv_bytes(export_id, [_fixed_row(export_id)]),
            export_id=export_id,
            reference_year=2026,
        )
        assert parsed.headers == expected
        assert parsed.rejection_reasons == ()


def test_csv_parser_preserves_quoted_commas_leading_zero_and_standard_block_order() -> None:
    row = _fixed_row(
        "FosterFamilyAgencies",
        facility_number="001234567",
        facility_name="Synthetic Home, North",
    )
    row.extend(["01/02/2026", "2", "3", "4", "5", "6"])
    parsed = parse_bulk_csv(
        _csv_bytes("FosterFamilyAgencies", [row]),
        export_id="FosterFamilyAgencies",
        reference_year=2026,
    )
    facility = parsed.rows[0]
    assert facility.facility_number == "001234567"
    assert facility.raw_record["Facility Name"] == "Synthetic Home, North"
    assert [block.ordinal for block in facility.complaint_blocks] == [1]
    assert facility.complaint_blocks[0].values == {
        "date": "01/02/2026",
        "substantiated_allegations": "2",
        "inconclusive_allegations": "3",
        "unsubstantiated_allegations": "4",
        "type_a_citations": "5",
        "type_b_citations": "6",
    }


def test_csv_parser_supports_rcfe_seven_field_blocks_zero_and_partial_blocks() -> None:
    rcfe = _fixed_row(RCFE_EXPORT_ID, facility_number="015601302")
    rcfe.extend(["02/03/2026", "1", "2", "3", "4", "5", "6"])
    no_complaints = _fixed_row(RCFE_EXPORT_ID, facility_number="015601303")
    no_complaints.append("No Complaints")
    partial = _fixed_row(RCFE_EXPORT_ID, facility_number="015601304")
    partial.extend(["03/04/2026", "1", "2"])
    parsed = parse_bulk_csv(
        _csv_bytes(RCFE_EXPORT_ID, [rcfe, no_complaints, partial]),
        export_id=RCFE_EXPORT_ID,
        reference_year=2026,
    )
    assert parsed.rows[0].complaint_blocks[0].values["unfounded_allegations"] == "4"
    assert parsed.rows[0].complaint_blocks[0].raw_values == tuple(rcfe[-7:])
    assert parsed.rows[1].complaint_blocks == ()
    assert parsed.rows[2].trailing_values == ("03/04/2026", "1", "2")
    assert parsed.rows[2].quarantine_categories == ("malformed_trailing_complaint_block",)


def test_status_closed_date_future_date_and_raw_values_remain_separate() -> None:
    row = _fixed_row(
        "ChildCareCenters",
        status="Licensed",
        closed_date="01/02/2099",
    )
    parsed = parse_bulk_csv(
        _csv_bytes("ChildCareCenters", [row]),
        export_id="ChildCareCenters",
        reference_year=2026,
    ).rows[0]
    assert parsed.raw_record["Facility Status"] == "Licensed"
    assert parsed.normalized_record["bulk_status"]["value"] == "Licensed"
    assert parsed.normalized_record["closed_date"]["value"] == "01/02/2099"
    assert "bulk status and Closed Date require reconciliation" in parsed.warnings
    assert "closed_date contains a suspicious future date" in parsed.warnings
    same_year = parse_bulk_csv(
        _csv_bytes("ChildCareCenters", [row]),
        export_id="ChildCareCenters",
        reference_year=2099,
    ).rows[0]
    assert "closed_date contains a suspicious future date" not in same_year.warnings


def test_populated_address_and_telephone_survive_blank_or_placeholder_observations() -> None:
    prior = normalize_bulk_row(_raw_record(address="100 Synthetic Way", telephone="555-0100"))
    current = normalize_bulk_row(_raw_record(address="Unavailable", telephone=""))
    resolved = preserve_prior_populated_values(current, prior)
    assert resolved["facility_address"]["value"] == "100 Synthetic Way"
    assert resolved["facility_address"]["preserved_from_prior"] is True
    assert resolved["facility_address"]["superseding_observation"]["state"] == "placeholder"
    assert resolved["facility_telephone_number"]["value"] == "555-0100"
    assert current["facility_address"]["raw"] == "Unavailable"


def test_detail_sentinel_contact_administrator_status_and_unknown_type_are_distinct() -> None:
    sentinel = parse_detail_response(
        (FIXTURE_ROOT / "facility-detail-sentinel.json").read_bytes(),
        facility_number="000123456",
    )
    assert sentinel.sentinel is True
    assert sentinel.quarantine_categories == ("facility_detail_sentinel",)

    detail = parse_detail_response(
        json.dumps(
            {
                "FacilityNumber": "000123456",
                "CONTACT": "Synthetic Contact",
                "Facility Administrator": "Synthetic Administrator",
                "STATUS": "PROBATIONARY",
                "TYPE": "999",
            }
        ).encode(),
        facility_number="000123456",
        known_type_codes=frozenset({"733", "777"}),
    )
    assert detail.contact == "Synthetic Contact"
    assert detail.facility_administrator == "Synthetic Administrator"
    assert detail.detail_status == "PROBATIONARY"
    assert detail.facility_type_code == "999"
    assert detail.quarantine_categories == ("unknown_facility_type_code",)
    valid_zero_instance_type = parse_detail_response(
        b'{"FacilityNumber":"000123456","TYPE":"777"}',
        facility_number="000123456",
        known_type_codes=frozenset({"733", "777"}),
    )
    assert valid_zero_instance_type.quarantine_categories == ()


def test_report_list_rejects_raw_reportpage_and_bounds_helper_index() -> None:
    items = parse_report_list(
        (FIXTURE_ROOT / "facility-reports-list.json").read_bytes(),
        facility_number="000123456",
    )
    assert len(items) == 1
    assert items[0].raw_record["REPORTPAGE_REJECTED"] is True
    assert report_helper_url("000123456", 0).endswith("facNum=000123456&inx=0")
    with pytest.raises(TransparencyApiConnectorError, match="nonnegative"):
        select_report_item(items, index=-1)
    with pytest.raises(TransparencyApiConnectorError, match="outside"):
        select_report_item(items, index=1)
    with pytest.raises(TransparencyApiConnectorError, match="Prohibited"):
        validate_governed_url("https://fakeout.gov/report")
    with pytest.raises(TransparencyApiConnectorError, match="Prohibited"):
        validate_governed_url(f"{BASE_URL}/FacilitySearch")


def test_report_helper_validates_html_and_quarantines_list_mismatches() -> None:
    selected = parse_report_list(
        (FIXTURE_ROOT / "facility-reports-list.json").read_bytes(),
        facility_number="000123456",
    )[0]
    body = (FIXTURE_ROOT / "facility-report-valid.html").read_bytes()
    artifact = _artifact(body)
    validated = validate_report_helper_response(
        artifact,
        body,
        selected=selected,
        report_list_sha256="1" * 64,
        report_count=1,
    )
    assert validated.quarantine_categories == ()
    assert validated.report_list_sha256 == "1" * 64
    assert validated.report_count == 1
    mismatch = body.replace(b"000123456", b"999999999")
    assert validate_report_helper_response(
        _artifact(mismatch),
        mismatch,
        selected=selected,
        report_list_sha256="1" * 64,
        report_count=1,
    ).quarantine_categories == ("report_list_helper_facility_mismatch",)
    with pytest.raises(TransparencyApiConnectorError, match="not HTML"):
        validate_report_helper_response(
            PreservedArtifact(**{**artifact.__dict__, "media_type": "application/json"}),
            body,
            selected=selected,
            report_list_sha256="1" * 64,
            report_count=1,
        )


def test_capture_fetches_exact_complete_source_family_and_preserves_raw_bytes(
    tmp_path: Path,
) -> None:
    responses = _source_family_responses()
    transport = _FixtureTransport(responses)
    capture = TransparencyApiConnector(transport=transport).capture_snapshot(
        tmp_path, retrieved_at="2026-07-21T00:00:00+00:00"
    )
    manifest = json.loads(capture.manifest_path.read_text(encoding="utf-8"))
    assert len(capture.artifacts) == 9
    assert len(transport.requested_urls) == 9
    assert manifest["source_identity"]["bulk_export_ids"] == list(EXPORT_IDS)
    assert manifest["source_identity"]["facility_search_used"] is False
    for artifact in capture.artifacts:
        assert (capture.evidence_directory / artifact.raw_ref).read_bytes() == responses[
            artifact.request_url
        ][1]
        assert artifact.byte_count == len(responses[artifact.request_url][1])
        assert artifact.excluded_header_names == ()
        assert "retained-public-metadata" in capture.manifest_path.read_text(encoding="utf-8")


def _fixed_row(
    export_id: str,
    *,
    facility_number: str = "900000001",
    facility_name: str = "Synthetic Facility",
    status: str = "Licensed",
    closed_date: str = "",
    address: str = "100 Synthetic Way",
    telephone: str = "555-0100",
) -> list[str]:
    headers = expected_headers(export_id)[:-1]
    values = {header: "" for header in headers}
    values.update(
        {
            "Facility Type": "SYNTHETIC TYPE",
            "Facility Number": facility_number,
            "Facility Name": facility_name,
            "Licensee": "Synthetic Licensee",
            "Facility Administrator": "Synthetic Administrator",
            "Facility Telephone Number": telephone,
            "Facility Address": address,
            "Facility City": "Fixture City",
            "Facility State": "CA",
            "Facility Zip": "90000",
            "County Name": "Fixture County",
            "Regional Office": "Fixture Office",
            "Facility Capacity": "10",
            "Facility Status": status,
            "License First Date": "01/01/2020",
            "Closed Date": closed_date,
            "Last Visit Date": "01/01/2026",
        }
    )
    return [values[header] for header in headers]


def _raw_record(*, address: str, telephone: str) -> dict[str, str]:
    row = _fixed_row("FosterFamilyAgencies", address=address, telephone=telephone)
    return dict(zip(STANDARD_HEADERS[:-1], row, strict=True))


def _csv_bytes(export_id: str, rows: list[list[str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(expected_headers(export_id))
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _source_family_responses(
    *,
    row_overrides: dict[str, list[list[str]]] | None = None,
) -> dict[str, tuple[str, bytes]]:
    overrides = row_overrides or {}
    responses: dict[str, tuple[str, bytes]] = {}
    for index, export_id in enumerate(EXPORT_IDS, start=1):
        rows = overrides.get(
            export_id,
            [_fixed_row(export_id, facility_number=f"9{index:08d}")],
        )
        url = f"{BASE_URL}/DownloadStateData?id={export_id}"
        responses[url] = ("text/csv; charset=utf-8", _csv_bytes(export_id, rows))
    responses[f"{BASE_URL}/Group/"] = (
        "application/json",
        b'[{"TYPE":"733","DESCRIPTION":"Synthetic"},{"TYPE":"777","DESCRIPTION":"Zero"}]',
    )
    responses[f"{BASE_URL}/CACounty"] = (
        "application/json",
        b'[{"CODE":"00","NAME":"Fixture County"}]',
    )
    return responses


def _artifact(body: bytes) -> PreservedArtifact:
    url = report_helper_url("000123456", 0)
    return PreservedArtifact(
        artifact_id="facility-report-000123456-0",
        endpoint_kind="report_document",
        export_id=None,
        request_url=url,
        final_url=url,
        retrieved_at="2026-07-21T00:00:00+00:00",
        status=200,
        response_headers=(("Content-Type", "text/html"),),
        excluded_header_names=(),
        media_type="text/html",
        content_disposition=None,
        byte_count=len(body),
        sha256="0" * 64,
        raw_ref="reports/000123456/0.html",
    )
