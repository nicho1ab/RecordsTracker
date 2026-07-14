from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

PresentationValueKind = Literal["text", "number", "date", "boolean"]
PresentationValueState = Literal[
    "present",
    "verified_zero",
    "present_blank",
    "null",
    "absent",
    "source_unavailable",
    "not_applicable",
    "undated",
    "invalid",
    "unsupported",
    "explicit_unknown",
]

NOT_PROVIDED = "Not provided"
DATE_NOT_PROVIDED = "Date not provided"
SOURCE_UNAVAILABLE = "Not available from source"
NOT_APPLICABLE = "Not applicable"
DATE_NOT_AVAILABLE = "Date not available"
INVALID_SOURCE_VALUE = "Invalid source value"
NOT_COLLECTED = "Not collected"

DATE_FIELDS = frozenset(
    {
        "complaint_received_date",
        "first_investigation_activity_date",
        "visit_date",
        "report_date",
        "date_signed",
        "event_date",
        "license_first_date",
        "closed_date",
        "snapshot_date",
    }
)
NUMBER_FIELDS = frozenset(
    {
        "capacity",
        "days_received_to_first_activity",
        "days_received_to_visit",
        "days_received_to_report",
        "days_report_to_signed",
        "allegation_count",
    }
)
BOOLEAN_FIELDS = frozenset(
    {
        "missing_first_activity_date",
        "report_date_used_as_proxy",
        "review_delay_over_30_days",
        "review_delay_over_60_days",
        "review_delay_over_90_days",
        "review_delay_over_120_days",
    }
)

REVIEWER_FIELDS_BY_ENTITY: Mapping[str, tuple[str, ...]] = {
    "facility": (
        "facility_name",
        "external_facility_number",
        "facility_number",
        "facility_type",
        "county",
        "regional_office",
        "capacity",
        "status",
        "license_first_date",
        "closed_date",
        "client_served",
    ),
    "complaint": (
        "complaint_control_number",
        "complaint_received_date",
        "first_investigation_activity_date",
        "visit_date",
        "report_date",
        "date_signed",
        "finding",
        "days_received_to_first_activity",
        "days_received_to_visit",
        "days_received_to_report",
        "days_report_to_signed",
    ),
    "event": ("event_date",),
}

_MISSING = object()
_UNAVAILABLE_LITERALS = frozenset(
    {"unavailable", "not available", "coverage unavailable", "source unavailable"}
)
_NOT_APPLICABLE_LITERALS = frozenset({"not applicable", "n/a"})
_UNDATED_LITERALS = frozenset({"date unavailable", "undated"})
_UNKNOWN_LITERALS = frozenset({"unknown"})


@dataclass(frozen=True)
class PresentationValue:
    raw_value: object
    stored: bool
    state: PresentationValueState
    display_text: str
    export_text: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "stored_value": self.raw_value if self.stored else None,
            "stored": self.stored,
            "state": self.state,
            "display": self.display_text,
            "export": self.export_text,
            "explanation": self.explanation,
        }


def presentation_value(
    value: object = _MISSING,
    *,
    kind: PresentationValueKind = "text",
    source_available: bool = True,
    applicable: bool = True,
    supported: bool = True,
) -> PresentationValue:
    """Keep the stored scalar separate from its governed reviewer presentation."""

    stored = value is not _MISSING
    raw_value = value if stored else None
    if not supported:
        return _state_value(
            raw_value,
            stored,
            "unsupported",
            NOT_COLLECTED,
            "This field is not collected for this record type.",
        )
    if not applicable:
        return _state_value(
            raw_value,
            stored,
            "not_applicable",
            NOT_APPLICABLE,
            "This field does not apply in this context.",
        )
    if not source_available:
        return _state_value(
            raw_value,
            stored,
            "source_unavailable",
            SOURCE_UNAVAILABLE,
            "The governed source needed for this value is unavailable.",
        )
    if not stored:
        label = DATE_NOT_PROVIDED if kind == "date" else NOT_COLLECTED
        return _state_value(
            raw_value,
            False,
            "absent",
            label,
            "No stored value is available for this field.",
        )
    if value is None:
        label = DATE_NOT_PROVIDED if kind == "date" else NOT_PROVIDED
        return _state_value(
            None,
            True,
            "null",
            label,
            "No source value is stored; no value is presented or inferred.",
        )
    if isinstance(value, str):
        stripped = value.strip()
        normalized = " ".join(stripped.casefold().split())
        if not stripped:
            label = DATE_NOT_PROVIDED if kind == "date" else NOT_PROVIDED
            return _state_value(
                value,
                True,
                "present_blank",
                label,
                "The source field is present but blank.",
            )
        if normalized in _UNAVAILABLE_LITERALS:
            return _state_value(
                value,
                True,
                "source_unavailable",
                SOURCE_UNAVAILABLE,
                "The source explicitly marks this value as unavailable.",
            )
        if normalized in _NOT_APPLICABLE_LITERALS:
            return _state_value(
                value,
                True,
                "not_applicable",
                NOT_APPLICABLE,
                "The source explicitly marks this field as not applicable.",
            )
        if kind == "date" and normalized in _UNDATED_LITERALS:
            return _state_value(
                value,
                True,
                "undated",
                DATE_NOT_AVAILABLE,
                "The source explicitly indicates that this record is undated.",
            )
        if normalized in _UNKNOWN_LITERALS:
            label = DATE_NOT_PROVIDED if kind == "date" else NOT_PROVIDED
            return _state_value(
                value,
                True,
                "explicit_unknown",
                label,
                "The source explicitly identifies this value as unknown.",
            )
        if kind == "date":
            return _date_presentation(value, stripped)
        if kind == "number":
            return _number_presentation(value, stripped)
        if kind == "boolean":
            return _boolean_presentation(value, stripped)
        return _state_value(
            value,
            True,
            "present",
            stripped,
            "A source value is present.",
            export_text=stripped,
        )
    if kind == "date":
        if isinstance(value, date):
            iso_value = value.isoformat()
            return _state_value(
                value,
                True,
                "present",
                f"{value:%m/%d/%Y}",
                "A valid source date is present.",
                export_text=iso_value,
            )
        return _invalid(value)
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, int | float):
            return _invalid(value)
        state: PresentationValueState = "verified_zero" if value == 0 else "present"
        explanation = (
            "The source contains a verified numeric zero."
            if state == "verified_zero"
            else "A valid numeric source value is present."
        )
        text = str(value)
        return _state_value(value, True, state, text, explanation, export_text=text)
    if kind == "boolean":
        if isinstance(value, int) and value in {0, 1}:
            value = bool(value)
        if not isinstance(value, bool):
            return _invalid(value)
        return _state_value(
            value,
            True,
            "present",
            "Yes" if value else "No",
            "An explicit source boolean is present.",
            export_text="true" if value else "false",
        )
    if isinstance(value, bool):
        return _state_value(
            value,
            True,
            "present",
            "Yes" if value else "No",
            "An explicit source boolean is present.",
            export_text="true" if value else "false",
        )
    text = str(value)
    return _state_value(
        value,
        True,
        "present",
        text,
        "A source value is present.",
        export_text=text,
    )


def presentation_value_for_field(
    values: Mapping[str, Any],
    field_name: str,
    *,
    kind: PresentationValueKind | None = None,
    source_available: bool = True,
    applicable: bool = True,
    supported: bool = True,
) -> PresentationValue:
    value = values[field_name] if field_name in values else _MISSING
    return presentation_value(
        value,
        kind=kind or presentation_kind_for_field(field_name),
        source_available=source_available,
        applicable=applicable,
        supported=supported,
    )


def presentation_values_for_mapping(
    values: Mapping[str, Any],
    *,
    include_fields: Iterable[str] = (),
) -> dict[str, PresentationValue]:
    field_names = dict.fromkeys((*include_fields, *values.keys()))
    return {
        field_name: presentation_value_for_field(values, field_name)
        for field_name in field_names
    }


def presentation_values_for_record(
    entity_type: str,
    values: Mapping[str, Any],
) -> dict[str, PresentationValue]:
    return presentation_values_for_mapping(
        values,
        include_fields=REVIEWER_FIELDS_BY_ENTITY.get(entity_type, ()),
    )


def presentation_kind_for_field(field_name: str) -> PresentationValueKind:
    if field_name in DATE_FIELDS or field_name.endswith("_date"):
        return "date"
    if field_name in NUMBER_FIELDS or field_name.endswith("_count"):
        return "number"
    if field_name in BOOLEAN_FIELDS:
        return "boolean"
    return "text"


def _date_presentation(raw_value: str, stripped: str) -> PresentationValue:
    try:
        parsed = date.fromisoformat(stripped)
    except ValueError:
        return _invalid(raw_value)
    return _state_value(
        raw_value,
        True,
        "present",
        f"{parsed:%m/%d/%Y}",
        "A valid source date is present.",
        export_text=parsed.isoformat(),
    )


def _number_presentation(raw_value: str, stripped: str) -> PresentationValue:
    normalized = stripped.replace(",", "")
    try:
        parsed = float(normalized) if "." in normalized else int(normalized)
    except ValueError:
        return _invalid(raw_value)
    state: PresentationValueState = "verified_zero" if parsed == 0 else "present"
    explanation = (
        "The source contains a verified numeric zero."
        if state == "verified_zero"
        else "A valid numeric source value is present."
    )
    return _state_value(
        raw_value,
        True,
        state,
        stripped,
        explanation,
        export_text=stripped,
    )


def _boolean_presentation(raw_value: str, stripped: str) -> PresentationValue:
    normalized = stripped.casefold()
    if normalized in {"true", "yes"}:
        return _state_value(
            raw_value,
            True,
            "present",
            "Yes",
            "An explicit source boolean is present.",
            export_text="true",
        )
    if normalized in {"false", "no"}:
        return _state_value(
            raw_value,
            True,
            "present",
            "No",
            "An explicit source boolean is present.",
            export_text="false",
        )
    return _invalid(raw_value)


def _invalid(raw_value: object) -> PresentationValue:
    return _state_value(
        raw_value,
        True,
        "invalid",
        INVALID_SOURCE_VALUE,
        "The stored source value is not valid for this field and is not interpreted.",
    )


def _state_value(
    raw_value: object,
    stored: bool,
    state: PresentationValueState,
    display_text: str,
    explanation: str,
    *,
    export_text: str | None = None,
) -> PresentationValue:
    return PresentationValue(
        raw_value=raw_value,
        stored=stored,
        state=state,
        display_text=display_text,
        export_text=display_text if export_text is None else export_text,
        explanation=explanation,
    )
