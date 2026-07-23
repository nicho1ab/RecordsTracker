from __future__ import annotations

import csv
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from ccld_complaints.connectors.base import SourceDocument, SourceDocumentCandidate
from ccld_complaints.extraction.dates import days_between, parse_date_or_none
from ccld_complaints.quality.validate import validate_schema
from ccld_complaints.storage.sqlite import write_normalized_records
from ccld_complaints.utils.hash import sha256_bytes

BASE_URL = "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
FACILITY_DETAIL_URL = "https://www.ccld.dss.ca.gov/carefacilitysearch/FacDetail"
SOURCE_ID = "ccld"
# Absolute path to schema files so validate_schema works regardless of the
# process working directory (e.g. inside a Docker container whose WORKDIR is
# not the repo root).
_SCHEMA_DIR = Path(__file__).resolve().parents[4] / "schemas"
DETERMINISTIC_METHOD = "ccld_facility_report_html_labels"
LIVE_REQUEST_TIMEOUT_SECONDS = 30
LIVE_USER_AGENT = "ccld-complaints-poc/0.1 (explicit-user-invoked-public-data-fetch)"
ALLOWED_FINDINGS = (
    "Substantiated",
    "Unsubstantiated",
    "Inconclusive",
    "Dismissed",
    "No deficiency cited",
    "Deficiency cited",
    "Unknown",
)
NUMBERED_ALLEGATION_PREFIX_RE = re.compile(
    r"^\s*(?:allegation\s*)?\d+\s*(?:[.)\-:]|$)\s*",
    re.IGNORECASE,
)
FINDING_INLINE_LABEL_RE = re.compile(r"^finding\s*[-:]\s*(.+)$", re.IGNORECASE)
SOURCE_DATE_TOKEN_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
INVESTIGATION_ACTIVITY_CUE_RE = re.compile(
    r"\b(?:conducted|interviewed|performed|reviewed|visited|inspected|investigated)\b",
    re.IGNORECASE,
)
FIELD_STATUS_EXTRACTED = "EXTRACTED_VALUE_PRESENT"
FIELD_STATUS_ABSENT = "SOURCE_ELEMENT_ABSENT"
FIELD_STATUS_COVERAGE_UNAVAILABLE = "SOURCE_COVERAGE_UNAVAILABLE"
FIELD_STATUS_BLANK = "SOURCE_ELEMENT_PRESENT_BLANK"
FIELD_STATUS_FAILED = "EXTRACTION_FAILED"
_FINDINGS_HEADINGS = (
    "INVESTIGATION FINDINGS:",
    "INVESTIGATION FINDINGS -",
    "INVESTIGATION FINDINGS",
    "INVESTIGATION FINDING:",
    "INVESTIGATION FINDING -",
    "INVESTIGATION FINDING",
)
_DEFICIENCIES_HEADINGS = ("DEFICIENCIES:", "DEFICIENCIES")
_FINDINGS_NON_NARRATIVE_PREFIXES = (
    "finding",
    "disposition",
    "deficiency",
    "deficiencies",
    "plan of correction",
    "poc",
)
_FINDINGS_BOILERPLATE_MARKERS = (
    "(continued)",
    "estimated days of completion",
    "supervisors name",
    "licensing evaluator name",
    "i acknowledge receipt",
    "this report must be available",
    "lic9099",
    "control number",
    "state of california",
)

ReportDocumentLoader = Callable[[SourceDocumentCandidate], SourceDocument | None]
ReportFetcher = Callable[[str], bytes]
ConnectorFactory = Callable[[str], "CcldFacilityReportsConnector"]
CandidateFilter = Callable[[SourceDocumentCandidate], bool]


@dataclass(frozen=True)
class IngestionFailure:
    candidate: SourceDocumentCandidate
    stage: str
    error_type: str
    message: str


@dataclass(frozen=True)
class FacilityIngestionResult:
    facility_number: str
    discovered_count: int
    candidates: list[SourceDocumentCandidate]
    records: list[dict[str, object]]
    failures: list[IngestionFailure]


@dataclass(frozen=True)
class FacilityWorkflowFailure:
    facility_number: str
    stage: str
    error_type: str
    message: str


@dataclass(frozen=True)
class MultiFacilityIngestionResult:
    facility_results: list[FacilityIngestionResult]
    facility_failures: list[FacilityWorkflowFailure]

    @property
    def candidates(self) -> list[SourceDocumentCandidate]:
        return [
            candidate
            for facility_result in self.facility_results
            for candidate in facility_result.candidates
        ]

    @property
    def records(self) -> list[dict[str, object]]:
        return [
            record
            for facility_result in self.facility_results
            for record in facility_result.records
        ]

    @property
    def failures(self) -> list[IngestionFailure]:
        return [
            failure
            for facility_result in self.facility_results
            for failure in facility_result.failures
        ]


@dataclass(frozen=True)
class FacilityNumberInputFile:
    values: list[str]
    ignored_value_count: int


@dataclass(frozen=True)
class FacilityNumberIntakeResult:
    facility_numbers: list[str]
    duplicate_facility_numbers: list[str]
    ignored_value_count: int
    invalid_values: list[str]


@dataclass(frozen=True)
class FieldEvidence:
    status: str
    source_section: str | None
    source_text: str | None
    source_value: str | None
    warning: str | None = None


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []

    def handle_data(self, data: str) -> None:
        for line in data.splitlines():
            cleaned = _clean_text(line)
            if cleaned:
                self.lines.append(cleaned)


class _HtmlTableCellParser(HTMLParser):
    """Capture visible table-cell text while retaining intentionally blank cells."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: list[str] = []
        self._cell_depth = 0
        self._cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "td":
            return
        self._cell_depth += 1
        if self._cell_depth == 1:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_depth:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "td" or not self._cell_depth:
            return
        self._cell_depth -= 1
        if self._cell_depth == 0:
            self.cells.append(_clean_text(" ".join(self._cell_parts)))
            self._cell_parts = []


class _FacilityDetailReportLinkParser(HTMLParser):
    def __init__(self, facility_number: str) -> None:
        super().__init__(convert_charrefs=True)
        self.facility_number = facility_number
        self.report_links: list[tuple[int, str, str, str | None]] = []
        self._active_report: tuple[int, str, str | None] | None = None
        self._active_text: list[str] = []
        self._active_heading_tag: str | None = None
        self._active_heading_text: list[str] = []
        self._current_section: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._active_heading_tag = tag.casefold()
            self._active_heading_text = []
            return
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href")
        if href is None:
            return
        report_index = _report_index_from_url(href, self.facility_number)
        if report_index is None:
            return
        self._active_report = (
            report_index,
            _report_source_url(self.facility_number, report_index),
            self._current_section,
        )
        self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._active_heading_tag is not None:
            self._active_heading_text.append(data)
        if self._active_report is not None:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == self._active_heading_tag:
            self._current_section = _report_section_from_heading(
                "".join(self._active_heading_text)
            )
            self._active_heading_tag = None
            self._active_heading_text = []
            return
        if tag.casefold() != "a" or self._active_report is None:
            return
        report_index, source_url, section = self._active_report
        self.report_links.append(
            (report_index, source_url, _clean_text("".join(self._active_text)), section)
        )
        self._active_report = None
        self._active_text = []


class CcldFacilityReportsConnector:
    connector_name = "ccld_facility_reports"
    connector_version = "0.1.0"

    def __init__(
        self,
        facility_number: str = "157806098",
        report_index: int = 3,
        raw_dir: Path = Path("data/raw/ccld"),
        db_path: Path | None = None,
        schema_dir: Path = _SCHEMA_DIR,
    ) -> None:
        self.facility_number = facility_number
        self.report_index = report_index
        self.raw_dir = raw_dir
        self.db_path = db_path
        self.schema_dir = schema_dir

    def discover(
        self,
        facility_detail_html: str | None = None,
        discovered_at: str | None = None,
        report_section: str | None = None,
        allow_report_list_fallback: bool = False,
    ) -> list[SourceDocumentCandidate]:
        is_live_discovery = facility_detail_html is None
        if facility_detail_html is None:
            detail_url = f"{FACILITY_DETAIL_URL}/{self.facility_number}"
            facility_detail_html = _fetch_url(detail_url).decode("utf-8", errors="replace")
        if discovered_at is None and is_live_discovery:
            discovered_at = datetime.now(UTC).isoformat()

        candidates = discover_facility_report_candidates(
            facility_detail_html,
            self.facility_number,
            discovered_at=discovered_at,
            report_section=report_section,
        )
        if candidates or not (is_live_discovery or allow_report_list_fallback):
            return candidates

        report_list_url = f"{BASE_URL}/{self.facility_number}"
        return _candidates_from_report_list_json(
            _fetch_url(report_list_url),
            self.facility_number,
            discovered_at=discovered_at,
            report_section=report_section,
        )

    def fetch(self, source_url: str) -> bytes:
        return _fetch_url(source_url)

    def store_raw(self, source_url: str, content: bytes) -> SourceDocument:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        source_url_fields = _source_url_fields(source_url)
        report_index = source_url_fields["report_index"] or self.report_index
        raw_path = self.raw_dir / f"{self.facility_number}_inx{report_index}.html"
        raw_path.write_bytes(content)
        return SourceDocument(
            source_url=source_url,
            raw_path=raw_path,
            raw_sha256=sha256_bytes(content),
            retrieved_at=datetime.now(UTC).isoformat(),
            content_type="text/html",
        )

    def extract(self, document: SourceDocument) -> dict[str, object]:
        html = _read_raw_text(document.raw_path)
        lines = _html_lines(html)
        cells = _html_table_cells(html)
        source_url_fields = _source_url_fields(document.source_url)

        complaint_received_date = _iso_date(_complaint_received_date(lines))
        report_date = _iso_date(
            _value_after_label(lines, "Report Date:")
            or _value_after_exact_label(lines, "Report Date")
            or _value_after_spaced_colon_label(lines, "Report Date")
            or _value_after_punctuated_label(lines, "Report Date")
        )
        visit_date_source = (
            _value_after_label(lines, "VISIT DATE:")
            or _value_after_exact_label(lines, "VISIT DATE")
            or _value_after_spaced_colon_label(lines, "VISIT DATE")
            or _value_after_punctuated_label(lines, "VISIT DATE")
        )
        visit_date = _iso_date(visit_date_source)
        date_signed = _iso_date(
            _value_after_label(lines, "Date Signed:")
            or _value_after_exact_label(lines, "Date Signed")
            or _value_after_spaced_colon_label(lines, "Date Signed")
            or _value_after_punctuated_label(lines, "Date Signed")
        )
        facility_address = _table_label_evidence(cells, "ADDRESS", "facility details")
        facility_city = _table_label_evidence(cells, "CITY", "facility details")
        facility_type = _table_label_evidence(cells, "FACILITY TYPE", "facility details")
        facility_contact = _table_label_evidence(cells, "TELEPHONE", "facility details")
        facility_capacity = _integer_field_evidence(
            _table_label_evidence(cells, "CAPACITY", "facility details")
        )
        regional_office = _regional_office_evidence(cells)
        agency_name = _table_label_evidence(cells, "AGENCY", "report heading")
        investigation_findings_narrative = _investigation_findings_narrative_evidence(
            lines
        )
        deficiency_texts, deficiency_evidence = _deficiency_texts_evidence(lines)
        activity_event, first_activity_evidence = _first_investigation_activity(
            lines,
            visit_date=visit_date,
            visit_date_source=visit_date_source,
        )
        first_activity_date = first_activity_evidence.source_value
        delay_metrics = _delay_metrics(
            complaint_received_date=complaint_received_date,
            first_investigation_activity_date=first_activity_date,
            visit_date=visit_date,
            report_date=report_date,
            date_signed=date_signed,
        )

        field_evidence = {
            "facility_address": facility_address,
            "facility_capacity": facility_capacity,
            "facility_city": facility_city,
            "facility_type": facility_type,
            "facility_contact": facility_contact,
            "regional_office": regional_office,
            "agency_name": agency_name,
            "investigation_findings_narrative": investigation_findings_narrative,
            "deficiency_text": deficiency_evidence,
            "first_investigation_activity_date": first_activity_evidence,
        }
        events: list[dict[str, object]] = []
        if activity_event is not None:
            events.append(activity_event)

        return {
            "source_url": document.source_url,
            "raw_path": document.raw_path.as_posix(),
            "raw_sha256": document.raw_sha256,
            "retrieved_at": document.retrieved_at,
            "content_type": document.content_type,
            "report_index": source_url_fields["report_index"],
            "facility_number": _value_after_label(lines, "FACILITY NUMBER:")
            or _value_after_exact_label(lines, "FACILITY NUMBER")
            or _value_after_spaced_colon_label(lines, "FACILITY NUMBER")
            or _value_after_punctuated_label(lines, "FACILITY NUMBER"),
            "facility_name": _value_after_label(lines, "FACILITY NAME:")
            or _value_after_exact_label(lines, "FACILITY NAME")
            or _value_after_spaced_colon_label(lines, "FACILITY NAME")
            or _value_after_punctuated_label(lines, "FACILITY NAME"),
            "report_type": _report_type(lines),
            "facility_address": facility_address.source_value,
            "facility_capacity": _evidence_int_value(facility_capacity),
            "facility_city": facility_city.source_value,
            "facility_type": facility_type.source_value,
            "facility_contact": facility_contact.source_value,
            "regional_office": regional_office.source_value,
            "agency_name": agency_name.source_value,
            "investigation_findings_narrative": investigation_findings_narrative.source_value,
            "deficiency_texts": deficiency_texts,
            "report_date": report_date,
            "date_signed": date_signed,
            "complaint_received_date": complaint_received_date,
            "first_investigation_activity_date": first_activity_date,
            "complaint_control_number": _value_after_label(
                lines, "COMPLAINT CONTROL NUMBER:"
            )
            or _value_after_exact_label(lines, "COMPLAINT CONTROL NUMBER")
            or _value_after_spaced_colon_label(lines, "COMPLAINT CONTROL NUMBER")
            or _value_after_punctuated_label(lines, "COMPLAINT CONTROL NUMBER"),
            "allegations": _allegations(lines),
            "finding": _finding(lines),
            "visit_date": visit_date,
            "events": events,
            "_field_evidence": field_evidence,
            "_deficiency_evidence": deficiency_evidence,
            **delay_metrics,
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
        extracted_events = cast(list[dict[str, object]], extracted.get("events", []))

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

        normalized_events = [
            {
                "event_id": f"{complaint_id}-event-{index}",
                "complaint_id": complaint_id,
                "event_date": _required_mapping_str(event, "event_date"),
                "event_type": _required_mapping_str(event, "event_type"),
                "event_text": _optional_mapping_str(event, "event_text"),
                "extracted_from_section": _optional_mapping_str(
                    event, "extracted_from_section"
                ),
                "extraction_confidence": 1.0,
            }
            for index, event in enumerate(extracted_events, start=1)
        ]

        complaint: dict[str, object] = {
            "complaint_id": complaint_id,
            "facility_id": facility_id,
            "document_id": document_id,
            "complaint_control_number": complaint_control_number,
            "complaint_received_date": _optional_str(extracted, "complaint_received_date"),
            "first_investigation_activity_date": _optional_str(
                extracted, "first_investigation_activity_date"
            ),
            "visit_date": _optional_str(extracted, "visit_date"),
            "report_date": _optional_str(extracted, "report_date"),
            "date_signed": _optional_str(extracted, "date_signed"),
            "finding": finding,
            "days_received_to_first_activity": cast(
                int | None, extracted.get("days_received_to_first_activity")
            ),
            "days_received_to_visit": cast(int | None, extracted.get("days_received_to_visit")),
            "days_received_to_report": cast(
                int | None, extracted.get("days_received_to_report")
            ),
            "days_report_to_signed": cast(int | None, extracted.get("days_report_to_signed")),
            "review_delay_over_30_days": bool(extracted.get("review_delay_over_30_days")),
            "review_delay_over_60_days": bool(extracted.get("review_delay_over_60_days")),
            "review_delay_over_90_days": bool(extracted.get("review_delay_over_90_days")),
            "review_delay_over_120_days": bool(extracted.get("review_delay_over_120_days")),
            "missing_first_activity_date": bool(extracted.get("missing_first_activity_date")),
            "report_date_used_as_proxy": bool(extracted.get("report_date_used_as_proxy")),
            "extraction_confidence": 1.0,
        }
        field_evidence = cast(dict[str, FieldEvidence], extracted.get("_field_evidence", {}))
        for field_name in (
            "agency_name",
            "investigation_findings_narrative",
            "facility_contact",
        ):
            evidence = field_evidence[field_name]
            if evidence.status != FIELD_STATUS_ABSENT:
                normalized_field_name = (
                    "complaint_report_contact"
                    if field_name == "facility_contact"
                    else field_name
                )
                source_value = evidence.source_value
                if field_name == "facility_contact":
                    source_value = _historical_contact_value(source_value)
                else:
                    source_value = _historical_observation_value(source_value)
                if source_value is not None or field_name == "facility_contact":
                    complaint[normalized_field_name] = source_value
        deficiency_texts = cast(list[str], extracted.get("deficiency_texts", []))
        if deficiency_texts:
            complaint["deficiency_texts"] = deficiency_texts

        normalized: dict[str, object] = {
            "facility": {
                "facility_id": facility_id,
                "source_id": SOURCE_ID,
                "external_facility_number": facility_number,
                "facility_name": facility_name,
                "facility_type": _optional_str(extracted, "facility_type"),
                "licensee_name": None,
                "county": None,
                "status": None,
                "capacity": cast(int | None, extracted.get("facility_capacity")),
                "regional_office": _optional_str(extracted, "regional_office"),
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
            "complaint": complaint,
            "allegations": normalized_allegations,
            "extraction_audit": _audit_records(document_id, extracted),
        }
        if normalized_events:
            normalized["events"] = normalized_events
        return normalized

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
        for event in cast(list[dict[str, Any]], normalized.get("events", [])):
            validate_schema(event, self.schema_dir / "event.schema.json")
        for audit_record in cast(list[dict[str, Any]], normalized["extraction_audit"]):
            validate_schema(audit_record, self.schema_dir / "extraction_audit.schema.json")

    def emit(self, normalized: dict[str, object]) -> None:
        self.validate(normalized)
        if self.db_path is not None:
            write_normalized_records(self.db_path, [normalized])


def ingest_facility_reports_for_facility(
    facility_number: str = "157806098",
    *,
    connector: CcldFacilityReportsConnector | None = None,
    facility_detail_html: str | None = None,
    discovered_at: str | None = None,
    limit: int | None = None,
    max_requests: int | None = None,
    load_document: ReportDocumentLoader | None = None,
    fetch_report: ReportFetcher | None = None,
    report_section: str | None = None,
    candidate_filter: CandidateFilter | None = None,
    allow_report_list_fallback: bool = False,
) -> FacilityIngestionResult:
    if limit is not None and limit < 0:
        raise ValueError("limit must be greater than or equal to 0.")
    if max_requests is not None and max_requests < 0:
        raise ValueError("max_requests must be greater than or equal to 0.")

    active_connector = connector or CcldFacilityReportsConnector(facility_number=facility_number)
    discovered_candidates = active_connector.discover(
        facility_detail_html=facility_detail_html,
        discovered_at=discovered_at,
        report_section=report_section,
        allow_report_list_fallback=allow_report_list_fallback,
    )
    candidates = discovered_candidates
    if candidate_filter is not None:
        candidates = [candidate for candidate in candidates if candidate_filter(candidate)]
    if limit is not None:
        candidates = candidates[:limit]
    if max_requests is not None and len(candidates) > max_requests:
        raise ValueError(
            "Selected report candidates exceed max_requests. "
            f"Selected {len(candidates)} report(s), max_requests is {max_requests}."
        )

    return _ingest_selected_candidates(
        active_connector,
        candidates,
        discovered_count=len(discovered_candidates),
        load_document=load_document,
        fetch_report=fetch_report,
    )


def ingest_facility_reports_for_facilities(
    facility_numbers: list[str],
    *,
    connector_factory: ConnectorFactory | None = None,
    facility_detail_html_by_number: dict[str, str] | None = None,
    discovered_at: str | None = None,
    per_facility_limit: int | None = None,
    max_requests: int | None = None,
    load_document: ReportDocumentLoader | None = None,
    fetch_report: ReportFetcher | None = None,
) -> MultiFacilityIngestionResult:
    if per_facility_limit is not None and per_facility_limit < 0:
        raise ValueError("per_facility_limit must be greater than or equal to 0.")
    if max_requests is not None and max_requests < 0:
        raise ValueError("max_requests must be greater than or equal to 0.")

    normalized_facility_numbers = normalize_facility_numbers(facility_numbers)
    selected: list[tuple[CcldFacilityReportsConnector, list[SourceDocumentCandidate], int]] = []
    facility_failures: list[FacilityWorkflowFailure] = []

    for facility_number in normalized_facility_numbers:
        active_connector = (
            connector_factory(facility_number)
            if connector_factory is not None
            else CcldFacilityReportsConnector(facility_number=facility_number)
        )
        try:
            discovered_candidates = active_connector.discover(
                facility_detail_html=(facility_detail_html_by_number or {}).get(facility_number),
                discovered_at=discovered_at,
            )
        except Exception as exc:
            facility_failures.append(_facility_workflow_failure(facility_number, "discover", exc))
            continue

        candidates = discovered_candidates
        if per_facility_limit is not None:
            candidates = candidates[:per_facility_limit]
        selected.append((active_connector, candidates, len(discovered_candidates)))

    selected_report_count = sum(len(candidates) for _, candidates, _ in selected)
    if max_requests is not None and selected_report_count > max_requests:
        raise ValueError(
            "Selected report candidates exceed max_requests. "
            f"Selected {selected_report_count} report(s), max_requests is {max_requests}."
        )

    facility_results = [
        _ingest_selected_candidates(
            active_connector,
            candidates,
            discovered_count=discovered_count,
            load_document=load_document,
            fetch_report=fetch_report,
        )
        for active_connector, candidates, discovered_count in selected
    ]

    return MultiFacilityIngestionResult(
        facility_results=facility_results,
        facility_failures=facility_failures,
    )


def normalize_facility_numbers(facility_numbers: list[str]) -> list[str]:
    intake = inspect_facility_numbers(facility_numbers)
    if intake.invalid_values:
        invalid_values = ", ".join(repr(value) for value in intake.invalid_values)
        raise ValueError(f"Facility number must contain digits only: {invalid_values}")
    if not intake.facility_numbers:
        raise ValueError("At least one facility number is required.")
    return intake.facility_numbers


def inspect_facility_numbers(facility_numbers: list[str]) -> FacilityNumberIntakeResult:
    normalized: list[str] = []
    duplicates: list[str] = []
    invalid_values: list[str] = []
    seen: set[str] = set()
    ignored_value_count = 0

    for facility_number in facility_numbers:
        cleaned = facility_number.strip()
        if _is_ignored_facility_number_value(cleaned):
            ignored_value_count += 1
            continue
        if not cleaned.isdigit():
            invalid_values.append(cleaned)
            continue
        if cleaned in seen:
            duplicates.append(cleaned)
            continue
        seen.add(cleaned)
        normalized.append(cleaned)

    return FacilityNumberIntakeResult(
        facility_numbers=normalized,
        duplicate_facility_numbers=duplicates,
        ignored_value_count=ignored_value_count,
        invalid_values=invalid_values,
    )


def read_facility_numbers_file(path: Path) -> list[str]:
    return normalize_facility_numbers(read_facility_number_input_file(path).values)


def read_facility_number_input_file(path: Path) -> FacilityNumberInputFile:
    values: list[str] = []
    ignored_value_count = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if not row:
                ignored_value_count += 1
                continue
            for value in row:
                cleaned = value.strip()
                if _is_ignored_facility_number_value(cleaned):
                    ignored_value_count += 1
                    continue
                values.append(cleaned)
    return FacilityNumberInputFile(values=values, ignored_value_count=ignored_value_count)


def _is_ignored_facility_number_value(value: str) -> bool:
    return (
        not value
        or value.startswith("#")
        or value.casefold() in {"facility_number", "facilitynumber", "facnum"}
    )


def _ingest_selected_candidates(
    active_connector: CcldFacilityReportsConnector,
    candidates: list[SourceDocumentCandidate],
    *,
    discovered_count: int,
    load_document: ReportDocumentLoader | None,
    fetch_report: ReportFetcher | None,
) -> FacilityIngestionResult:

    records: list[dict[str, object]] = []
    failures: list[IngestionFailure] = []

    for candidate in candidates:
        document = _load_or_fetch_document(
            active_connector,
            candidate,
            failures,
            load_document=load_document,
            fetch_report=fetch_report,
        )
        if document is None:
            continue

        try:
            extracted = active_connector.extract(document)
        except Exception as exc:
            failures.append(_ingestion_failure(candidate, "extract", exc))
            continue

        try:
            normalized = active_connector.normalize(extracted)
        except Exception as exc:
            failures.append(_ingestion_failure(candidate, "normalize", exc))
            continue

        try:
            active_connector.validate(normalized)
        except Exception as exc:
            failures.append(_ingestion_failure(candidate, "validate", exc))
            continue

        try:
            active_connector.emit(normalized)
        except Exception as exc:
            failures.append(_ingestion_failure(candidate, "emit", exc))
            continue

        records.append(normalized)

    return FacilityIngestionResult(
        facility_number=active_connector.facility_number,
        discovered_count=discovered_count,
        candidates=candidates,
        records=records,
        failures=failures,
    )


def _facility_workflow_failure(
    facility_number: str, stage: str, exc: Exception
) -> FacilityWorkflowFailure:
    return FacilityWorkflowFailure(
        facility_number=facility_number,
        stage=stage,
        error_type=type(exc).__name__,
        message=str(exc),
    )


def _load_or_fetch_document(
    connector: CcldFacilityReportsConnector,
    candidate: SourceDocumentCandidate,
    failures: list[IngestionFailure],
    *,
    load_document: ReportDocumentLoader | None,
    fetch_report: ReportFetcher | None,
) -> SourceDocument | None:
    if load_document is not None:
        try:
            document = load_document(candidate)
        except Exception as exc:
            failures.append(_ingestion_failure(candidate, "load", exc))
            return None

        if document is None:
            failures.append(
                IngestionFailure(
                    candidate=candidate,
                    stage="load",
                    error_type="ReportContentNotFound",
                    message="No report content was available for the discovered candidate.",
                )
            )
        return document

    try:
        content = (fetch_report or connector.fetch)(candidate.source_url)
    except Exception as exc:
        failures.append(_ingestion_failure(candidate, "fetch", exc))
        return None

    try:
        return connector.store_raw(candidate.source_url, content)
    except Exception as exc:
        failures.append(_ingestion_failure(candidate, "store_raw", exc))
        return None


def _ingestion_failure(
    candidate: SourceDocumentCandidate, stage: str, exc: Exception
) -> IngestionFailure:
    return IngestionFailure(
        candidate=candidate,
        stage=stage,
        error_type=type(exc).__name__,
        message=str(exc),
    )


def _html_lines(html: str) -> list[str]:
    parser = _HtmlTextParser()
    parser.feed(html)
    return parser.lines


def _html_table_cells(html: str) -> list[str]:
    parser = _HtmlTableCellParser()
    parser.feed(html)
    return parser.cells


def _table_label_evidence(
    cells: list[str], label: str, source_section: str
) -> FieldEvidence:
    normalized_label = label.strip(" .:-").casefold()
    for index, cell in enumerate(cells):
        if cell.strip(" .:-").casefold() != normalized_label:
            continue
        value = cells[index + 1] if index + 1 < len(cells) else ""
        source_text = f"{cell} {value}".strip()
        if not value.strip():
            return FieldEvidence(
                status=FIELD_STATUS_BLANK,
                source_section=source_section,
                source_text=cell,
                source_value=None,
                warning="Source element is present but blank.",
            )
        return FieldEvidence(
            status=FIELD_STATUS_EXTRACTED,
            source_section=source_section,
            source_text=source_text,
            source_value=value,
        )
    return FieldEvidence(
        status=FIELD_STATUS_ABSENT,
        source_section=source_section,
        source_text=None,
        source_value=None,
        warning="Source element was not found in the retained source report.",
    )


def _integer_field_evidence(evidence: FieldEvidence) -> FieldEvidence:
    if evidence.status != FIELD_STATUS_EXTRACTED or evidence.source_value is None:
        return evidence
    if re.fullmatch(r"\d+", evidence.source_value.strip()):
        return evidence
    return FieldEvidence(
        status=FIELD_STATUS_FAILED,
        source_section=evidence.source_section,
        source_text=evidence.source_text,
        source_value=None,
        warning="Source element was present but was not a deterministic integer.",
    )


def _evidence_int_value(evidence: FieldEvidence) -> int | None:
    if evidence.status != FIELD_STATUS_EXTRACTED or evidence.source_value is None:
        return None
    return int(evidence.source_value)


def _regional_office_evidence(cells: list[str]) -> FieldEvidence:
    for cell in cells:
        match = re.search(r"\bCCLD Regional Office\b", cell, re.IGNORECASE)
        if match is None:
            continue
        return FieldEvidence(
            status=FIELD_STATUS_EXTRACTED,
            source_section="report header",
            source_text=cell,
            source_value=match.group(0),
        )
    return FieldEvidence(
        status=FIELD_STATUS_ABSENT,
        source_section="report header",
        source_text=None,
        source_value=None,
        warning="Source element was not found in the retained source report.",
    )


def _first_investigation_activity(
    lines: list[str],
    *,
    visit_date: str | None = None,
    visit_date_source: str | None = None,
) -> tuple[dict[str, object] | None, FieldEvidence]:
    section_lines = _investigation_findings_lines(lines)

    candidates: list[tuple[date, int, str, str]] = []
    if visit_date is not None:
        parsed_visit_date = parse_date_or_none(visit_date)
        if parsed_visit_date is not None:
            candidates.append(
                (
                    parsed_visit_date,
                    1,
                    f"VISIT DATE: {visit_date_source or visit_date}",
                    "report header",
                )
            )

    malformed_source_text: str | None = None
    for line in section_lines or []:
        if INVESTIGATION_ACTIVITY_CUE_RE.search(line) is None:
            continue
        source_text = re.split(r"(?<=[.!?])\s+", line, maxsplit=1)[0].strip()
        date_tokens = SOURCE_DATE_TOKEN_RE.findall(source_text)
        for token in date_tokens:
            normalized = _iso_date(token)
            if normalized is None:
                malformed_source_text = source_text
                continue
            parsed = parse_date_or_none(normalized)
            if parsed is not None:
                candidates.append((parsed, 0, source_text, "investigation findings"))

    if not candidates:
        if malformed_source_text is not None:
            return None, FieldEvidence(
                status=FIELD_STATUS_FAILED,
                source_section="investigation findings",
                source_text=malformed_source_text,
                source_value=None,
                warning=(
                    "Investigation activity text contained a date-like value that "
                    "could not be parsed deterministically."
                ),
            )
        return None, FieldEvidence(
            status=FIELD_STATUS_ABSENT,
            source_section="investigation findings",
            source_text=None,
            source_value=None,
            warning=(
                "No deterministic dated investigation activity was found."
                if section_lines is not None
                else "Investigation findings section and structured visit date were not found."
            ),
        )

    first_date, _evidence_priority, source_text, source_section = min(
        candidates,
        key=lambda item: (item[0], item[1], item[2]),
    )
    normalized_date = first_date.isoformat()
    evidence = FieldEvidence(
        status=FIELD_STATUS_EXTRACTED,
        source_section=source_section,
        source_text=source_text,
        source_value=normalized_date,
    )
    return (
        {
            "event_date": normalized_date,
            "event_type": "investigation_activity",
            "event_text": source_text,
            "extracted_from_section": source_section,
            "source_text": source_text,
            "source_section": source_section,
        },
        evidence,
    )


def _investigation_findings_lines(lines: list[str]) -> list[str] | None:
    heading_index = _line_index_any(lines, _FINDINGS_HEADINGS)
    if heading_index is None:
        return None
    section: list[str] = []
    for line in lines[heading_index + 1 :]:
        if section and line.strip(" .:-").casefold() == "facility name":
            break
        section.append(line)
    return section


def _investigation_findings_narrative_evidence(lines: list[str]) -> FieldEvidence:
    section_lines = _investigation_findings_lines(lines)
    if section_lines is None:
        return FieldEvidence(
            status=FIELD_STATUS_ABSENT,
            source_section="investigation findings",
            source_text=None,
            source_value=None,
            warning="Investigation findings section was not found in the retained source report.",
        )
    narrative_lines: list[str] = []
    for line in section_lines:
        normalized_line = line.strip(" .:-").casefold()
        if normalized_line in {"deficiencies", "plan of correction", "poc", "facility name"}:
            break
        if normalized_line.startswith(_FINDINGS_NON_NARRATIVE_PREFIXES):
            continue
        if normalized_line in {"substantiated", "unsubstantiated", "inconclusive", "dismissed"}:
            continue
        narrative_line = _without_findings_boilerplate(line)
        if narrative_line:
            narrative_lines.append(narrative_line)
    if not narrative_lines:
        return FieldEvidence(
            status=FIELD_STATUS_BLANK,
            source_section="investigation findings",
            source_text="INVESTIGATION FINDINGS",
            source_value=None,
            warning="Investigation findings section was present without narrative text.",
        )
    narrative = " ".join(narrative_lines)
    return FieldEvidence(
        status=FIELD_STATUS_EXTRACTED,
        source_section="investigation findings",
        source_text=narrative,
        source_value=narrative,
    )


def _without_findings_boilerplate(line: str) -> str:
    cut_at = len(line)
    normalized_line = line.casefold()
    for marker in _FINDINGS_BOILERPLATE_MARKERS:
        marker_index = normalized_line.find(marker)
        if marker_index >= 0:
            cut_at = min(cut_at, marker_index)
    narrative = line[:cut_at].strip()
    narrative = re.sub(r"^(?:\d+\s+){2,}", "", narrative)
    return narrative.strip()


def _deficiency_texts_evidence(
    lines: list[str],
) -> tuple[list[str], FieldEvidence]:
    heading_index = _line_index_any(lines, _DEFICIENCIES_HEADINGS)
    if heading_index is None:
        return [], FieldEvidence(
            status=FIELD_STATUS_ABSENT,
            source_section="deficiencies",
            source_text=None,
            source_value=None,
            warning="Structured deficiencies section was not found in the retained source report.",
        )
    values: list[str] = []
    for line in lines[heading_index + 1 :]:
        normalized_line = line.strip(" .:-").casefold()
        if normalized_line in {"facility name", "plan of correction", "poc"}:
            break
        if line.strip():
            values.append(line)
    if not values:
        return [], FieldEvidence(
            status=FIELD_STATUS_BLANK,
            source_section="deficiencies",
            source_text="DEFICIENCIES",
            source_value=None,
            warning="Structured deficiencies section was present but blank.",
        )
    return values, FieldEvidence(
        status=FIELD_STATUS_EXTRACTED,
        source_section="deficiencies",
        source_text="DEFICIENCIES",
        source_value=" | ".join(values),
    )


def discover_facility_report_candidates(
    facility_detail_html: str,
    facility_number: str,
    discovered_at: str | None = None,
    report_section: str | None = None,
) -> list[SourceDocumentCandidate]:
    parser = _FacilityDetailReportLinkParser(facility_number)
    parser.feed(facility_detail_html)

    candidates: list[SourceDocumentCandidate] = []
    seen_indexes: set[int] = set()
    seen_urls: set[str] = set()
    selected_report_section = _normalized_report_section(report_section)
    for report_index, source_url, link_text, section in parser.report_links:
        if selected_report_section is not None and section != selected_report_section:
            continue
        if report_index in seen_indexes or source_url in seen_urls:
            continue
        seen_indexes.add(report_index)
        seen_urls.add(source_url)
        candidates.append(
            SourceDocumentCandidate(
                source_name=SOURCE_ID,
                facility_number=facility_number,
                report_index=report_index,
                source_url=source_url,
                discovered_report_date=_iso_date(link_text),
                discovered_at=discovered_at,
                report_section=section,
            )
        )
    return candidates


def _report_section_from_heading(value: str) -> str | None:
    normalized = _normalized_report_section(value)
    if normalized in {"all_visits", "complaints"}:
        return normalized
    return None


def _normalized_report_section(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    if normalized in {"all_visit", "all_visits"}:
        return "all_visits"
    if normalized in {"complaint", "complaints"}:
        return "complaints"
    return normalized or None


def _fetch_url(source_url: str) -> bytes:
    request = Request(source_url, headers={"User-Agent": LIVE_USER_AGENT})
    with urlopen(request, timeout=LIVE_REQUEST_TIMEOUT_SECONDS) as response:
        return cast(bytes, response.read())


def _read_raw_text(raw_path: Path) -> str:
    if raw_path.exists() or raw_path.is_absolute():
        return raw_path.read_text(encoding="utf-8")
    return (Path(__file__).resolve().parents[4] / raw_path).read_text(encoding="utf-8")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _source_url_fields(source_url: str) -> dict[str, int | None]:
    query = parse_qs(urlparse(source_url).query)
    report_index = query.get("inx", [None])[0]
    return {"report_index": int(report_index) if report_index is not None else None}


def _report_index_from_url(source_url: str, facility_number: str) -> int | None:
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https":
        return None
    if parsed_url.netloc.casefold() != "www.ccld.dss.ca.gov":
        return None
    if parsed_url.path != "/transparencyapi/api/FacilityReports":
        return None

    query = parse_qs(parsed_url.query)
    if query.get("facNum", [None])[0] != facility_number:
        return None
    report_index = query.get("inx", [None])[0]
    if report_index is None or not report_index.isdigit():
        return None
    return int(report_index)


def _report_source_url(facility_number: str, report_index: int) -> str:
    return f"{BASE_URL}?{urlencode({'facNum': facility_number, 'inx': report_index})}"


def _candidates_from_report_list_json(
    report_list_content: bytes,
    facility_number: str,
    discovered_at: str | None = None,
    report_section: str | None = None,
) -> list[SourceDocumentCandidate]:
    parsed = json.loads(report_list_content.decode("utf-8"))
    # The CCLD API returns JSON null for facilities with no records (e.g. closed
    # facilities that have never had a complaint report indexed).  Treat null as
    # an authoritative "no records" response and return an empty candidate list.
    if parsed is None:
        return []
    if not isinstance(parsed, dict):
        raise ValueError(
            f"Discovery response has unexpected structure: "
            f"expected JSON object or null, got {type(parsed).__name__}"
        )
    report_list = cast(dict[str, object], parsed)
    raw_array = report_list.get("REPORTARRAY")
    # REPORTARRAY may be absent (no default needed), null, or a list.  Treat
    # absent-or-null as "no records" so a closed facility with no report index
    # is not misreported as a discovery failure.
    if raw_array is None:
        return []
    if not isinstance(raw_array, list):
        raise ValueError(
            f"Discovery response REPORTARRAY has unexpected type: {type(raw_array).__name__}"
        )
    report_array = cast(list[dict[str, object]], raw_array)
    selected_report_section = _normalized_report_section(report_section)
    candidates = []
    for report_index, report in enumerate(report_array):
        if not isinstance(report, dict):
            # A null or non-object element is not a usable report entry; skip it.
            continue
        if report.get("FACILITYNUMBER") != facility_number:
            continue
        section = _report_section_from_report_type(cast(str | None, report.get("REPORTTYPE")))
        if selected_report_section is not None and section != selected_report_section:
            continue
        candidates.append(
            SourceDocumentCandidate(
                source_name=SOURCE_ID,
                facility_number=facility_number,
                report_index=report_index,
                source_url=_report_source_url(facility_number, report_index),
                discovered_report_date=_iso_date(cast(str | None, report.get("REPORTDATE"))),
                discovered_at=discovered_at,
                report_section=section,
            )
        )
    return candidates


def _report_section_from_report_type(value: str | None) -> str | None:
    normalized = _normalized_report_section(value)
    if normalized in {"complaint", "complaints"}:
        return "complaints"
    if normalized in {"visit", "visits", "all_visit", "all_visits"}:
        return "all_visits"
    return normalized


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


def _value_after_exact_label(lines: list[str], label: str) -> str | None:
    normalized_label = label.casefold()
    for index, line in enumerate(lines):
        if line.casefold() == normalized_label:
            return _next_value(lines, index)
    return None


def _value_after_spaced_colon_label(lines: list[str], label: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(label)}\s+:(.*)$", re.IGNORECASE)
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match is None:
            continue
        value = _clean_text(match.group(1))
        return value or _next_value(lines, index)
    return None


def _value_after_punctuated_label(lines: list[str], label: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(label)}\s*[;\-]\s*(.*)$", re.IGNORECASE)
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match is None:
            continue
        value = _clean_text(match.group(1))
        return value or _next_value(lines, index)
    return None


def _next_value(lines: list[str], index: int) -> str | None:
    for value in lines[index + 1 :]:
        if not value.endswith(":"):
            return value
    return None


def _report_type(lines: list[str]) -> str | None:
    for line in lines:
        if line.strip(" .:-").casefold() == "complaint investigation report":
            return "COMPLAINT INVESTIGATION REPORT"
    return None


def _complaint_received_date(lines: list[str]) -> str | None:
    phrases = (
        "complaint received in our office on",
        "complaint was received in our office on",
        "complaint received in our office",
        "complaint was received in our office",
    )
    for index, line in enumerate(lines):
        normalized_line = line.casefold()
        for phrase in phrases:
            if phrase in normalized_line:
                inline_value = line[normalized_line.index(phrase) + len(phrase) :].strip(" .:-")
                inline_date = _source_date_token(inline_value)
                if inline_date is not None:
                    return inline_date
                if inline_value:
                    return inline_value
                return _next_value(lines, index)
    return None


def _source_date_token(value: str) -> str | None:
    match = SOURCE_DATE_TOKEN_RE.search(value)
    if match is None:
        return None
    return match.group(0)


def _allegations(lines: list[str]) -> list[str]:
    start = _line_index_any(
        lines,
        (
            "ALLEGATION(S):",
            "ALLEGATION(S) -",
            "ALLEGATION(S)",
            "ALLEGATION (S):",
            "ALLEGATION (S) -",
            "ALLEGATION (S)",
            "ALLEGATIONS:",
            "ALLEGATIONS -",
            "ALLEGATIONS",
            "ALLEGATION:",
            "ALLEGATION -",
            "ALLEGATION",
        ),
    )
    end = _line_index_any(
        lines,
        (
            "INVESTIGATION FINDINGS:",
              "INVESTIGATION FINDINGS -",
            "INVESTIGATION FINDINGS",
            "INVESTIGATION FINDING:",
              "INVESTIGATION FINDING -",
            "INVESTIGATION FINDING",
        ),
    )
    if start is None or end is None:
        return []

    allegations: list[str] = []
    for line in lines[start + 1 : end]:
        allegation = _allegation_text(line)
        if allegation is not None:
            if _is_allegation_continuation(line) and allegations:
                allegations[-1] = f"{allegations[-1]} {allegation}"
            else:
                allegations.append(allegation)
    return allegations


def _allegation_text(line: str) -> str | None:
    allegation = NUMBERED_ALLEGATION_PREFIX_RE.sub("", line).strip()
    if not allegation:
        return None
    return " ".join(allegation.split())


def _is_allegation_continuation(line: str) -> bool:
    stripped = line.lstrip()
    return (
        bool(stripped)
        and not NUMBERED_ALLEGATION_PREFIX_RE.match(stripped)
        and stripped[0].islower()
    )


def _line_index(lines: list[str], value: str) -> int | None:
    for index, line in enumerate(lines):
        if line.casefold() == value.casefold():
            return index
    return None


def _line_index_any(lines: list[str], values: tuple[str, ...]) -> int | None:
    normalized_values = {value.casefold() for value in values}
    for index, line in enumerate(lines):
        if line.casefold() in normalized_values:
            return index
    return None


def _finding(lines: list[str]) -> str:
    for line in lines:
        finding = _normalized_finding(line)
        if finding is not None:
            return finding

        inline_labeled_finding = _inline_labeled_finding(line)
        if inline_labeled_finding is not None:
            finding = _normalized_finding(inline_labeled_finding)
            if finding is not None:
                return finding

    labeled_finding = _value_after_label(lines, "Finding:")
    if labeled_finding is not None:
        finding = _normalized_finding(labeled_finding)
        if finding is not None:
            return finding

    split_label_finding = _value_after_exact_label(lines, "Finding")
    if split_label_finding is not None:
        finding = _normalized_finding(split_label_finding)
        if finding is not None:
            return finding

    spaced_colon_finding = _value_after_spaced_colon_label(lines, "Finding")
    if spaced_colon_finding is not None:
        finding = _normalized_finding(spaced_colon_finding)
        if finding is not None:
            return finding

    return "Unknown"


def _inline_labeled_finding(line: str) -> str | None:
    match = FINDING_INLINE_LABEL_RE.match(line)
    return match.group(1) if match is not None else None


def _normalized_finding(value: str) -> str | None:
    normalized_value = value.strip(" .:-")
    for finding in ALLOWED_FINDINGS:
        if normalized_value.casefold() == finding.casefold():
            return finding
    return None


def _delay_metrics(
    *,
    complaint_received_date: str | None,
    first_investigation_activity_date: str | None,
    visit_date: str | None,
    report_date: str | None,
    date_signed: str | None,
) -> dict[str, object]:
    received_date = parse_date_or_none(complaint_received_date)
    first_activity_date = parse_date_or_none(first_investigation_activity_date)
    parsed_visit_date = parse_date_or_none(visit_date)
    parsed_report_date = parse_date_or_none(report_date)

    days_received_to_first_activity = days_between(received_date, first_activity_date)
    days_received_to_visit = days_between(received_date, parsed_visit_date)
    days_received_to_report = days_between(received_date, parsed_report_date)
    delay_basis = _delay_review_basis(
        days_received_to_first_activity,
        days_received_to_visit,
        days_received_to_report,
    )

    return {
        "days_received_to_first_activity": days_received_to_first_activity,
        "days_received_to_visit": days_received_to_visit,
        "days_received_to_report": days_received_to_report,
        "days_report_to_signed": days_between(parsed_report_date, parse_date_or_none(date_signed)),
        "review_delay_over_30_days": _review_delay_over(delay_basis, 30),
        "review_delay_over_60_days": _review_delay_over(delay_basis, 60),
        "review_delay_over_90_days": _review_delay_over(delay_basis, 90),
        "review_delay_over_120_days": _review_delay_over(delay_basis, 120),
        "missing_first_activity_date": received_date is not None and first_activity_date is None,
        "report_date_used_as_proxy": (
            days_received_to_first_activity is None
            and days_received_to_visit is None
            and days_received_to_report is not None
        ),
    }


def _delay_review_basis(
    days_received_to_first_activity: int | None,
    days_received_to_visit: int | None,
    days_received_to_report: int | None,
) -> int | None:
    for delay_days in (
        days_received_to_first_activity,
        days_received_to_visit,
        days_received_to_report,
    ):
        if delay_days is not None:
            return delay_days
    return None


def _review_delay_over(delay_days: int | None, threshold: int) -> bool:
    return delay_days is not None and delay_days > threshold


def _iso_date(value: str | None) -> str | None:
    try:
        parsed = parse_date_or_none(value)
    except (OverflowError, ValueError):
        return None
    return parsed.isoformat() if parsed is not None else None


def _required_str(extracted: dict[str, object], field_name: str) -> str:
    value = _optional_str(extracted, field_name)
    if value is None:
        raise ValueError(f"Missing required extracted field: {field_name}")
    return value


def _optional_str(extracted: dict[str, object], field_name: str) -> str | None:
    value = extracted.get(field_name)
    return value if isinstance(value, str) else None


def _historical_contact_value(value: str | None) -> str | None:
    normalized_value = _historical_observation_value(value)
    if normalized_value is None:
        return None
    normalized = " ".join(normalized_value.split()).casefold().rstrip(".")
    if normalized == "see faqs":
        return None
    return normalized_value


def _historical_observation_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).casefold().rstrip(".")
    if normalized in {"n/a", "na", "not available", "unavailable"}:
        return None
    return value


def _required_mapping_str(values: dict[str, object], field_name: str) -> str:
    value = _optional_mapping_str(values, field_name)
    if value is None:
        raise ValueError(f"Missing required extracted field: {field_name}")
    return value


def _optional_mapping_str(values: dict[str, object], field_name: str) -> str | None:
    value = values.get(field_name)
    return value if isinstance(value, str) else None


def _audit_records(document_id: str, extracted: dict[str, object]) -> list[dict[str, object]]:
    field_names = (
        "facility_number",
        "facility_name",
        "facility_address",
        "facility_capacity",
        "facility_city",
        "facility_contact",
        "facility_type",
        "regional_office",
        "agency_name",
        "investigation_findings_narrative",
        "report_type",
        "report_date",
        "date_signed",
        "complaint_received_date",
        "first_investigation_activity_date",
        "complaint_control_number",
        "allegations",
        "finding",
        "visit_date",
        "days_received_to_first_activity",
        "days_received_to_visit",
        "days_received_to_report",
        "days_report_to_signed",
        "review_delay_over_30_days",
        "review_delay_over_60_days",
        "review_delay_over_90_days",
        "review_delay_over_120_days",
        "missing_first_activity_date",
        "report_date_used_as_proxy",
    )
    field_evidence = cast(
        dict[str, FieldEvidence], extracted.get("_field_evidence", {})
    )
    records: list[dict[str, object]] = []
    for field_name in field_names:
        value = extracted.get(field_name)
        evidence = field_evidence.get(field_name)
        records.append(
            {
                "audit_id": f"{document_id}-{field_name}",
                "document_id": document_id,
                "field_name": field_name,
                "extraction_method": DETERMINISTIC_METHOD,
                "extractor_version": CcldFacilityReportsConnector.connector_version,
                "extracted_value": _audit_value(value),
                "confidence": (
                    1.0
                    if evidence is not None and evidence.status == FIELD_STATUS_EXTRACTED
                    else 1.0 if evidence is None and value is not None else 0.0
                ),
                "source_text": evidence.source_text if evidence is not None else None,
                "source_section": evidence.source_section if evidence is not None else None,
                "warning": (
                    evidence.warning
                    if evidence is not None
                    else None if value is not None else "Field was not found in source report."
                ),
            }
        )
    deficiency_evidence = cast(
        FieldEvidence | None, extracted.get("_deficiency_evidence")
    )
    for index, deficiency_text in enumerate(
        cast(list[str], extracted.get("deficiency_texts", [])), start=1
    ):
        records.append(
            {
                "audit_id": f"{document_id}-deficiency_text-{index}",
                "document_id": document_id,
                "field_name": "deficiency_text",
                "extraction_method": DETERMINISTIC_METHOD,
                "extractor_version": CcldFacilityReportsConnector.connector_version,
                "extracted_value": deficiency_text,
                "confidence": 1.0,
                "source_text": deficiency_text,
                "source_section": "deficiencies",
                "warning": None,
            }
        )
    if deficiency_evidence is not None and not extracted.get("deficiency_texts"):
        records.append(
            {
                "audit_id": f"{document_id}-deficiency_text",
                "document_id": document_id,
                "field_name": "deficiency_text",
                "extraction_method": DETERMINISTIC_METHOD,
                "extractor_version": CcldFacilityReportsConnector.connector_version,
                "extracted_value": None,
                "confidence": 0.0,
                "source_text": deficiency_evidence.source_text,
                "source_section": deficiency_evidence.source_section,
                "warning": deficiency_evidence.warning,
            }
        )
    events = cast(list[dict[str, object]], extracted.get("events", []))
    for index, event in enumerate(events, start=1):
        for field_name in ("event_date", "event_type", "event_text"):
            value = event.get(field_name)
            records.append(
                {
                    "audit_id": f"{document_id}-event-{index}-{field_name}",
                    "document_id": document_id,
                    "field_name": f"event.{field_name}",
                    "extraction_method": DETERMINISTIC_METHOD,
                    "extractor_version": CcldFacilityReportsConnector.connector_version,
                    "extracted_value": _audit_value(value),
                    "confidence": 1.0,
                    "source_text": _optional_mapping_str(event, "source_text"),
                    "source_section": _optional_mapping_str(event, "source_section"),
                    "warning": None,
                }
            )
    return records


def _audit_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)
