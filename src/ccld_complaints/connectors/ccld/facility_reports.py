from __future__ import annotations

import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.extraction.dates import days_between, parse_date_or_none
from ccld_complaints.quality.validate import validate_schema
from ccld_complaints.utils.hash import sha256_bytes

BASE_URL = "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
SOURCE_ID = "ccld"
DETERMINISTIC_METHOD = "ccld_facility_report_html_labels"
ALLOWED_FINDINGS = (
    "Substantiated",
    "Unsubstantiated",
    "Inconclusive",
    "Dismissed",
    "No deficiency cited",
    "Deficiency cited",
    "Unknown",
)


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []

    def handle_data(self, data: str) -> None:
        for line in data.splitlines():
            cleaned = _clean_text(line)
            if cleaned:
                self.lines.append(cleaned)


class CcldFacilityReportsConnector:
    connector_name = "ccld_facility_reports"
    connector_version = "0.1.0"

    def __init__(
        self,
        facility_number: str = "157806098",
        report_index: int = 3,
        raw_dir: Path = Path("data/raw/ccld"),
        schema_dir: Path = Path("schemas"),
    ) -> None:
        self.facility_number = facility_number
        self.report_index = report_index
        self.raw_dir = raw_dir
        self.schema_dir = schema_dir

    def discover(self) -> list[str]:
        query = urlencode({"facNum": self.facility_number, "inx": self.report_index})
        return [f"{BASE_URL}?{query}"]

    def fetch(self, source_url: str) -> bytes:
        request = Request(source_url, headers={"User-Agent": "ccld-complaints-poc/0.1"})
        with urlopen(request, timeout=30) as response:
            return cast(bytes, response.read())

    def store_raw(self, source_url: str, content: bytes) -> SourceDocument:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = self.raw_dir / f"{self.facility_number}_inx{self.report_index}.html"
        raw_path.write_bytes(content)
        return SourceDocument(
            source_url=source_url,
            raw_path=raw_path,
            raw_sha256=sha256_bytes(content),
            retrieved_at=datetime.now(UTC).isoformat(),
            content_type="text/html",
        )

    def extract(self, document: SourceDocument) -> dict[str, object]:
        html = document.raw_path.read_text(encoding="utf-8")
        lines = _html_lines(html)
        source_url_fields = _source_url_fields(document.source_url)

        complaint_received_date = _iso_date(_complaint_received_date(lines))
        report_date = _iso_date(_value_after_label(lines, "Report Date:"))

        return {
            "source_url": document.source_url,
            "raw_path": document.raw_path.as_posix(),
            "raw_sha256": document.raw_sha256,
            "retrieved_at": document.retrieved_at,
            "content_type": document.content_type,
            "report_index": source_url_fields["report_index"],
            "facility_number": _value_after_label(lines, "FACILITY NUMBER:"),
            "facility_name": _value_after_label(lines, "FACILITY NAME:"),
            "report_type": _report_type(lines),
            "report_date": report_date,
            "date_signed": _iso_date(_value_after_label(lines, "Date Signed:")),
            "complaint_received_date": complaint_received_date,
            "complaint_control_number": _value_after_label(lines, "COMPLAINT CONTROL NUMBER:"),
            "allegations": _allegations(lines),
            "finding": _finding(lines),
            "visit_date": _iso_date(_value_after_label(lines, "VISIT DATE:")),
            "days_received_to_report": days_between(
                parse_date_or_none(complaint_received_date),
                parse_date_or_none(report_date),
            ),
        }

    def normalize(self, extracted: dict[str, object]) -> dict[str, object]:
        facility_number = _required_str(extracted, "facility_number")
        facility_name = _required_str(extracted, "facility_name")
        complaint_control_number = _optional_str(extracted, "complaint_control_number")
        report_index = cast(int | None, extracted.get("report_index"))

        document_id = f"ccld-{facility_number}-inx-{report_index}"
        facility_id = f"ccld-facility-{facility_number}"
        complaint_id = f"ccld-complaint-{complaint_control_number or document_id}"
        finding = _optional_str(extracted, "finding") or "Unknown"
        allegations = cast(list[str], extracted.get("allegations", []))

        normalized_allegations = [
            {
                "allegation_id": f"{complaint_id}-allegation-{index}",
                "complaint_id": complaint_id,
                "allegation_text": allegation,
                "allegation_category": None,
                "finding": finding,
                "extraction_confidence": 1.0,
            }
            for index, allegation in enumerate(allegations, start=1)
        ]

        return {
            "facility": {
                "facility_id": facility_id,
                "source_id": SOURCE_ID,
                "external_facility_number": facility_number,
                "facility_name": facility_name,
                "facility_type": None,
                "licensee_name": None,
                "county": None,
                "status": None,
                "capacity": None,
                "regional_office": None,
            },
            "source_document": {
                "document_id": document_id,
                "source_id": SOURCE_ID,
                "facility_id": facility_id,
                "source_url": _required_str(extracted, "source_url"),
                "retrieved_at": _optional_str(extracted, "retrieved_at")
                or datetime.now(UTC).isoformat(),
                "raw_sha256": _required_str(extracted, "raw_sha256"),
                "connector_name": self.connector_name,
                "connector_version": self.connector_version,
                "raw_path": _optional_str(extracted, "raw_path"),
                "document_type": _optional_str(extracted, "report_type"),
                "report_index": report_index,
                "http_status": None,
                "content_type": _optional_str(extracted, "content_type"),
            },
            "complaint": {
                "complaint_id": complaint_id,
                "facility_id": facility_id,
                "document_id": document_id,
                "complaint_control_number": complaint_control_number,
                "complaint_received_date": _optional_str(extracted, "complaint_received_date"),
                "first_investigation_activity_date": None,
                "visit_date": _optional_str(extracted, "visit_date"),
                "report_date": _optional_str(extracted, "report_date"),
                "date_signed": _optional_str(extracted, "date_signed"),
                "finding": finding,
                "days_received_to_first_activity": None,
                "days_received_to_report": cast(
                    int | None, extracted.get("days_received_to_report")
                ),
                "extraction_confidence": 1.0,
            },
            "allegations": normalized_allegations,
            "extraction_audit": _audit_records(document_id, extracted),
        }

    def validate(self, normalized: dict[str, object]) -> None:
        validate_schema(
            cast(dict[str, Any], normalized["facility"]), self.schema_dir / "facility.schema.json"
        )
        validate_schema(
            cast(dict[str, Any], normalized["source_document"]),
            self.schema_dir / "source_document.schema.json",
        )
        validate_schema(
            cast(dict[str, Any], normalized["complaint"]), self.schema_dir / "complaint.schema.json"
        )
        for allegation in cast(list[dict[str, Any]], normalized["allegations"]):
            validate_schema(allegation, self.schema_dir / "allegation.schema.json")
        for audit_record in cast(list[dict[str, Any]], normalized["extraction_audit"]):
            validate_schema(audit_record, self.schema_dir / "extraction_audit.schema.json")

    def emit(self, normalized: dict[str, object]) -> None:
        self.validate(normalized)


def _html_lines(html: str) -> list[str]:
    parser = _HtmlTextParser()
    parser.feed(html)
    return parser.lines


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _source_url_fields(source_url: str) -> dict[str, int | None]:
    query = parse_qs(urlparse(source_url).query)
    report_index = query.get("inx", [None])[0]
    return {"report_index": int(report_index) if report_index is not None else None}


def _value_after_label(lines: list[str], label: str) -> str | None:
    normalized_label = label.casefold()
    for index, line in enumerate(lines):
        normalized_line = line.casefold()
        if normalized_line == normalized_label:
            return _next_value(lines, index)
        if normalized_line.startswith(normalized_label):
            value = _clean_text(line[len(label) :])
            return value or _next_value(lines, index)
    return None


def _next_value(lines: list[str], index: int) -> str | None:
    for value in lines[index + 1 :]:
        if not value.endswith(":"):
            return value
    return None


def _report_type(lines: list[str]) -> str | None:
    for line in lines:
        if line == "COMPLAINT INVESTIGATION REPORT":
            return line
    return None


def _complaint_received_date(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        if "complaint received in our office on" in line.casefold():
            return _next_value(lines, index)
    return None


def _allegations(lines: list[str]) -> list[str]:
    start = _line_index(lines, "ALLEGATION(S):")
    end = _line_index(lines, "INVESTIGATION FINDINGS:")
    if start is None or end is None:
        return []

    allegations: list[str] = []
    for line in lines[start + 1 : end]:
        if not line.isdigit():
            allegations.append(line)
    return allegations


def _line_index(lines: list[str], value: str) -> int | None:
    for index, line in enumerate(lines):
        if line.casefold() == value.casefold():
            return index
    return None


def _finding(lines: list[str]) -> str:
    for line in lines:
        for finding in ALLOWED_FINDINGS:
            if line.casefold() == finding.casefold():
                return finding
    return "Unknown"


def _iso_date(value: str | None) -> str | None:
    parsed = parse_date_or_none(value)
    return parsed.isoformat() if parsed is not None else None


def _required_str(extracted: dict[str, object], field_name: str) -> str:
    value = _optional_str(extracted, field_name)
    if value is None:
        raise ValueError(f"Missing required extracted field: {field_name}")
    return value


def _optional_str(extracted: dict[str, object], field_name: str) -> str | None:
    value = extracted.get(field_name)
    return value if isinstance(value, str) else None


def _audit_records(document_id: str, extracted: dict[str, object]) -> list[dict[str, object]]:
    field_names = (
        "facility_number",
        "facility_name",
        "report_type",
        "report_date",
        "date_signed",
        "complaint_received_date",
        "complaint_control_number",
        "allegations",
        "finding",
        "visit_date",
        "days_received_to_report",
    )
    records: list[dict[str, object]] = []
    for field_name in field_names:
        value = extracted.get(field_name)
        records.append(
            {
                "audit_id": f"{document_id}-{field_name}",
                "document_id": document_id,
                "field_name": field_name,
                "extraction_method": DETERMINISTIC_METHOD,
                "extractor_version": CcldFacilityReportsConnector.connector_version,
                "extracted_value": _audit_value(value),
                "confidence": 1.0 if value is not None else 0.0,
                "source_text": None,
                "source_section": None,
                "warning": None if value is not None else "Field was not found in source report.",
            }
        )
    return records


def _audit_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)