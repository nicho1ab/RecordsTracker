from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from ccld_complaints.aggregate_readiness_evidence import (
    OUTPUT_FILES,
    write_aggregate_readiness_evidence,
)
from ccld_complaints.aggregate_results import (
    AggregateResult,
    aggregate_result_from_mapping,
    build_aggregate_result,
)


def test_aggregate_result_distinguishes_zero_unavailable_partial_and_truncated() -> None:
    zero = build_aggregate_result(
        value=0,
        denominator="loaded complaint records",
        eligible_count=3,
        returned_count=3,
        source_coverage_count=3,
        source_unavailable_count=0,
    )
    unavailable = build_aggregate_result(
        value=None,
        denominator="loaded complaint records",
        eligible_count=2,
        returned_count=0,
        source_coverage_count=0,
        source_unavailable_count=2,
    )
    partial = build_aggregate_result(
        value=2,
        denominator="loaded complaint records",
        eligible_count=3,
        returned_count=3,
        source_coverage_count=2,
        source_unavailable_count=1,
    )
    truncated = build_aggregate_result(
        value=10,
        denominator="loaded complaint records",
        eligible_count=125,
        returned_count=10,
        source_coverage_count=125,
        source_unavailable_count=0,
        limit=10,
    )

    assert zero.status == "zero"
    assert "zero qualifying" in zero.cause
    assert unavailable.status == "unavailable"
    assert unavailable.value is None
    assert partial.status == "partial"
    assert partial.source_unavailable_count == 1
    assert truncated.status == "truncated"
    assert truncated.truncated is True
    assert "10 of 125" in truncated.cause


def test_aggregate_result_serialization_round_trips_postgresql_style_mapping() -> None:
    result = build_aggregate_result(
        value=4,
        denominator="authorized complaint records",
        eligible_count=4,
        returned_count=4,
        source_coverage_count=4,
        source_unavailable_count=0,
        date_dimension="first_investigation_activity_date",
        query_start="2026-01-01",
        query_end="2026-01-31",
    )

    assert aggregate_result_from_mapping(result.to_dict()) == result


@pytest.mark.parametrize("status", ["unavailable", "error"])
def test_unavailable_and_error_cannot_be_numeric_zero(status: str) -> None:
    values = build_aggregate_result(
        value=None,
        denominator="authorized complaint records",
        eligible_count=1,
        returned_count=0,
        source_coverage_count=0,
        source_unavailable_count=1,
    ).to_dict()
    values["status"] = status
    values["value"] = 0

    with pytest.raises(ValueError, match="must not use a numeric value"):
        AggregateResult(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("mode", ["local", "runtime"])
def test_aggregate_readiness_evidence_modes_are_safe_and_complete(
    tmp_path: Path,
    mode: str,
) -> None:
    output_dir = tmp_path / mode
    manifest = write_aggregate_readiness_evidence(output_dir, mode=mode)  # type: ignore[arg-type]

    assert {path.name for path in output_dir.iterdir()} == set(OUTPUT_FILES)
    assert manifest["failed_assertion_count"] == 0
    assert manifest["passed_assertion_count"] == manifest["assertion_count"]
    assert manifest["execution"]["actual_production_style_store_inspected"] is False
    assert manifest["existing_postgresql_rows_require_regeneration_or_reimport"] is True
    assert manifest["safe_production_refresh_command"] is None

    aggregate_rows = list(
        csv.DictReader((output_dir / "aggregate-results.csv").open(encoding="utf-8"))
    )
    assert aggregate_rows
    assert all(row["denominator"] for row in aggregate_rows)
    assert all(row["date_dimension"] for row in aggregate_rows)
    assert all(row["cause"] for row in aggregate_rows)
    assert next(
        row for row in aggregate_rows if row["scenario"] == "over-100-no-limit"
    )["returned_count"] == "125"
    assert next(
        row for row in aggregate_rows if row["scenario"] == "explicit-limit"
    )["truncated"] == "True"

    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
    )
    assert "900000001" not in combined
    assert "900000002" not in combined
    assert "C:\\Users\\" not in combined
    json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
