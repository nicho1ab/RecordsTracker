from __future__ import annotations

from types import MappingProxyType

import pytest

from ccld_complaints.presentation_values import (
    presentation_value,
    presentation_value_for_field,
    presentation_values_for_mapping,
)


@pytest.mark.parametrize(
    ("value", "kind", "state", "display"),
    [
        (0, "number", "verified_zero", "0"),
        (12, "number", "present", "12"),
        (None, "number", "null", "Not provided"),
        ("", "number", "present_blank", "Not provided"),
        ("not-a-number", "number", "invalid", "Invalid source value"),
        ("unavailable", "number", "source_unavailable", "Not available from source"),
        ("N/A", "number", "not_applicable", "Not applicable"),
        ("2026-07-13", "date", "present", "07/13/2026"),
        ("undated", "date", "undated", "Date not available"),
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

    assert absent.state == "absent"
    assert absent.display_text == "Not collected"
    assert absent.raw_value is None
    assert absent.stored is False
    assert unsupported.state == "unsupported"
    assert unsupported.display_text == "Not collected"
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
        "client_served": "source_unavailable",
    }
