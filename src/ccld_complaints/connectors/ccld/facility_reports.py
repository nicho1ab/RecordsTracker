from __future__ import annotations

import csv
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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

ReportDocumentLoader = Callable[[SourceDocumentCandidate], SourceDocument | None]
ReportFetcher = Callable[[str], bytes]
ConnectorFactory = Callable[[str], "CcldFacilityReportsConnector"]


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


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []

    def handle_data(self, data: str) -> None:
        for line in data.splitlines():
            cleaned = _clean_text(line)
            if cleaned:
                self.lines.append(cleaned)


class _FacilityDetailReportLinkParser(HTMLParser):
    def __init__(self, facility_number: str) -> None:
        super().__init__(convert_charrefs=True)
        self.facility_number = facility_number
        self.report_links: list[tuple[int, str, str]] = []
        self._active_report: tuple[int, str] | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
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
        )
        self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._active_report is not None:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._active_report is None:
            return
        report_index, source_url = self._active_report
        self.report_links.append(
            (report_index, source_url, _clean_text("".join(self._active_text)))
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
        schema_dir: Path = Path("schemas"),
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
        )
        if candidates or not is_live_discovery:
            return candidates

        report_list_url = f"{BASE_URL}/{self.facility_number}"
        return _candidates_from_report_list_json(
            _fetch_url(report_list_url),
            self.facility_number,
            discovered_at=discovered_at,
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
        source_url_fields = _source_url_fields(document.source_url)

        complaint_received_date = _iso_date(_complaint_received_date(lines))
        report_date = _iso_date(
            _value_after_label(lines, "Report Date:")
            or _value_after_exact_label(lines, "Report Date")
        )
        visit_date = _iso_date(
            _value_after_label(lines, "VISIT DATE:")
            or _value_after_exact_label(lines, "VISIT DATE")
        )
        date_signed = _iso_date(
            _value_after_label(lines, "Date Signed:")
            or _value_after_exact_label(lines, "Date Signed")
        )
        first_activity_date = None
        delay_metrics = _delay_metrics(
            complaint_received_date=complaint_received_date,
            first_investigation_activity_date=first_activity_date,
            visit_date=visit_date,
            report_date=report_date,
            date_signed=date_signed,
        )

        return {
            "source_url": document.source_url,
            "raw_path": document.raw_path.as_posix(),
            "raw_sha256": document.raw_sha256,
            "retrieved_at": document.retrieved_at,
            "content_type": document.content_type,
            "report_index": source_url_fields["report_index"],
            "facility_number": _value_after_label(lines, "FACILITY NUMBER:")
            or _value_after_exact_label(lines, "FACILITY NUMBER"),
            "facility_name": _value_after_label(lines, "FACILITY NAME:")
            or _value_after_exact_label(lines, "FACILITY NAME"),
            "report_type": _report_type(lines),
            "report_date": report_date,
            "date_signed": date_signed,
            "complaint_received_date": complaint_received_date,
            "first_investigation_activity_date": first_activity_date,
            "complaint_control_number": _value_after_label(
                lines, "COMPLAINT CONTROL NUMBER:"
            )
            or _value_after_exact_label(lines, "COMPLAINT CONTROL NUMBER"),
            "allegations": _allegations(lines),
            "finding": _finding(lines),
            "visit_date": visit_date,
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
) -> FacilityIngestionResult:
    if limit is not None and limit < 0:
        raise ValueError("limit must be greater than or equal to 0.")
    if max_requests is not None and max_requests < 0:
        raise ValueError("max_requests must be greater than or equal to 0.")

    active_connector = connector or CcldFacilityReportsConnector(facility_number=facility_number)
    discovered_candidates = active_connector.discover(
        facility_detail_html=facility_detail_html,
        discovered_at=discovered_at,
    )
    candidates = discovered_candidates
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
    normalized: list[str] = []
    seen: set[str] = set()
    for facility_number in facility_numbers:
        cleaned = facility_number.strip()
        if not cleaned:
            continue
        if not cleaned.isdigit():
            raise ValueError(f"Facility number must contain digits only: {facility_number!r}")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    if not normalized:
        raise ValueError("At least one facility number is required.")
    return normalized


def read_facility_numbers_file(path: Path) -> list[str]:
    values: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            for value in row:
                cleaned = value.strip()
                if not cleaned or cleaned.startswith("#"):
                    continue
                if cleaned.casefold() in {"facility_number", "facilitynumber", "facnum"}:
                    continue
                values.append(cleaned)
    return normalize_facility_numbers(values)


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


def discover_facility_report_candidates(
    facility_detail_html: str,
    facility_number: str,
    discovered_at: str | None = None,
) -> list[SourceDocumentCandidate]:
    parser = _FacilityDetailReportLinkParser(facility_number)
    parser.feed(facility_detail_html)

    candidates: list[SourceDocumentCandidate] = []
    seen_indexes: set[int] = set()
    seen_urls: set[str] = set()
    for report_index, source_url, link_text in parser.report_links:
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
            )
        )
    return candidates


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
) -> list[SourceDocumentCandidate]:
    report_list = cast(dict[str, object], json.loads(report_list_content.decode("utf-8")))
    report_array = cast(list[dict[str, object]], report_list.get("REPORTARRAY", []))
    return [
        SourceDocumentCandidate(
            source_name=SOURCE_ID,
            facility_number=facility_number,
            report_index=report_index,
            source_url=_report_source_url(facility_number, report_index),
            discovered_report_date=_iso_date(cast(str | None, report.get("REPORTDATE"))),
            discovered_at=discovered_at,
        )
        for report_index, report in enumerate(report_array)
        if report.get("FACILITYNUMBER") == facility_number
    ]


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


def _next_value(lines: list[str], index: int) -> str | None:
    for value in lines[index + 1 :]:
        if not value.endswith(":"):
            return value
    return None


def _report_type(lines: list[str]) -> str | None:
    for line in lines:
        if line.casefold() == "complaint investigation report":
            return "COMPLAINT INVESTIGATION REPORT"
    return None


def _complaint_received_date(lines: list[str]) -> str | None:
    phrases = (
        "complaint received in our office on",
        "complaint was received in our office on",
    )
    for index, line in enumerate(lines):
        normalized_line = line.casefold()
        for phrase in phrases:
            if phrase in normalized_line:
                inline_value = line[normalized_line.index(phrase) + len(phrase) :].strip(" .:-")
                if inline_value:
                    return inline_value
                return _next_value(lines, index)
    return None


def _allegations(lines: list[str]) -> list[str]:
    start = _line_index_any(
        lines,
        (
            "ALLEGATION(S):",
            "ALLEGATION(S)",
            "ALLEGATION (S):",
            "ALLEGATION (S)",
            "ALLEGATIONS:",
            "ALLEGATIONS",
            "ALLEGATION:",
            "ALLEGATION",
        ),
    )
    end = _line_index_any(lines, ("INVESTIGATION FINDINGS:", "INVESTIGATION FINDING:"))
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