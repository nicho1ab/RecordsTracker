from __future__ import annotations

import pytest

from ccld_complaints.hosted_app import reviewer_ui
from ccld_complaints.hosted_app.reviewer_semantics import (
    is_complaint_status_value,
    reviewer_semantic_presentation,
)


@pytest.mark.parametrize(
    ("value", "label", "component_class"),
    (
        (
            "Substantiated",
            "Substantiated",
            "finding-badge finding-badge--substantiated finding-badge--status",
        ),
        (
            "Unsubstantiated",
            "Unsubstantiated",
            "finding-badge finding-badge--unsubstantiated finding-badge--status",
        ),
        (
            "Inconclusive",
            "Inconclusive",
            "finding-badge finding-badge--inconclusive finding-badge--status",
        ),
    ),
)
def test_canonical_findings_have_governed_presentations(
    value: str,
    label: str,
    component_class: str,
) -> None:
    presentation = reviewer_semantic_presentation("finding", value)

    assert presentation.label == label
    assert presentation.component_class == component_class
    assert presentation.is_canonical is True


@pytest.mark.parametrize(
    "value",
    ("Founded", "Sustained", "Deficiency cited", "No deficiency cited"),
)
def test_noncanonical_findings_remain_labeled_source_facts(value: str) -> None:
    presentation = reviewer_semantic_presentation("finding", value)

    assert presentation.domain == "labeled_source_fact"
    assert presentation.label == f"Source finding: {value}"
    assert presentation.is_canonical is False


@pytest.mark.parametrize(
    "value",
    ("active", "pending", "uninvestigated", "not determined", "not yet determined"),
)
def test_complaint_status_like_values_are_not_findings(value: str) -> None:
    assert is_complaint_status_value(value) is True
    assert reviewer_semantic_presentation("complaint_status", value).label == value


def test_status_like_value_bypasses_the_missing_finding_fallback() -> None:
    markup = reviewer_ui._facility_intelligence_finding_markup("pending")

    assert "Finding not provided" not in markup
    assert "finding-badge" not in markup
    assert ">pending<" in markup
    assert reviewer_ui._finding_field_label("pending") == "Complaint status"


@pytest.mark.parametrize(
    ("value", "label"),
    (
        ("Mistreatment-topic", "Mistreatment"),
        ("Care-omission topic", "Care omission"),
        ("Supervision topic", "Supervision"),
        ("Medication/medical-care topic", "Medication or medical care"),
        ("Runaway/AWOL topic", "Runaway or AWOL"),
        ("Staff-conduct topic", "Staff misconduct"),
    ),
)
def test_review_topics_have_approved_display_labels(value: str, label: str) -> None:
    presentation = reviewer_semantic_presentation("review_topic", value)

    assert presentation.label == label
    assert presentation.is_canonical is True


def test_keyword_cue_remains_distinct_from_a_normalized_topic() -> None:
    presentation = reviewer_semantic_presentation("review_topic", "Possible keyword cue")

    assert presentation.label == "Possible keyword cue"
    assert presentation.is_canonical is False


def test_serious_topic_row_uses_the_same_normalized_topic_label() -> None:
    row = reviewer_ui._render_serious_topic_row(
        {
            "facility_display": "Example facility",
            "facility_identity_context": "Facility identity available",
            "facility_identity_conflicts": "No conflicts",
            "facility_number": "123",
            "complaint_date_display": "01/01/2026",
            "finding_value": "Inconclusive",
            "category_labels": "Staff-conduct topic; Supervision topic",
            "match_bases": "Source category",
            "matched_fields": "source-derived allegation_category",
            "matched_terms": "Staff conduct; Inadequate supervision",
            "source_categories": "Staff conduct; Inadequate supervision",
            "facility_type": "Example type",
            "geography": "Example county",
            "source_url_href": "",
            "detail_href": "/reviewer/records/detail?source_record_key=example",
        }
    )

    assert "Staff misconduct; Supervision" in row
    assert "Staff-conduct topic" not in row
    assert "finding-badge--inconclusive" in row


@pytest.mark.parametrize(
    ("value", "label"),
    (
        ("CCLD source available", "Source available"),
        ("Source available", "Source available"),
        ("Source unavailable", "Source unavailable"),
    ),
)
def test_source_availability_is_separate_from_typed_reason(value: str, label: str) -> None:
    assert reviewer_semantic_presentation("source_availability", value).label == label


@pytest.mark.parametrize(
    ("state", "label"),
    (
        ("source_label_absent", "Not listed in source"),
        ("explicit_unknown", "Unknown"),
        ("source_artifact_unavailable", "Source unavailable"),
        ("conflicting_sources", "Sources differ"),
        ("extraction_failed", "Data processing incomplete"),
        ("source_pending", "Source pending"),
        (("unresolved_raw_code", "42"), "Source code 42 — label not verified"),
        ("unsupported_layout", "Source format not supported"),
        ("invalid", "Invalid source value"),
    ),
)
def test_typed_source_and_data_states_do_not_collapse(state: object, label: str) -> None:
    assert reviewer_semantic_presentation("source_data_state", state).label == label


@pytest.mark.parametrize(
    ("value", "label"),
    (
        ("not_started", "Not started"),
        ("in_review", "In review"),
        ("needs_follow_up", "Needs follow-up"),
        ("reviewed", "Reviewed"),
        ("blocked", "Blocked"),
    ),
)
def test_reviewer_workflow_states_stay_in_their_own_domain(value: str, label: str) -> None:
    presentation = reviewer_semantic_presentation("reviewer_workflow_state", value)

    assert presentation.label == label
    assert presentation.domain == "reviewer_workflow_state"


@pytest.mark.parametrize("value", ("30+ day gap", "60+ day gap", "90+ day gap"))
def test_timing_cues_are_named_as_analytical_screening(value: str) -> None:
    presentation = reviewer_semantic_presentation("timing_screening_cue", value)

    assert presentation.accessible_label == f"{value} — analytical timing screening cue"


def test_120_day_cue_is_not_an_available_ui_timing_cue() -> None:
    with pytest.raises(ValueError, match="Unsupported timing screening cue"):
        reviewer_semantic_presentation("timing_screening_cue", "120+ day gap")


def test_120_day_flag_remains_available_to_non_ui_code_but_not_ui_labels() -> None:
    assert "review_delay_over_120_days" in reviewer_ui._SAFE_CONTEXT_FIELDS_BY_ENTITY[
        "complaint"
    ]
    assert reviewer_ui._review_flag_labels({"review_delay_over_120_days": True}) == ()


def test_reviewer_ui_uses_the_shared_domain_aware_contract_for_chips() -> None:
    assert not hasattr(reviewer_ui, "_review_flag_chip_class")
    assert 'aria-label="30+ day gap — analytical timing screening cue"' in (
        reviewer_ui._semantic_chip_markup("timing_screening_cue", "30+ day gap")
    )
