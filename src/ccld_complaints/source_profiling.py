from __future__ import annotations

import codecs
import csv
import io
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ccld_complaints.utils.hash import sha256_bytes

DEFAULT_SOURCE_ROOT = Path("data/raw/source-profiling")
DEFAULT_OUTPUT_DIR = Path("data/processed/source-profiling")
DEFAULT_LOG_PATH = Path("data/logs/source-profiling.log")

MISSING_VALUE_MARKERS = {"", "-", "na", "n/a", "none", "null", "unknown"}
DATE_HEADER_PATTERN = re.compile(r"date|updated|created|effective|expires?|closed|opened", re.I)
DATE_VALUE_PATTERN = re.compile(
    r"^(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-\d{1,2}-\d{2,4})$"
)
IDENTIFIER_HEADER_PATTERN = re.compile(
    r"(^|[_\s-])(id|identifier|number|num|no|code|license|lic|facility[_\s-]*(?:id|number|no))($|[_\s-])",
    re.I,
)
FACILITY_IDENTIFIER_HEADER_PATTERN = re.compile(
    r"facility|source|record|license|licen[cs]e|provider",
    re.I,
)
GEOGRAPHY_HEADER_PATTERN = re.compile(
    r"county|city|state|zip|postal|address|latitude|longitude|location|region|regional|district|geo",
    re.I,
)


@dataclass(frozen=True)
class CsvProfileOptions:
    sample_values_per_column: int = 3
    sample_value_max_length: int = 80
    unexpected_row_sample_limit: int = 25
    detection_value_limit: int = 50


@dataclass
class ColumnAccumulator:
    index: int
    header_name: str
    missing_value_count: int = 0
    sample_values: list[str] = field(default_factory=list)
    detection_values: list[str] = field(default_factory=list)


def profile_csv_tree(
    source_root: Path = DEFAULT_SOURCE_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    log_path: Path = DEFAULT_LOG_PATH,
    workspace_root: Path = Path("."),
    options: CsvProfileOptions | None = None,
) -> dict[str, Any]:
    selected_options = options or CsvProfileOptions()
    resolved_source_root = source_root.resolve()
    csv_paths = _find_csv_files(resolved_source_root)
    skipped_non_csv_count = _count_non_csv_files(resolved_source_root)

    profiles = [
        profile_csv_file(path, resolved_source_root, workspace_root, selected_options)
        for path in csv_paths
    ]
    summary = _build_summary(source_root, profiles, skipped_non_csv_count)

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_summary(output_dir / "csv-profile-summary.json", summary)
    _write_csv_summary(output_dir / "csv-profile-summary.csv", profiles)
    log_path.write_text(_format_log(summary), encoding="utf-8")
    return summary


def profile_csv_file(
    path: Path,
    source_root: Path,
    workspace_root: Path = Path("."),
    options: CsvProfileOptions | None = None,
    dialect: Any | None = None,
) -> dict[str, Any]:
    selected_options = options or CsvProfileOptions()
    content = path.read_bytes()
    decoded_text, encoding = _decode_bytes(content)
    selected_dialect = dialect or _detect_dialect(decoded_text)
    rows, parser_warnings = _read_csv_rows(decoded_text, selected_dialect)

    header_names = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []
    column_count = len(header_names)
    duplicate_headers = _duplicate_headers(header_names)
    blank_header_indexes = [
        index + 1 for index, name in enumerate(header_names) if name.strip() == ""
    ]
    columns = [ColumnAccumulator(index + 1, header) for index, header in enumerate(header_names)]
    unexpected_rows = _profile_data_rows(data_rows, columns, column_count, selected_options)
    column_profiles = [_column_profile(column) for column in columns]
    suitability_reasons = _suitability_reasons(
        header_names=header_names,
        row_count=len(data_rows),
        parser_warning_count=len(parser_warnings),
    )

    return {
        "source_file_path": _display_path(path, workspace_root, source_root),
        "source_relative_path": _relative_path(path, source_root),
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256_bytes(content),
        "encoding": encoding,
        "row_count": len(data_rows),
        "column_count": column_count,
        "header_names": header_names,
        "duplicate_headers": duplicate_headers,
        "has_duplicate_headers": len(duplicate_headers) > 0,
        "blank_header_indexes": blank_header_indexes,
        "has_blank_headers": len(blank_header_indexes) > 0,
        "malformed_row_count": len(unexpected_rows),
        "parser_warning_count": len(parser_warnings),
        "parser_warnings": parser_warnings,
        "rows_with_unexpected_column_count": unexpected_rows,
        "columns": column_profiles,
        "date_like_column_candidates": _candidate_names(column_profiles, "date_like_candidate"),
        "identifier_like_column_candidates": _candidate_names(
            column_profiles, "identifier_like_candidate"
        ),
        "likely_facility_number_source_identifier_candidates": _candidate_names(
            column_profiles, "facility_number_source_identifier_candidate"
        ),
        "likely_county_geography_candidates": _candidate_names(
            column_profiles, "county_geography_candidate"
        ),
        "suitable_for_tiny_fixture_creation": len(suitability_reasons) == 0,
        "suitability_reasons": suitability_reasons,
    }


def _find_csv_files(source_root: Path) -> list[Path]:
    if not source_root.exists():
        return []
    return sorted(
        path for path in source_root.rglob("*") if path.is_file() and path.suffix.lower() == ".csv"
    )


def _count_non_csv_files(source_root: Path) -> int:
    if not source_root.exists():
        return 0
    return sum(
        1 for path in source_root.rglob("*") if path.is_file() and path.suffix.lower() != ".csv"
    )


def _decode_bytes(content: bytes) -> tuple[str, str]:
    if content.startswith(codecs.BOM_UTF16_LE) or content.startswith(codecs.BOM_UTF16_BE):
        return content.decode("utf-16"), "utf-16"
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace"), "utf-8-replacement"


def _detect_dialect(text: str) -> Any:
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample)
    except csv.Error:
        return csv.get_dialect("excel")


def _read_csv_rows(text: str, dialect: Any) -> tuple[list[list[str]], list[str]]:
    rows: list[list[str]] = []
    warnings: list[str] = []
    stream = io.StringIO(text)
    try:
        reader = csv.reader(stream, dialect=dialect, strict=True)
    except (TypeError, ValueError) as error:
        warnings.append(f"dialect warning: {error}; retried with standard CSV dialect")
        stream = io.StringIO(text)
        reader = csv.reader(stream, dialect=csv.get_dialect("excel"), strict=True)
    try:
        for row in reader:
            rows.append(row)
    except csv.Error as error:
        warnings.append(f"line {reader.line_num}: {error}")
    return rows, warnings


def _duplicate_headers(header_names: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    duplicates: set[str] = set()
    for header in header_names:
        normalized = header.strip().casefold()
        if not normalized:
            continue
        if normalized in seen:
            duplicates.add(seen[normalized])
        else:
            seen[normalized] = header.strip()
    return sorted(duplicates)


def _profile_data_rows(
    data_rows: list[list[str]],
    columns: list[ColumnAccumulator],
    column_count: int,
    options: CsvProfileOptions,
) -> list[dict[str, int]]:
    unexpected_rows: list[dict[str, int]] = []
    for row_offset, row in enumerate(data_rows, start=2):
        if len(row) != column_count and len(unexpected_rows) < options.unexpected_row_sample_limit:
            unexpected_rows.append(
                {
                    "row_number": row_offset,
                    "expected_column_count": column_count,
                    "actual_column_count": len(row),
                }
            )
        for column_index, column in enumerate(columns):
            value = row[column_index] if column_index < len(row) else ""
            _record_column_value(column, value, options)
    return unexpected_rows


def _record_column_value(
    column: ColumnAccumulator, value: str, options: CsvProfileOptions) -> None:
    normalized = value.strip()
    if _is_missing(normalized):
        column.missing_value_count += 1
        return
    safe_value = _safe_sample_value(normalized, options.sample_value_max_length)
    if (
        safe_value not in column.sample_values
        and len(column.sample_values) < options.sample_values_per_column
    ):
        column.sample_values.append(safe_value)
    if len(column.detection_values) < options.detection_value_limit:
        column.detection_values.append(normalized)


def _is_missing(value: str) -> bool:
    return value.strip().casefold() in MISSING_VALUE_MARKERS


def _safe_sample_value(value: str, max_length: int) -> str:
    collapsed = re.sub(r"\s+", " ", value).strip()
    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[: max_length - 3]}..."


def _column_profile(column: ColumnAccumulator) -> dict[str, Any]:
    return {
        "index": column.index,
        "header_name": column.header_name,
        "missing_value_count": column.missing_value_count,
        "sample_values": column.sample_values,
        "date_like_candidate": _is_date_like(column.header_name, column.detection_values),
        "identifier_like_candidate": _is_identifier_like(
            column.header_name, column.detection_values
        ),
        "facility_number_source_identifier_candidate": _is_facility_identifier_like(
            column.header_name, column.detection_values
        ),
        "county_geography_candidate": _is_geography_like(column.header_name),
    }


def _is_date_like(header: str, values: list[str]) -> bool:
    if DATE_HEADER_PATTERN.search(header):
        return True
    return _ratio_at_least(values, lambda value: bool(DATE_VALUE_PATTERN.match(value)), 0.6)


def _is_identifier_like(header: str, values: list[str]) -> bool:
    if IDENTIFIER_HEADER_PATTERN.search(_normalized_header(header)):
        return True
    return _ratio_at_least(values, _looks_like_identifier_value, 0.8)


def _is_facility_identifier_like(header: str, values: list[str]) -> bool:
    normalized_header = _normalized_header(header)
    if (
        FACILITY_IDENTIFIER_HEADER_PATTERN.search(normalized_header)
        and IDENTIFIER_HEADER_PATTERN.search(normalized_header)
    ):
        return True
    return "facilitynumber" in normalized_header or _ratio_at_least(
        values, lambda value: value.isdigit() and 6 <= len(value) <= 12, 0.8
    )


def _is_geography_like(header: str) -> bool:
    return bool(GEOGRAPHY_HEADER_PATTERN.search(header))


def _looks_like_identifier_value(value: str) -> bool:
    compact = re.sub(r"[\s-]", "", value)
    return (
        compact.isalnum()
        and any(character.isdigit() for character in compact)
        and len(compact) >= 3
    )


def _ratio_at_least(
    values: list[str], predicate: Callable[[str], bool], threshold: float
) -> bool:
    if not values:
        return False
    matches = sum(1 for value in values if predicate(value))
    return matches / len(values) >= threshold


def _normalized_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header.strip().casefold()).strip("_")


def _candidate_names(column_profiles: list[dict[str, Any]], key: str) -> list[str]:
    candidates: list[str] = []
    for column in column_profiles:
        if column[key]:
            header = str(column["header_name"]).strip() or f"column_{column['index']}"
            candidates.append(header)
    return candidates


def _suitability_reasons(
    header_names: list[str], row_count: int, parser_warning_count: int
) -> list[str]:
    reasons: list[str] = []
    if not header_names:
        reasons.append("no header row detected")
    if row_count == 0:
        reasons.append("no data rows detected")
    if parser_warning_count > 0:
        reasons.append("parser warnings require review")
    if header_names and all(header.strip() == "" for header in header_names):
        reasons.append("all detected headers are blank")
    return reasons


def _build_summary(
    source_root: Path, profiles: list[dict[str, Any]], skipped_non_csv_count: int
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(tz=UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "source_root": source_root.as_posix(),
        "outputs_are_local_only": True,
        "raw_files_modified": False,
        "imports_data": False,
        "creates_canonical_fields": False,
        "profiles": profiles,
        "totals": {
            "csv_file_count": len(profiles),
            "skipped_non_csv_file_count": skipped_non_csv_count,
            "total_file_size_bytes": sum(int(profile["file_size_bytes"]) for profile in profiles),
            "total_row_count": sum(int(profile["row_count"]) for profile in profiles),
            "total_parser_warning_count": sum(
                int(profile["parser_warning_count"]) for profile in profiles
            ),
            "total_malformed_row_count": sum(
                int(profile["malformed_row_count"]) for profile in profiles
            ),
            "suitable_file_count": sum(
                1 for profile in profiles if bool(profile["suitable_for_tiny_fixture_creation"])
            ),
        },
    }


def _write_json_summary(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv_summary(path: Path, profiles: list[dict[str, Any]]) -> None:
    fieldnames = [
        "source_file_path",
        "file_name",
        "file_size_bytes",
        "sha256",
        "encoding",
        "row_count",
        "column_count",
        "has_duplicate_headers",
        "duplicate_headers",
        "has_blank_headers",
        "blank_header_indexes",
        "malformed_row_count",
        "parser_warning_count",
        "unexpected_column_count_row_count",
        "date_like_column_candidates",
        "identifier_like_column_candidates",
        "likely_facility_number_source_identifier_candidates",
        "likely_county_geography_candidates",
        "suitable_for_tiny_fixture_creation",
        "suitability_reasons",
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for profile in profiles:
            writer.writerow(
                {
                    "source_file_path": profile["source_file_path"],
                    "file_name": profile["file_name"],
                    "file_size_bytes": profile["file_size_bytes"],
                    "sha256": profile["sha256"],
                    "encoding": profile["encoding"],
                    "row_count": profile["row_count"],
                    "column_count": profile["column_count"],
                    "has_duplicate_headers": profile["has_duplicate_headers"],
                    "duplicate_headers": "; ".join(profile["duplicate_headers"]),
                    "has_blank_headers": profile["has_blank_headers"],
                    "blank_header_indexes": "; ".join(
                        str(index) for index in profile["blank_header_indexes"]
                    ),
                    "malformed_row_count": profile["malformed_row_count"],
                    "parser_warning_count": profile["parser_warning_count"],
                    "unexpected_column_count_row_count": len(
                        profile["rows_with_unexpected_column_count"]
                    ),
                    "date_like_column_candidates": "; ".join(
                        profile["date_like_column_candidates"]
                    ),
                    "identifier_like_column_candidates": "; ".join(
                        profile["identifier_like_column_candidates"]
                    ),
                    "likely_facility_number_source_identifier_candidates": "; ".join(
                        profile["likely_facility_number_source_identifier_candidates"]
                    ),
                    "likely_county_geography_candidates": "; ".join(
                        profile["likely_county_geography_candidates"]
                    ),
                    "suitable_for_tiny_fixture_creation": profile[
                        "suitable_for_tiny_fixture_creation"
                    ],
                    "suitability_reasons": "; ".join(profile["suitability_reasons"]),
                }
            )


def _format_log(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    lines = [
        "Source profiling run",
        f"Generated at: {summary['generated_at']}",
        f"Source root: {summary['source_root']}",
        f"CSV files profiled: {totals['csv_file_count']}",
        f"Non-CSV files skipped: {totals['skipped_non_csv_file_count']}",
        f"Total rows: {totals['total_row_count']}",
        f"Parser warnings: {totals['total_parser_warning_count']}",
        f"Malformed or irregular rows: {totals['total_malformed_row_count']}",
        f"Suitable for later tiny fixture creation: {totals['suitable_file_count']}",
        "Local-only boundary: no raw files modified, no import, no schema changes, no connectors.",
    ]
    return "\n".join(lines) + "\n"


def _display_path(path: Path, workspace_root: Path, source_root: Path) -> str:
    for root in (workspace_root.resolve(), source_root.resolve()):
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError:
            continue
    return path.name


def _relative_path(path: Path, source_root: Path) -> str:
    try:
        return path.resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError:
        return path.name