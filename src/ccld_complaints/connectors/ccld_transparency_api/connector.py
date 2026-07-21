from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ccld_complaints.connectors.ccld_transparency_api.contract import (
    BASE_URL,
    CONNECTOR_VERSION,
    EXPORT_IDS,
    SOURCE_FAMILY_ID,
    complaint_fields,
    expected_headers,
    normalize_bulk_row,
    schema_fingerprint,
    source_family_schema_fingerprint,
)
from ccld_complaints.statewide_facility_source_evaluation import canonical_fingerprint

DEFAULT_TIMEOUT_SECONDS = 60.0
_PROHIBITED_RESPONSE_HEADERS = frozenset(
    {"authorization", "proxy-authorization", "set-cookie", "set-cookie2"}
)
_FACILITY_NUMBER_RE = re.compile(r"^\d+$")
_REPORT_FACILITY_RE = re.compile(
    r"FACILITY\s+NUMBER\s*:?\s*</?[^>]*>*\s*(\d+)|FACILITY\s+NUMBER\s*:?\s*(\d+)",
    re.IGNORECASE,
)


class TransparencyApiConnectorError(ValueError):
    """Raised when a request or source artifact violates the governed contract."""


@dataclass(frozen=True)
class HttpArtifactResponse:
    request_url: str
    final_url: str
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    @property
    def content_type(self) -> str:
        for name, value in self.headers:
            if name.casefold() == "content-type":
                return value.split(";", 1)[0].strip().casefold()
        return ""


class GetTransport(Protocol):
    def get(self, url: str, *, timeout_seconds: float) -> HttpArtifactResponse: ...


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(  # type: ignore[no-untyped-def]
        self, request, response, code, message, headers, new_url
    ):
        raise TransparencyApiConnectorError(
            "Redirects are prohibited for the TransparencyAPI connector."
        )


class NoRedirectGetTransport:
    """Execute one unauthenticated public GET without cookies or redirects."""

    def get(self, url: str, *, timeout_seconds: float) -> HttpArtifactResponse:
        validate_governed_url(url)
        request = Request(url, method="GET")
        opener = build_opener(_RejectRedirectHandler())
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except HTTPError as error:
            return HttpArtifactResponse(
                request_url=url,
                final_url=error.geturl(),
                status=error.code,
                headers=tuple(error.headers.items()),
                body=error.read(),
            )
        with response:
            return HttpArtifactResponse(
                request_url=url,
                final_url=response.geturl(),
                status=response.status,
                headers=tuple(response.headers.items()),
                body=response.read(),
            )


@dataclass(frozen=True)
class PreservedArtifact:
    artifact_id: str
    endpoint_kind: str
    export_id: str | None
    request_url: str
    final_url: str
    retrieved_at: str
    status: int
    response_headers: tuple[tuple[str, str], ...]
    excluded_header_names: tuple[str, ...]
    media_type: str
    content_disposition: str | None
    byte_count: int
    sha256: str
    raw_ref: str

    def manifest_record(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "endpoint_kind": self.endpoint_kind,
            "export_id": self.export_id,
            "request_url": self.request_url,
            "final_url": self.final_url,
            "retrieved_at": self.retrieved_at,
            "status": self.status,
            "response_headers": [list(value) for value in self.response_headers],
            "excluded_header_names": list(self.excluded_header_names),
            "media_type": self.media_type,
            "content_disposition": self.content_disposition,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "raw_ref": self.raw_ref,
        }


@dataclass(frozen=True)
class ComplaintBlock:
    ordinal: int
    raw_values: tuple[str, ...]
    values: Mapping[str, str]


@dataclass(frozen=True)
class ParsedFacilityRow:
    export_id: str
    row_ordinal: int
    facility_number: str | None
    raw_values: tuple[str, ...]
    raw_record: Mapping[str, str]
    normalized_record: Mapping[str, Any]
    complaint_blocks: tuple[ComplaintBlock, ...]
    trailing_values: tuple[str, ...]
    raw_row_sha256: str
    warnings: tuple[str, ...]
    quarantine_categories: tuple[str, ...]


@dataclass(frozen=True)
class ParsedExport:
    export_id: str
    headers: tuple[str, ...]
    rows: tuple[ParsedFacilityRow, ...]
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DetailObservation:
    facility_number: str
    raw_record: Mapping[str, Any]
    contact: Any
    facility_administrator: Any
    detail_status: Any
    facility_type_code: str | None
    sentinel: bool
    quarantine_categories: tuple[str, ...]


@dataclass(frozen=True)
class ReportListItem:
    index: int
    facility_number: str
    control_number: str | None
    report_date: str | None
    raw_record: Mapping[str, Any]


@dataclass(frozen=True)
class ReportHelperValidation:
    selected: ReportListItem
    helper_sha256: str
    report_list_sha256: str
    report_count: int
    quarantine_categories: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotCapture:
    evidence_directory: Path
    manifest_path: Path
    snapshot_id: str
    artifacts: tuple[PreservedArtifact, ...]


class TransparencyApiConnector:
    connector_name = "ccld_transparency_api_facility_reference"
    connector_version = CONNECTOR_VERSION

    def __init__(
        self,
        *,
        transport: GetTransport | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.transport = transport or NoRedirectGetTransport()
        self.timeout_seconds = timeout_seconds

    def capture_snapshot(
        self, repository_root: Path, *, retrieved_at: str | None = None
    ) -> SnapshotCapture:
        recorded_at = retrieved_at or datetime.now(UTC).isoformat()
        run_id = _run_id(recorded_at)
        evidence_directory = (
            repository_root.resolve() / "data/raw/ccld/transparencyapi-facility-reference" / run_id
        )
        evidence_directory.mkdir(parents=True, exist_ok=False)
        artifacts: list[PreservedArtifact] = []
        for export_id in EXPORT_IDS:
            artifacts.append(
                self._fetch_and_preserve(
                    evidence_directory,
                    artifact_id=f"bulk-{export_id}",
                    endpoint_kind="bulk_export",
                    export_id=export_id,
                    url=bulk_export_url(export_id),
                    raw_ref=f"bulk/{export_id}.csv",
                    retrieved_at=recorded_at,
                )
            )
        artifacts.append(
            self._fetch_and_preserve(
                evidence_directory,
                artifact_id="facility-type-taxonomy",
                endpoint_kind="facility_type_taxonomy",
                export_id=None,
                url=f"{BASE_URL}/Group/",
                raw_ref="taxonomy/groups.json",
                retrieved_at=recorded_at,
            )
        )
        artifacts.append(
            self._fetch_and_preserve(
                evidence_directory,
                artifact_id="county-taxonomy",
                endpoint_kind="county_taxonomy",
                export_id=None,
                url=f"{BASE_URL}/CACounty",
                raw_ref="taxonomy/counties.json",
                retrieved_at=recorded_at,
            )
        )
        raw_set_sha256 = canonical_fingerprint(
            [(artifact.artifact_id, artifact.sha256) for artifact in artifacts]
        )
        taxonomy_fingerprints = {
            artifact.endpoint_kind: _json_fingerprint_or_none(
                (evidence_directory / artifact.raw_ref).read_bytes()
            )
            for artifact in artifacts
            if artifact.endpoint_kind in {"facility_type_taxonomy", "county_taxonomy"}
        }
        snapshot_id = f"transparencyapi-{raw_set_sha256[:48]}"
        manifest = {
            "contract_version": CONNECTOR_VERSION,
            "source_family_id": SOURCE_FAMILY_ID,
            "snapshot_id": snapshot_id,
            "recorded_at": recorded_at,
            "source_identity": {
                "base_url": BASE_URL,
                "bulk_export_ids": list(EXPORT_IDS),
                "statewide_enumeration_endpoint": "DownloadStateData",
                "facility_search_used": False,
            },
            "fixed_header_fingerprints": {
                export_id: schema_fingerprint(export_id) for export_id in EXPORT_IDS
            },
            "source_family_schema_fingerprint": source_family_schema_fingerprint(),
            "taxonomy_fingerprints": taxonomy_fingerprints,
            "domain_fingerprint": canonical_fingerprint(taxonomy_fingerprints),
            "raw_response_set_sha256": raw_set_sha256,
            "artifacts": [artifact.manifest_record() for artifact in artifacts],
        }
        manifest_path = evidence_directory / "manifest.json"
        _write_exclusive(
            manifest_path,
            json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n",
        )
        return SnapshotCapture(
            evidence_directory=evidence_directory,
            manifest_path=manifest_path,
            snapshot_id=snapshot_id,
            artifacts=tuple(artifacts),
        )

    def fetch_detail(
        self,
        evidence_directory: Path,
        facility_number: str,
        *,
        retrieved_at: str,
        known_type_codes: frozenset[str] | None = None,
    ) -> tuple[PreservedArtifact, DetailObservation]:
        _validate_facility_number(facility_number)
        artifact = self._fetch_and_preserve(
            evidence_directory,
            artifact_id=f"facility-detail-{facility_number}",
            endpoint_kind="facility_detail",
            export_id=None,
            url=f"{BASE_URL}/FacilityDetail/{facility_number}",
            raw_ref=f"detail/{facility_number}.json",
            retrieved_at=retrieved_at,
        )
        response_bytes = (evidence_directory / artifact.raw_ref).read_bytes()
        return artifact, parse_detail_response(
            response_bytes,
            facility_number=facility_number,
            known_type_codes=known_type_codes,
        )

    def fetch_report_list(
        self, evidence_directory: Path, facility_number: str, *, retrieved_at: str
    ) -> tuple[PreservedArtifact, tuple[ReportListItem, ...]]:
        _validate_facility_number(facility_number)
        artifact = self._fetch_and_preserve(
            evidence_directory,
            artifact_id=f"facility-report-list-{facility_number}",
            endpoint_kind="report_list",
            export_id=None,
            url=f"{BASE_URL}/FacilityReports/{facility_number}",
            raw_ref=f"reports/{facility_number}/list.json",
            retrieved_at=retrieved_at,
        )
        response_bytes = (evidence_directory / artifact.raw_ref).read_bytes()
        return artifact, parse_report_list(response_bytes, facility_number=facility_number)

    def fetch_report_helper(
        self,
        evidence_directory: Path,
        facility_number: str,
        report_list_artifact: PreservedArtifact,
        report_items: Sequence[ReportListItem],
        *,
        index: int,
        retrieved_at: str,
    ) -> tuple[PreservedArtifact, ReportHelperValidation]:
        selected = select_report_item(report_items, index=index)
        if selected.facility_number != facility_number:
            raise TransparencyApiConnectorError("Report list facility does not match the request.")
        url = report_helper_url(facility_number, index)
        artifact = self._fetch_and_preserve(
            evidence_directory,
            artifact_id=f"facility-report-{facility_number}-{index}",
            endpoint_kind="report_document",
            export_id=None,
            url=url,
            raw_ref=f"reports/{facility_number}/{index}.html",
            retrieved_at=retrieved_at,
        )
        body = (evidence_directory / artifact.raw_ref).read_bytes()
        return artifact, validate_report_helper_response(
            artifact,
            body,
            selected=selected,
            report_list_sha256=report_list_artifact.sha256,
            report_count=len(report_items),
        )

    def _fetch_and_preserve(
        self,
        evidence_directory: Path,
        *,
        artifact_id: str,
        endpoint_kind: str,
        export_id: str | None,
        url: str,
        raw_ref: str,
        retrieved_at: str,
    ) -> PreservedArtifact:
        validate_governed_url(url)
        response = self.transport.get(url, timeout_seconds=self.timeout_seconds)
        raw_path = evidence_directory / raw_ref
        _write_exclusive(raw_path, response.body)
        safe_headers: list[tuple[str, str]] = []
        excluded: set[str] = set()
        for name, value in response.headers:
            lowered = name.casefold()
            if lowered in _PROHIBITED_RESPONSE_HEADERS:
                excluded.add(name)
            else:
                safe_headers.append((name, value))
        content_disposition = next(
            (value for name, value in safe_headers if name.casefold() == "content-disposition"),
            None,
        )
        return PreservedArtifact(
            artifact_id=artifact_id,
            endpoint_kind=endpoint_kind,
            export_id=export_id,
            request_url=response.request_url,
            final_url=response.final_url,
            retrieved_at=retrieved_at,
            status=response.status,
            response_headers=tuple(safe_headers),
            excluded_header_names=tuple(sorted(excluded, key=str.casefold)),
            media_type=response.content_type,
            content_disposition=content_disposition,
            byte_count=len(response.body),
            sha256=hashlib.sha256(response.body).hexdigest(),
            raw_ref=raw_ref,
        )


def parse_bulk_csv(
    content: bytes,
    *,
    export_id: str,
    reference_year: int | None,
) -> ParsedExport:
    headers_expected = expected_headers(export_id)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("windows-1252")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        headers = tuple(next(reader))
    except StopIteration:
        return ParsedExport(export_id, (), (), ("bulk export is empty",))
    if headers != headers_expected:
        return ParsedExport(
            export_id,
            headers,
            (),
            ("fixed CSV headers differ from the approved export contract",),
        )
    complaint_start = len(headers_expected) - 1
    block_fields = complaint_fields(export_id)
    rows: list[ParsedFacilityRow] = []
    for ordinal, raw_values in enumerate(reader, start=1):
        if not raw_values or all(not value.strip() for value in raw_values):
            continue
        fixed = list(raw_values[:complaint_start])
        if len(fixed) < complaint_start:
            fixed.extend([""] * (complaint_start - len(fixed)))
        raw_record = dict(zip(headers_expected[:complaint_start], fixed, strict=True))
        tail = tuple(raw_values[complaint_start:])
        blocks: list[ComplaintBlock] = []
        trailing: tuple[str, ...] = ()
        warnings: list[str] = []
        quarantines: list[str] = []
        if not _is_zero_complaint_tail(tail):
            complete_length = len(tail) - (len(tail) % len(block_fields))
            for offset in range(0, complete_length, len(block_fields)):
                values = tuple(tail[offset : offset + len(block_fields)])
                blocks.append(
                    ComplaintBlock(
                        ordinal=len(blocks) + 1,
                        raw_values=values,
                        values=dict(zip(block_fields, values, strict=True)),
                    )
                )
            trailing = tuple(tail[complete_length:])
            if trailing:
                warnings.append("partial complaint block is preserved")
                quarantines.append("malformed_trailing_complaint_block")
        facility_number_literal = raw_record.get("Facility Number", "")
        facility_number = facility_number_literal.strip() or None
        if facility_number is None:
            quarantines.append("blank_facility_number")
        normalized = normalize_bulk_row(raw_record)
        if _status_closed_date_disagree(normalized):
            warnings.append("bulk status and Closed Date require reconciliation")
        warnings.extend(_future_date_warnings(normalized, reference_year=reference_year))
        raw_row_sha256 = hashlib.sha256(
            json.dumps(raw_values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        rows.append(
            ParsedFacilityRow(
                export_id=export_id,
                row_ordinal=ordinal,
                facility_number=facility_number,
                raw_values=tuple(raw_values),
                raw_record=raw_record,
                normalized_record=normalized,
                complaint_blocks=tuple(blocks),
                trailing_values=trailing,
                raw_row_sha256=raw_row_sha256,
                warnings=tuple(sorted(set(warnings))),
                quarantine_categories=tuple(sorted(set(quarantines))),
            )
        )
    return ParsedExport(export_id, headers, tuple(rows), ())


def parse_detail_response(
    content: bytes,
    *,
    facility_number: str,
    known_type_codes: frozenset[str] | None = None,
) -> DetailObservation:
    payload = _json_value(content, label="FacilityDetail response")
    if not isinstance(payload, Mapping):
        raise TransparencyApiConnectorError("FacilityDetail response must be a JSON object.")
    raw = dict(payload)
    sentinel = any("facility number not found" in str(value).casefold() for value in raw.values())
    returned_number = _mapping_value(raw, "FacilityNumber", "FACILITYNUMBER", "FAC_NBR")
    quarantines: list[str] = []
    if sentinel:
        quarantines.append("facility_detail_sentinel")
    if returned_number not in (None, "") and str(returned_number).strip() != facility_number:
        quarantines.append("facility_detail_identity_mismatch")
    type_code = _optional_text(
        _mapping_value(raw, "TYPE", "TypeCode", "FacilityTypeCode", "GROUPID")
    )
    if known_type_codes is not None and type_code and type_code not in known_type_codes:
        quarantines.append("unknown_facility_type_code")
    return DetailObservation(
        facility_number=facility_number,
        raw_record=raw,
        contact=_mapping_value(raw, "CONTACT", "Contact"),
        facility_administrator=_mapping_value(
            raw, "Facility Administrator", "FacilityAdministrator", "ADMINISTRATOR"
        ),
        detail_status=_mapping_value(raw, "STATUS", "FacilityStatus", "FACILITYSTATUS"),
        facility_type_code=type_code,
        sentinel=sentinel,
        quarantine_categories=tuple(quarantines),
    )


def parse_report_list(content: bytes, *, facility_number: str) -> tuple[ReportListItem, ...]:
    payload = _json_value(content, label="FacilityReports list response")
    if isinstance(payload, Mapping):
        items = next(
            (
                value
                for key, value in payload.items()
                if key.casefold() in {"reports", "data", "items"}
            ),
            None,
        )
    else:
        items = payload
    if not isinstance(items, list):
        raise TransparencyApiConnectorError("FacilityReports list response must contain an array.")
    parsed: list[ReportListItem] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise TransparencyApiConnectorError("FacilityReports list item must be an object.")
        raw = dict(item)
        item_number = _mapping_value(raw, "FacilityNumber", "FACILITYNUMBER", "FAC_NUM")
        normalized_number = (
            facility_number if item_number in (None, "") else str(item_number).strip()
        )
        report_page = _mapping_value(raw, "REPORTPAGE", "ReportPage")
        if report_page and "fakeout.gov" in str(report_page).casefold():
            raw["REPORTPAGE_REJECTED"] = True
        parsed.append(
            ReportListItem(
                index=index,
                facility_number=normalized_number,
                control_number=_optional_text(
                    _mapping_value(raw, "ControlNumber", "CONTROLNUMBER", "ComplaintControl")
                ),
                report_date=_optional_text(_mapping_value(raw, "ReportDate", "REPORTDATE", "Date")),
                raw_record=raw,
            )
        )
    return tuple(parsed)


def select_report_item(items: Sequence[ReportListItem], *, index: int) -> ReportListItem:
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise TransparencyApiConnectorError("Report index must be a nonnegative integer.")
    if index >= len(items):
        raise TransparencyApiConnectorError("Report index is outside the preserved report list.")
    return items[index]


def validate_report_helper_response(
    artifact: PreservedArtifact,
    content: bytes,
    *,
    selected: ReportListItem,
    report_list_sha256: str,
    report_count: int,
) -> ReportHelperValidation:
    if artifact.status != 200:
        raise TransparencyApiConnectorError("Report helper response was not HTTP 200.")
    if artifact.final_url != artifact.request_url:
        raise TransparencyApiConnectorError("Report helper response redirected unexpectedly.")
    if artifact.media_type not in {"text/html", "application/xhtml+xml"}:
        raise TransparencyApiConnectorError("Report helper response is not HTML.")
    text = content.decode("utf-8", errors="replace")
    quarantines: list[str] = []
    number_matches = [
        value for pair in _REPORT_FACILITY_RE.findall(text) for value in pair if value
    ]
    if number_matches and selected.facility_number not in number_matches:
        quarantines.append("report_list_helper_facility_mismatch")
    if selected.control_number and selected.control_number not in text:
        quarantines.append("report_list_helper_control_mismatch")
    if selected.report_date and selected.report_date not in text:
        quarantines.append("report_list_helper_date_mismatch")
    return ReportHelperValidation(
        selected=selected,
        helper_sha256=hashlib.sha256(content).hexdigest(),
        report_list_sha256=report_list_sha256,
        report_count=report_count,
        quarantine_categories=tuple(quarantines),
    )


def bulk_export_url(export_id: str) -> str:
    expected_headers(export_id)
    return f"{BASE_URL}/DownloadStateData?{urlencode({'id': export_id})}"


def report_helper_url(facility_number: str, index: int) -> str:
    _validate_facility_number(facility_number)
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise TransparencyApiConnectorError("Report index must be a nonnegative integer.")
    return f"{BASE_URL}/FacilityReports?{urlencode({'facNum': facility_number, 'inx': index})}"


def validate_governed_url(url: str) -> None:
    if "fakeout.gov" in url.casefold():
        raise TransparencyApiConnectorError("Prohibited REPORTPAGE source identity.")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.ccld.dss.ca.gov"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise TransparencyApiConnectorError(
            "Request is outside the approved HTTPS source identity."
        )
    path = parsed.path
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if len({key for key, _value in pairs}) != len(pairs):
        raise TransparencyApiConnectorError("Duplicate query parameters are prohibited.")
    params = dict(pairs)
    endpoint = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    if "FacilitySearch" in path:
        raise TransparencyApiConnectorError("Prohibited source path.")
    if endpoint == f"{BASE_URL}/DownloadStateData":
        if set(params) != {"id"} or params["id"] not in EXPORT_IDS:
            raise TransparencyApiConnectorError(
                "Bulk export request is outside the seven-ID allowlist."
            )
        return
    if endpoint in {f"{BASE_URL}/Group/", f"{BASE_URL}/CACounty"} and not params:
        return
    suffix = path.removeprefix("/transparencyapi/api/")
    if suffix.startswith("FacilityDetail/") and not params:
        _validate_facility_number(suffix.removeprefix("FacilityDetail/"))
        return
    if suffix.startswith("FacilityReports/") and not params:
        _validate_facility_number(suffix.removeprefix("FacilityReports/"))
        return
    if endpoint == f"{BASE_URL}/FacilityReports" and set(params) == {"facNum", "inx"}:
        _validate_facility_number(params["facNum"])
        try:
            index = int(params["inx"])
        except ValueError as error:
            raise TransparencyApiConnectorError("Report index must be an integer.") from error
        if index < 0 or str(index) != params["inx"]:
            raise TransparencyApiConnectorError("Report index must be canonical and nonnegative.")
        return
    raise TransparencyApiConnectorError("Request endpoint is outside the approved allowlist.")


def _is_zero_complaint_tail(tail: Sequence[str]) -> bool:
    return (
        not tail
        or all(not value.strip() for value in tail)
        or (len(tail) == 1 and tail[0].strip().casefold() == "no complaints")
    )


def _status_closed_date_disagree(normalized: Mapping[str, Any]) -> bool:
    status = cast(Mapping[str, Any], normalized["bulk_status"])
    closed_date = cast(Mapping[str, Any], normalized["closed_date"])
    if closed_date.get("state") != "populated":
        return False
    status_value = str(status.get("value") or "").casefold()
    return not any(word in status_value for word in ("closed", "inactive"))


def _future_date_warnings(
    normalized: Mapping[str, Any],
    *,
    reference_year: int | None,
) -> list[str]:
    warnings: list[str] = []
    if reference_year is None:
        return warnings
    for field in ("license_first_date", "closed_date", "last_visit_date"):
        observation = cast(Mapping[str, Any], normalized[field])
        value = str(observation.get("value") or "")
        years = re.findall(r"(?:19|20)\d{2}", value)
        if years and int(years[-1]) > reference_year:
            warnings.append(f"{field} contains a suspicious future date")
    return warnings


def _json_value(content: bytes, *, label: str) -> object:
    try:
        return json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TransparencyApiConnectorError(f"{label} is not valid UTF-8 JSON.") from error


def _json_fingerprint_or_none(content: bytes) -> str | None:
    try:
        value = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return canonical_fingerprint(value)


def _mapping_value(value: Mapping[str, Any], *names: str) -> Any:
    by_casefold = {str(key).casefold(): item for key, item in value.items()}
    return next(
        (by_casefold[name.casefold()] for name in names if name.casefold() in by_casefold), None
    )


def _optional_text(value: object) -> str | None:
    stripped = "" if value is None else str(value).strip()
    return stripped or None


def _validate_facility_number(facility_number: str) -> None:
    if not _FACILITY_NUMBER_RE.fullmatch(facility_number):
        raise TransparencyApiConnectorError("Facility Number must contain digits only.")


def _write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def _run_id(recorded_at: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "", recorded_at)
    return cleaned[:24] or hashlib.sha256(recorded_at.encode()).hexdigest()[:24]
