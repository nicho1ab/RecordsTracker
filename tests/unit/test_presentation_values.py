from __future__ import annotations

from types import MappingProxyType

import pytest

from ccld_complaints.presentation_values import (
    presentation_value,
    presentation_value_for_field,
    presentation_values_for_mapping,
    presentation_values_for_repeated_field,
)


@pytest.mark.parametrize(
    ("value", "kind", "state", "display"),
    [
        (0, "number", "verified_zero", "0"),
        (12, "number", "present", "12"),
        (None, "number", "null", "No value recorded"),
        ("", "number", "present_blank", "Blank in source"),
        ("not-a-number", "number", "invalid", "Invalid source value"),
        ("unavailable", "number", "source_artifact_unavailable", "Source unavailable"),
        ("N/A", "number", "not_applicable", "Not applicable"),
        ("2026-07-13", "date", "present", "07/13/2026"),
        ("undated", "date", "undated", "Date not listed"),
        ("not-a-date", "date", "invalid", "Invalid source value"),
    ],
)
def test_presentation_value_keeps_governed_states_distinct(
    value: object,
    kind: str,
    state: str,
    display: str,
) -> None:
    presented = presentation_value(value, kind=kind)  # type: ignore[arg-type]

    assert presented.raw_value == value
    assert presented.stored is True
    assert presented.state == state
    assert presented.display_text == display


def test_absent_unsupported_and_governed_not_applicable_are_not_inferred_as_zero() -> None:
    absent = presentation_value_for_field({}, "capacity")
    unsupported = presentation_value(0, kind="number", supported=False)
    governed_not_applicable = presentation_value(None, applicable=False)

    assert absent.state == "source_label_absent"
    assert absent.display_text == "Not listed in source"
    assert absent.raw_value is None
    assert absent.stored is False
    assert unsupported.state == "unsupported_layout"
    assert unsupported.display_text == "Source format not supported"
    assert governed_not_applicable.state == "not_applicable"
    assert governed_not_applicable.display_text == "Not applicable"
    assert presentation_value(None).state == "null"


def test_valid_export_values_preserve_iso_dates_and_numeric_zero() -> None:
    values = {
        "complaint_received_date": "2026-07-13",
        "days_received_to_first_activity": 0,
    }
    presented = presentation_values_for_mapping(values)

    assert presented["complaint_received_date"].display_text == "07/13/2026"
    assert presented["complaint_received_date"].export_text == "2026-07-13"
    assert presented["days_received_to_first_activity"].export_text == "0"


def test_sqlite_and_postgresql_style_mappings_preserve_the_same_states() -> None:
    sqlite_values = {
        "capacity": 0,
        "county": None,
        "regional_office": "",
        "closed_date": "not-a-date",
        "license_first_date": "undated",
        "client_served": "unavailable",
        "days_received_to_first_activity": 7,
        "days_received_to_visit": 0,
        "days_received_to_report": None,
        "days_report_to_signed": "unavailable",
    }
    postgresql_style_values = MappingProxyType(dict(sqlite_values))

    sqlite_states = {
        key: value.state
        for key, value in presentation_values_for_mapping(sqlite_values).items()
    }
    postgresql_states = {
        key: value.state
        for key, value in presentation_values_for_mapping(
            postgresql_style_values
        ).items()
    }

    assert sqlite_states == postgresql_states == {
        "capacity": "verified_zero",
        "county": "null",
        "regional_office": "present_blank",
        "closed_date": "invalid",
        "license_first_date": "undated",
        "client_served": "source_artifact_unavailable",
        "days_received_to_first_activity": "present",
        "days_received_to_visit": "verified_zero",
        "days_received_to_report": "null",
        "days_report_to_signed": "source_artifact_unavailable",
    }


def test_presentation_state_hints_distinguish_pipeline_and_source_conditions() -> None:
    pipeline = presentation_value(state_hint="stored_but_not_read")
    conflict = presentation_value("ignored", state_hint="conflicting_sources")
    internal = presentation_value("private", state_hint="intentionally_internal")

    assert pipeline.state == "stored_but_not_read"
    assert pipeline.display_text == "Data processing incomplete"
    assert "may contain" in pipeline.explanation
    assert conflict.display_text == "Sources differ"
    assert internal.hidden is True
    assert internal.display_text == ""


def test_repeated_presentations_preserve_order_and_blank_state() -> None:
    populated = presentation_values_for_repeated_field(
        {"deficiency_texts": ["First", "Second"]}, "deficiency_texts"
    )
    blank = presentation_values_for_repeated_field(
        {"deficiency_texts": []}, "deficiency_texts"
    )

    assert [value.display_text for value in populated] == ["First", "Second"]
    assert [value.display_text for value in blank] == ["Blank in source"]
