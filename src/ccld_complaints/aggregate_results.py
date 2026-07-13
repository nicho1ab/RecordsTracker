from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

AggregateStatus = Literal[
    "available",
    "zero",
    "unavailable",
    "partial",
    "truncated",
    "error",
]

AGGREGATE_STATUSES: tuple[AggregateStatus, ...] = (
    "available",
    "zero",
    "unavailable",
    "partial",
    "truncated",
    "error",
)

DATE_DIMENSION_LABELS: Mapping[str, str] = {
    "complaint_received_date": "Complaint received date",
    "first_investigation_activity_date": "First investigation activity date",
    "visit_date": "Visit date",
    "report_date": "Report date",
    "date_signed": "Date signed",
    "latest_supported_activity": "Latest supported activity date",
    "any_review_date": "Any supported complaint or report date",
}


@dataclass(frozen=True)
class AggregateResult:
    value: int | float | None
    denominator: str
    eligible_count: int
    returned_count: int
    source_coverage_count: int
    source_unavailable_count: int
    filtered_count: int
    outside_range_count: int
    limit: int | None
    truncated: bool
    status: AggregateStatus
    cause: str
    date_dimension: str
    query_start: str | None
    query_end: str | None

    def __post_init__(self) -> None:
        for field_name in (
            "eligible_count",
            "returned_count",
            "source_coverage_count",
            "source_unavailable_count",
            "filtered_count",
            "outside_range_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must not be negative.")
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be at least 1 when supplied.")
        if not self.denominator.strip():
            raise ValueError("denominator must describe the record universe.")
        if not self.cause.strip():
            raise ValueError("cause must explain the aggregate status.")
        if self.status not in AGGREGATE_STATUSES:
            raise ValueError(f"Unsupported aggregate status: {self.status}")
        if self.status in {"unavailable", "error"} and self.value is not None:
            raise ValueError("Unavailable and error results must not use a numeric value.")
        if self.status == "zero" and self.value != 0:
            raise ValueError("Zero results must use numeric value 0.")
        if self.truncated != (self.status == "truncated"):
            raise ValueError("truncated must agree with the truncated status.")
        if self.truncated and self.limit is None:
            raise ValueError("A truncated result requires an explicit limit.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_aggregate_result(
    *,
    value: int | float | None,
    denominator: str,
    eligible_count: int,
    returned_count: int,
    source_coverage_count: int,
    source_unavailable_count: int,
    filtered_count: int = 0,
    outside_range_count: int = 0,
    limit: int | None = None,
    date_dimension: str = "complaint_received_date",
    query_start: str | None = None,
    query_end: str | None = None,
    error: str | None = None,
) -> AggregateResult:
    validate_date_dimension(date_dimension)
    truncated = limit is not None and returned_count < eligible_count
    if error is not None:
        status: AggregateStatus = "error"
        result_value = None
        cause = f"The aggregate query failed: {error}"
        truncated = False
    elif source_coverage_count == 0 and source_unavailable_count > 0:
        status = "unavailable"
        result_value = None
        cause = (
            "The required source fields are unavailable for all eligible records; "
            "no numeric result is reported."
        )
        truncated = False
    elif truncated:
        status = "truncated"
        result_value = value
        cause = (
            f"An explicit limit returned {returned_count} of {eligible_count} eligible "
            f"records (limit {limit})."
        )
    elif source_unavailable_count > 0:
        status = "partial"
        result_value = value
        cause = (
            f"Required source fields are available for {source_coverage_count} of "
            f"{eligible_count} eligible records; {source_unavailable_count} are unavailable."
        )
    elif value == 0:
        status = "zero"
        result_value = 0
        if eligible_count == 0 and outside_range_count:
            cause = (
                f"No eligible records fall within the selected range; "
                f"{outside_range_count} record(s) are outside it."
            )
        elif eligible_count == 0 and filtered_count:
            cause = (
                f"No records meet the active eligibility filters; "
                f"{filtered_count} record(s) were filtered out."
            )
        else:
            cause = "Complete eligible source coverage contains zero qualifying records."
    else:
        status = "available"
        result_value = value
        cause = "The result includes every eligible record in the selected range."
    return AggregateResult(
        value=result_value,
        denominator=denominator,
        eligible_count=eligible_count,
        returned_count=returned_count,
        source_coverage_count=source_coverage_count,
        source_unavailable_count=source_unavailable_count,
        filtered_count=filtered_count,
        outside_range_count=outside_range_count,
        limit=limit,
        truncated=truncated,
        status=status,
        cause=cause,
        date_dimension=date_dimension,
        query_start=query_start,
        query_end=query_end,
    )


def aggregate_result_from_mapping(values: Mapping[str, Any]) -> AggregateResult:
    status = values.get("status")
    if status not in AGGREGATE_STATUSES:
        raise ValueError(f"Unsupported aggregate status: {status}")
    return AggregateResult(
        value=_numeric_or_none(values.get("value")),
        denominator=_required_string(values, "denominator"),
        eligible_count=_required_int(values, "eligible_count"),
        returned_count=_required_int(values, "returned_count"),
        source_coverage_count=_required_int(values, "source_coverage_count"),
        source_unavailable_count=_required_int(values, "source_unavailable_count"),
        filtered_count=_required_int(values, "filtered_count"),
        outside_range_count=_required_int(values, "outside_range_count"),
        limit=_optional_int(values.get("limit")),
        truncated=_required_bool(values, "truncated"),
        status=cast(AggregateStatus, status),
        cause=_required_string(values, "cause"),
        date_dimension=_required_string(values, "date_dimension"),
        query_start=_optional_string(values.get("query_start")),
        query_end=_optional_string(values.get("query_end")),
    )


def validate_date_dimension(value: str) -> str:
    if value not in DATE_DIMENSION_LABELS:
        allowed = ", ".join(DATE_DIMENSION_LABELS)
        raise ValueError(f"date_dimension must be one of: {allowed}.")
    return value


def date_dimension_label(value: str) -> str:
    return DATE_DIMENSION_LABELS[validate_date_dimension(value)]


def _required_string(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str):
        raise TypeError(f"Expected {key} to be a string.")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Expected a string or null.")
    return value


def _required_int(values: Mapping[str, Any], key: str) -> int:
    value = values.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"Expected {key} to be an integer.")
    return value


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("Expected an integer or null.")
    return value


def _required_bool(values: Mapping[str, Any], key: str) -> bool:
    value = values.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"Expected {key} to be a boolean.")
    return value


def _numeric_or_none(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("Expected value to be numeric or null.")
    return value
