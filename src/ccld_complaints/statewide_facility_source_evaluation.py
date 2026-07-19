from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Protocol, cast
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from jsonschema import validate as jsonschema_validate

from ccld_complaints.utils.hash import sha256_bytes

CONTRACT_VERSION: Final = "issue-490.source-profile.v1"
STATUS_VALUES: Final = frozenset(
    {"pass", "fail", "warning", "blocked", "inconclusive", "not_applicable"}
)
SENSITIVE_QUERY_NAME_PATTERN: Final = re.compile(
    r"(?:authorization|credential|signature|token|cookie|x-amz-)", re.IGNORECASE
)
SECRET_LIKE_PATTERN: Final = re.compile(
    r"(?:AKIA[0-9A-Z]{12,}|x-amz-(?:credential|signature)|bearer\s+[a-z0-9._-]+|"
    r"(?:password|private[_-]?key|client[_-]?secret)\s*[:=])",
    re.IGNORECASE,
)
PERSONAL_PATH_PATTERN: Final = re.compile(r"(?:[A-Za-z]:\\Users\\|/Users/|/home/)")


class FetchTransport(Protocol):
    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse: ...


@dataclass(frozen=True)
class HttpResponse:
    request_url: str
    final_url: str
    status: int
    content_type: str
    body: bytes
    redirect_chain: tuple[str, ...] = ()


@dataclass(frozen=True)
class SnapshotArtifact:
    endpoint_id: str
    request_url: str
    final_endpoint: str
    retrieved_at: str
    status: int
    content_type: str
    byte_count: int
    sha256: str
    artifact_ref: str
    redirect_chain: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint_id": self.endpoint_id,
            "request_url": sanitize_url(self.request_url),
            "final_endpoint": self.final_endpoint,
            "retrieved_at": self.retrieved_at,
            "status": self.status,
            "content_type": self.content_type,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "artifact_ref": self.artifact_ref,
            "redirect_chain": list(self.redirect_chain),
            "warnings": list(self.warnings),
        }


def utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_endpoint_identity(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError("Only an absolute HTTPS endpoint identity is permitted.")
    host = parsed.hostname.casefold()
    port = f":{parsed.port}" if parsed.port and parsed.port != 443 else ""
    return urlunsplit(("https", f"{host}{port}", parsed.path or "/", "", ""))


def sanitize_url(url: str) -> str:
    parsed = urlsplit(url)
    safe_query = [
        (name, value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not SENSITIVE_QUERY_NAME_PATTERN.search(name)
    ]
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(safe_query, doseq=True), "")
    )


class _ExactRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_identities: frozenset[str], maximum_redirects: int = 2) -> None:
        super().__init__()
        self.allowed_identities = allowed_identities
        self.maximum_redirects = maximum_redirects
        self.redirect_chain: list[str] = []

    def redirect_request(  # type: ignore[no-untyped-def]
        self, request, response, code, message, headers, new_url
    ):
        identity = safe_endpoint_identity(new_url)
        if identity not in self.allowed_identities:
            raise ValueError(f"Redirect endpoint is not allowlisted: {identity}")
        if len(self.redirect_chain) >= self.maximum_redirects:
            raise ValueError("Redirect limit exceeded.")
        self.redirect_chain.append(identity)
        return super().redirect_request(request, response, code, message, headers, new_url)


class ExactRedirectTransport:
    def __init__(self, allowed_redirect_endpoints: Iterable[str] = ()) -> None:
        self.allowed_identities = frozenset(
            safe_endpoint_identity(url) for url in allowed_redirect_endpoints
        )

    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse:
        redirect_handler = _ExactRedirectHandler(self.allowed_identities)
        opener = build_opener(redirect_handler)
        request = Request(url, headers={"User-Agent": "RecordsTracker-source-profile/1"})
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except HTTPError as error:
            body = error.read()
            return HttpResponse(
                request_url=url,
                final_url=error.geturl(),
                status=error.code,
                content_type=error.headers.get_content_type(),
                body=body,
                redirect_chain=tuple(redirect_handler.redirect_chain),
            )
        with response:
            body = response.read()
            return HttpResponse(
                request_url=url,
                final_url=response.geturl(),
                status=response.status,
                content_type=response.headers.get_content_type(),
                body=body,
                redirect_chain=tuple(redirect_handler.redirect_chain),
            )


def fetch_and_preserve(
    *,
    endpoint_id: str,
    request_url: str,
    artifact_path: Path,
    artifact_ref: str,
    transport: FetchTransport,
    retrieved_at: str | None = None,
    timeout_seconds: float = 60.0,
) -> SnapshotArtifact:
    response = transport.get(request_url, timeout_seconds=timeout_seconds)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("xb") as output:
        output.write(response.body)
    stored_bytes = artifact_path.read_bytes()
    if stored_bytes != response.body:
        raise OSError("Stored snapshot bytes do not match the fetched response bytes.")
    warnings: list[str] = []
    if response.status < 200 or response.status >= 300:
        warnings.append(f"HTTP status {response.status}")
    return SnapshotArtifact(
        endpoint_id=endpoint_id,
        request_url=request_url,
        final_endpoint=safe_endpoint_identity(response.final_url),
        retrieved_at=retrieved_at or utc_now(),
        status=response.status,
        content_type=response.content_type,
        byte_count=len(stored_bytes),
        sha256=sha256_bytes(stored_bytes),
        artifact_ref=artifact_ref.replace("\\", "/"),
        redirect_chain=tuple(response.redirect_chain),
        warnings=tuple(warnings),
    )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def canonical_fingerprint(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def ordered_schema_fingerprint(fields: Sequence[Mapping[str, Any]]) -> str:
    normalized = [
        {
            "name": str(field.get("name", "")),
            "type": str(field.get("type", "")),
            "alias": str(field.get("alias", "")),
            "nullable": field.get("nullable"),
            "length": field.get("length"),
            "domain": field.get("domain"),
        }
        for field in fields
    ]
    return canonical_fingerprint(normalized)


def parse_json_bytes(content: bytes) -> dict[str, Any]:
    parsed = json.loads(content.decode("utf-8-sig"))
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object response.")
    return cast(dict[str, Any], parsed)


def decode_csv_bytes(content: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace"), "utf-8-replacement"


def parse_csv_bytes(content: bytes) -> tuple[list[str], list[dict[str, str]], str, list[str]]:
    text, encoding = decode_csv_bytes(content)
    warnings: list[str] = []
    stream = io.StringIO(text)
    reader = csv.reader(stream)
    try:
        raw_rows = list(reader)
    except csv.Error as error:
        raise ValueError(f"CSV parse failed at line {reader.line_num}.") from error
    if not raw_rows:
        return [], [], encoding, ["no rows"]
    fields = [value.strip() for value in raw_rows[0]]
    rows: list[dict[str, str]] = []
    for row_number, values in enumerate(raw_rows[1:], start=2):
        if len(values) != len(fields):
            warnings.append(
                f"row {row_number} has {len(values)} columns; expected {len(fields)}"
            )
        padded = values[: len(fields)] + [""] * max(0, len(fields) - len(values))
        rows.append(dict(zip(fields, padded, strict=True)))
    return fields, rows, encoding, warnings


def extract_zip_members(content: bytes) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in sorted(archive.infolist(), key=lambda member: member.filename):
            if info.is_dir():
                continue
            member_bytes = archive.read(info)
            members.append(
                {
                    "name": info.filename.replace("\\", "/"),
                    "byte_count": len(member_bytes),
                    "sha256": sha256_bytes(member_bytes),
                    "content": member_bytes,
                }
            )
    return members


def rows_from_arcgis_response(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    features = payload.get("features", [])
    if not isinstance(features, list):
        raise ValueError("ArcGIS response features must be a list.")
    rows: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, Mapping) or not isinstance(feature.get("attributes"), Mapping):
            raise ValueError("ArcGIS feature is missing an attributes object.")
        rows.append(dict(cast(Mapping[str, Any], feature["attributes"])))
    return rows


def rows_from_geojson_response(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    features = payload.get("features", [])
    if not isinstance(features, list):
        raise ValueError("GeoJSON features must be a list.")
    rows: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, Mapping) or not isinstance(feature.get("properties"), Mapping):
            raise ValueError("GeoJSON feature is missing a properties object.")
        rows.append(dict(cast(Mapping[str, Any], feature["properties"])))
    return rows


def parse_arcgis_layer_html(content: bytes) -> dict[str, Any]:
    text = content.decode("utf-8", errors="replace")

    def first(pattern: str) -> str:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))).strip()

    fields: list[dict[str, Any]] = []
    field_pattern = re.compile(
        r"<li>([^<]+)\s*<i>\(type:\s*([^,\)]+),\s*alias:\s*([^,\)]+).*?"
        r"nullable:\s*(true|false).*?\)</i></li>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in field_pattern.finditer(text):
        fields.append(
            {
                "name": html.unescape(match.group(1)).strip(),
                "type": match.group(2).strip(),
                "alias": html.unescape(match.group(3)).strip(),
                "nullable": match.group(4).casefold() == "true",
                "domain": None,
            }
        )
    invalid_url = "Invalid URL" in text
    return {
        "name": first(r"<b>Name:</b>\s*(.*?)<br"),
        "display_field": first(r"<b>Display Field:</b>\s*(.*?)<br"),
        "geometry_type": first(r"<b>Geometry Type:</b>\s*(.*?)<br"),
        "copyright_text": first(r"<b>Copyright Text:</b>\s*(.*?)<br\s*/?>\s*<br"),
        "max_record_count": _integer_or_none(first(r"<b>Max Record Count:</b>\s*(.*?)<br")),
        "supported_query_formats": first(r"<b>Supported query Formats:</b>\s*(.*?)<br"),
        "object_id_field": first(r"<b>Object ID Field:</b>\s*(.*?)<br"),
        "capabilities": first(r"<b>Capabilities:</b>\s*(.*?)<br"),
        "fields": fields,
        "schema_fingerprint": ordered_schema_fingerprint(fields) if fields else "",
        "invalid_url": invalid_url,
    }


def _integer_or_none(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def extract_public_urls_from_html(content: bytes) -> list[str]:
    text = content.decode("utf-8", errors="replace")
    candidates = re.findall(r"https://[^\s\"'<>]+", html.unescape(text))
    sanitized: set[str] = set()
    for candidate in candidates:
        candidate = candidate.rstrip("),.;")
        try:
            sanitized.add(sanitize_url(candidate))
        except ValueError:
            continue
    return sorted(sanitized)


def parse_next_data_payload(content: bytes) -> dict[str, Any]:
    text = content.decode("utf-8", errors="replace")
    match = re.search(
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}
    parsed = json.loads(html.unescape(match.group(1)))
    if not isinstance(parsed, dict):
        raise ValueError("__NEXT_DATA__ payload must be a JSON object.")
    return cast(dict[str, Any], parsed)


def find_named_objects(value: Any, key: str) -> list[Any]:
    results: list[Any] = []
    if isinstance(value, Mapping):
        for name, child in value.items():
            if name == key:
                results.append(child)
            results.extend(find_named_objects(child, key))
    elif isinstance(value, list):
        for child in value:
            results.extend(find_named_objects(child, key))
    return results


def _normalized_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return re.sub(r"\s+", " ", str(value)).strip()


def canonical_row(row: Mapping[str, Any], fields: Sequence[str]) -> dict[str, str]:
    return {field: _normalized_scalar(row.get(field)) for field in fields}


def row_fingerprint(row: Mapping[str, Any], fields: Sequence[str]) -> str:
    return canonical_fingerprint(canonical_row(row, fields))


def analyze_pagination(
    pages: Sequence[Mapping[str, Any]],
    *,
    object_id_field: str,
    expected_object_ids: Sequence[Any] | None = None,
) -> dict[str, Any]:
    seen: Counter[str] = Counter()
    page_counts: list[int] = []
    terminal_page_observed = False
    malformed_pages: list[int] = []
    for page_index, page in enumerate(pages):
        try:
            rows = rows_from_arcgis_response(page)
        except ValueError:
            malformed_pages.append(page_index)
            continue
        page_counts.append(len(rows))
        if not rows:
            terminal_page_observed = True
        for row in rows:
            seen[_normalized_scalar(row.get(object_id_field))] += 1
    duplicate_ids = sorted(value for value, count in seen.items() if value and count > 1)
    expected = {_normalized_scalar(value) for value in (expected_object_ids or [])}
    observed = {value for value in seen if value}
    omitted_ids = sorted(expected - observed)
    unexpected_ids = sorted(observed - expected) if expected_object_ids is not None else []
    status = (
        "pass"
        if not duplicate_ids
        and not omitted_ids
        and not unexpected_ids
        and not malformed_pages
        and terminal_page_observed
        else "fail"
    )
    return {
        "status": status,
        "page_counts": page_counts,
        "record_count": sum(page_counts),
        "unique_object_id_count": len(observed),
        "duplicate_object_ids": duplicate_ids,
        "omitted_object_ids": omitted_ids,
        "unexpected_object_ids": unexpected_ids,
        "malformed_page_indexes": malformed_pages,
        "terminal_page_observed": terminal_page_observed,
    }


def compare_row_sets(
    left_rows: Sequence[Mapping[str, Any]],
    right_rows: Sequence[Mapping[str, Any]],
    *,
    identifier_field: str,
    compared_fields: Sequence[str],
    left_schema: Sequence[str] | None = None,
    right_schema: Sequence[str] | None = None,
) -> dict[str, Any]:
    def index_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
        indexed: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            identifier = _normalized_scalar(row.get(identifier_field))
            indexed[identifier].append(row_fingerprint(row, compared_fields))
        for fingerprints in indexed.values():
            fingerprints.sort()
        return dict(indexed)

    left = index_rows(left_rows)
    right = index_rows(right_rows)
    left_ids = set(left)
    right_ids = set(right)
    duplicates_left = sorted(identifier for identifier, values in left.items() if len(values) > 1)
    duplicates_right = sorted(identifier for identifier, values in right.items() if len(values) > 1)
    changed = sorted(
        identifier for identifier in left_ids & right_ids if left[identifier] != right[identifier]
    )
    schema_match = (
        left_schema is None
        or right_schema is None
        or list(left_schema) == list(right_schema)
    )
    equivalent = (
        left_ids == right_ids
        and not duplicates_left
        and not duplicates_right
        and not changed
        and schema_match
    )
    return {
        "status": "pass" if equivalent else "fail",
        "verdict": "equivalent" if equivalent else "not_equivalent",
        "left_row_count": len(left_rows),
        "right_row_count": len(right_rows),
        "left_unique_identifier_count": len(left_ids - {""}),
        "right_unique_identifier_count": len(right_ids - {""}),
        "missing_identifier_rows_left": len(left.get("", [])),
        "missing_identifier_rows_right": len(right.get("", [])),
        "left_only_identifiers": sorted((left_ids - right_ids) - {""}),
        "right_only_identifiers": sorted((right_ids - left_ids) - {""}),
        "duplicate_identifiers_left": duplicates_left,
        "duplicate_identifiers_right": duplicates_right,
        "changed_identifiers": changed,
        "schema_match": schema_match,
    }


def value_state(
    *, present: bool, value: Any, validator: Callable[[str], bool] | None = None
) -> str:
    if not present:
        return "absent"
    if value is None:
        return "null"
    normalized = _normalized_scalar(value)
    if not normalized:
        return "blank"
    if validator is not None and not validator(normalized):
        return "invalid"
    return "populated"


def profile_fields(
    rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for field in fields:
        states = Counter(value_state(present=field in row, value=row.get(field)) for row in rows)
        nonblank = [
            _normalized_scalar(row.get(field))
            for row in rows
            if _normalized_scalar(row.get(field))
        ]
        profiles.append(
            {
                "field": field,
                "populated_count": states["populated"],
                "blank_count": states["blank"],
                "null_count": states["null"],
                "absent_count": states["absent"],
                "invalid_count": states["invalid"],
                "distinct_nonblank_count": len(set(nonblank)),
                "normalization_warning_count": 0,
            }
        )
    return profiles


def load_ckan_datastore_pages(
    paths: Sequence[Path], *, expected_total: int | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    page_counts: list[int] = []
    terminal_page_observed = False
    totals: set[int] = set()
    for path in sorted(paths, key=lambda item: item.name):
        payload = parse_json_bytes(path.read_bytes())
        if payload.get("success") is not True:
            raise ValueError(f"Datastore page failed: {path.name}")
        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise ValueError(f"Datastore result missing: {path.name}")
        raw_fields = result.get("fields")
        if isinstance(raw_fields, list):
            current_fields = [dict(field) for field in raw_fields if isinstance(field, Mapping)]
            if fields and current_fields != fields:
                raise ValueError(f"Datastore schema changed across pages: {path.name}")
            fields = current_fields
        raw_rows = result.get("records")
        if not isinstance(raw_rows, list):
            raise ValueError(f"Datastore records missing: {path.name}")
        page_rows = [dict(row) for row in raw_rows if isinstance(row, Mapping)]
        if len(page_rows) != len(raw_rows):
            raise ValueError(f"Datastore page includes a malformed record: {path.name}")
        page_counts.append(len(page_rows))
        terminal_page_observed = terminal_page_observed or len(page_rows) == 0
        rows.extend(page_rows)
        if isinstance(result.get("total"), int):
            totals.add(int(result["total"]))
    observed_ids = [_normalized_scalar(row.get("_id")) for row in rows]
    duplicate_object_ids = sorted(
        identifier
        for identifier, count in Counter(observed_ids).items()
        if identifier and count > 1
    )
    stable_order = observed_ids == sorted(observed_ids, key=_sortable_identifier)
    stated_total = next(iter(totals)) if len(totals) == 1 else None
    total_matches = stated_total == len(rows) and (
        expected_total is None or expected_total == len(rows)
    )
    summary = {
        "status": (
            "pass"
            if terminal_page_observed
            and not duplicate_object_ids
            and stable_order
            and total_matches
            else "fail"
        ),
        "page_counts": page_counts,
        "row_count": len(rows),
        "stated_total": stated_total,
        "terminal_page_observed": terminal_page_observed,
        "duplicate_object_ids": duplicate_object_ids,
        "stable_order": stable_order,
        "total_matches": total_matches,
    }
    return fields, rows, summary


def _sortable_identifier(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (2**63 - 1, value)


def profile_facility_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_id: str,
    identifier_field: str,
    type_field: str,
    status_field: str,
    fields: Sequence[str],
) -> dict[str, Any]:
    identifiers = [_normalized_scalar(row.get(identifier_field)) for row in rows]
    nonblank_identifiers = [identifier for identifier in identifiers if identifier]
    identifier_counts = Counter(nonblank_identifiers)
    status_counts = Counter(_normalized_scalar(row.get(status_field)) for row in rows)
    type_counts = Counter(_normalized_scalar(row.get(type_field)) for row in rows)
    field_profiles = profile_fields(rows, fields)
    for field_profile in field_profiles:
        field = str(field_profile["field"])
        invalid_count = sum(
            1
            for row in rows
            if _normalized_scalar(row.get(field))
            and not _valid_for_field(field, _normalized_scalar(row.get(field)))
        )
        field_profile["invalid_count"] = invalid_count
        field_profile["normalization_warning_count"] = invalid_count
    date_formats: dict[str, dict[str, int]] = {}
    for field in fields:
        if "date" not in field.casefold():
            continue
        formats = Counter(
            _date_format(_normalized_scalar(row.get(field)))
            for row in rows
            if _normalized_scalar(row.get(field))
        )
        date_formats[field] = dict(sorted(formats.items()))
    return {
        "source_id": source_id,
        "row_count": len(rows),
        "unique_facility_identifier_count": len(identifier_counts),
        "missing_facility_identifier_count": len(rows) - len(nonblank_identifiers),
        "duplicate_facility_identifier_count": sum(
            count - 1 for count in identifier_counts.values() if count > 1
        ),
        "duplicate_facility_identifiers": sorted(
            identifier for identifier, count in identifier_counts.items() if count > 1
        ),
        "row_cardinality_per_facility": dict(
            sorted(Counter(identifier_counts.values()).items(), key=lambda item: item[0])
        ),
        "facility_type_counts": [
            {"raw_value": value, "record_count": count}
            for value, count in sorted(type_counts.items())
        ],
        "status_counts": [
            {"raw_value": value, "record_count": count}
            for value, count in sorted(status_counts.items())
        ],
        "field_profiles": field_profiles,
        "date_formats": date_formats,
        "canonical_row_sha256": canonical_fingerprint(
            [canonical_row(row, fields) for row in rows]
        ),
    }


def _date_format(value: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", value):
        return "ISO-like"
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", value):
        return "MM/DD/YYYY-like"
    if re.fullmatch(r"\d{8}", value):
        return "compact-numeric"
    return "other"


def _valid_for_field(field: str, value: str) -> bool:
    normalized_field = field.casefold()
    if "facility_number" in normalized_field or normalized_field in {"fac_nbr", "objectid", "_id"}:
        return value.isdigit()
    if "capacity" in normalized_field:
        try:
            return float(value) >= 0
        except ValueError:
            return False
    if "zip" in normalized_field:
        return bool(re.fullmatch(r"\d{5}(?:-?\d{4})?", value))
    if normalized_field.endswith("state") or normalized_field == "facility_state":
        return value.casefold() in {"ca", "california"}
    if "date" in normalized_field:
        return _date_format(value) != "other"
    return True


def exact_value_contexts(
    sources: Mapping[str, Sequence[Mapping[str, Any]]], value: str
) -> list[dict[str, Any]]:
    contexts: Counter[tuple[str, str]] = Counter()
    for source_id, rows in sources.items():
        for row in rows:
            for field, observed in row.items():
                if _normalized_scalar(observed) == value:
                    contexts[(source_id, str(field))] += 1
    return [
        {"source_id": source_id, "field": field, "record_count": count}
        for (source_id, field), count in sorted(contexts.items())
    ]


def inventory_code_labels(
    rows: Sequence[Mapping[str, Any]],
    *,
    code_field: str,
    label_field: str | None,
    source_id: str,
) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        code = _normalized_scalar(row.get(code_field))
        label = _normalized_scalar(row.get(label_field)) if label_field else ""
        if code:
            counts[(code, label)] += 1
    labels_by_code: dict[str, set[str]] = defaultdict(set)
    for code, label in counts:
        if label:
            labels_by_code[code].add(label)
    result: list[dict[str, Any]] = []
    for (code, label), count in sorted(counts.items()):
        observed_labels = labels_by_code[code]
        evidence_status = "verified_unique" if len(observed_labels) == 1 else "unresolved"
        result.append(
            {
                "source_id": source_id,
                "code_field": code_field,
                "label_field": label_field or "",
                "raw_code": code,
                "raw_label": label,
                "record_count": count,
                "evidence_status": evidence_status,
            }
        )
    return result


def compare_source_coverage(
    left_rows: Sequence[Mapping[str, Any]],
    right_rows: Sequence[Mapping[str, Any]],
    *,
    left_id_field: str,
    right_id_field: str,
    field_pairs: Sequence[tuple[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    left_index = {
        _normalized_scalar(row.get(left_id_field)): row
        for row in left_rows
        if _normalized_scalar(row.get(left_id_field))
    }
    right_index = {
        _normalized_scalar(row.get(right_id_field)): row
        for row in right_rows
        if _normalized_scalar(row.get(right_id_field))
    }
    shared = sorted(set(left_index) & set(right_index))
    conflicts: list[dict[str, Any]] = []
    for identifier in shared:
        left_row = left_index[identifier]
        right_row = right_index[identifier]
        for left_field, right_field in field_pairs:
            left_value = _normalized_scalar(left_row.get(left_field))
            right_value = _normalized_scalar(right_row.get(right_field))
            if left_value and right_value and left_value.casefold() != right_value.casefold():
                conflicts.append(
                    {
                        "facility_identifier": identifier,
                        "left_field": left_field,
                        "right_field": right_field,
                        "left_value_fingerprint": sha256_bytes(left_value.encode("utf-8")),
                        "right_value_fingerprint": sha256_bytes(right_value.encode("utf-8")),
                        "category": "conflicting_nonblank",
                    }
                )
    summary = {
        "left_row_count": len(left_rows),
        "right_row_count": len(right_rows),
        "shared_identifier_count": len(shared),
        "left_only_identifier_count": len(set(left_index) - set(right_index)),
        "right_only_identifier_count": len(set(right_index) - set(left_index)),
        "conflicting_nonblank_value_count": len(conflicts),
    }
    return summary, conflicts


def compare_content_snapshots(
    previous_rows: Sequence[Mapping[str, Any]],
    current_rows: Sequence[Mapping[str, Any]],
    *,
    identifier_field: str,
    fields: Sequence[str],
    previous_bytes_sha256: str,
    current_bytes_sha256: str,
    previous_schema_fingerprint: str,
    current_schema_fingerprint: str,
    metadata_changed: bool,
) -> dict[str, Any]:
    row_comparison = compare_row_sets(
        previous_rows,
        current_rows,
        identifier_field=identifier_field,
        compared_fields=fields,
    )
    return {
        "status": "pass",
        "metadata_changed": metadata_changed,
        "byte_changed": previous_bytes_sha256 != current_bytes_sha256,
        "schema_changed": previous_schema_fingerprint != current_schema_fingerprint,
        "row_set_changed": bool(
            row_comparison["left_only_identifiers"]
            or row_comparison["right_only_identifiers"]
            or row_comparison["duplicate_identifiers_left"]
            or row_comparison["duplicate_identifiers_right"]
        ),
        "field_value_changed": bool(row_comparison["changed_identifiers"]),
        "comparison": row_comparison,
    }


def output_envelope(
    output_type: str,
    data: Mapping[str, Any],
    *,
    generated_at: str,
    status: str = "pass",
    warnings: Sequence[str] = (),
) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise ValueError(f"Unsupported finite status: {status}")
    return {
        "contract_version": CONTRACT_VERSION,
        "output_type": output_type,
        "generated_at": generated_at,
        "status": status,
        "warnings": list(warnings),
        "data": dict(data),
    }


def write_json_output(path: Path, payload: Mapping[str, Any], schema: Mapping[str, Any]) -> str:
    jsonschema_validate(instance=payload, schema=schema)
    content = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    assert_safe_output(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return sha256_bytes(content.encode("utf-8"))


def write_csv_output(
    path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=fieldnames,
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in sorted(rows, key=lambda item: tuple(str(item.get(name, "")) for name in fieldnames)):
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    content = stream.getvalue()
    assert_safe_output(content)
    path.write_text(content, encoding="utf-8", newline="\n")
    return sha256_bytes(content.encode("utf-8"))


def assert_safe_output(text: str) -> None:
    if SECRET_LIKE_PATTERN.search(text):
        raise ValueError("Output contains a secret-like value.")
    if PERSONAL_PATH_PATTERN.search(text):
        raise ValueError("Output contains an absolute personal path.")


def load_output_schema(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Evaluation schema must be a JSON object.")
    return cast(dict[str, Any], parsed)


def describe_zip(content: bytes) -> dict[str, Any]:
    members = extract_zip_members(content)
    return {
        "member_count": len(members),
        "members": [
            {"name": member["name"], "byte_count": member["byte_count"], "sha256": member["sha256"]}
            for member in members
        ],
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
