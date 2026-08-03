"""Governed reviewer-facing semantic labels and component treatments.

This module keeps a displayed string from determining its own meaning.  Source
values remain raw unless an Issue #656-approved domain mapping explicitly
supplies a reviewer label.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReviewerSemanticDomain = Literal[
    "complaint_status",
    "finding",
    "review_topic",
    "source_availability",
    "source_data_state",
    "reviewer_workflow_state",
    "timing_screening_cue",
    "labeled_source_fact",
]


@dataclass(frozen=True)
class ReviewerSemanticPresentation:
    """A domain-aware reviewer label and its existing component treatment."""

    domain: ReviewerSemanticDomain
    label: str
    component_class: str
    marker: str | None = None
    accessible_label: str | None = None
    is_canonical: bool = False


_CANONICAL_FINDINGS = {
    "substantiated": "Substantiated",
    "unsubstantiated": "Unsubstantiated",
    "inconclusive": "Inconclusive",
}
_COMPLAINT_STATUS_VALUES = frozenset(
    {"active", "pending", "uninvestigated", "not determined", "not yet determined"}
)
_REVIEW_TOPIC_LABELS = {
    "abuse or mistreatment": "Mistreatment",
    "mistreatment-topic": "Mistreatment",
    "neglect": "Care omission",
    "care-omission topic": "Care omission",
    "inadequate supervision": "Supervision",
    "supervision topic": "Supervision",
    "medication or medical care": "Medication or medical care",
    "medication/medical-care topic": "Medication or medical care",
    "runaway or awol": "Runaway or AWOL",
    "runaway/awol topic": "Runaway or AWOL",
    "staff conduct": "Staff misconduct",
    "staff-conduct topic": "Staff misconduct",
}
_SOURCE_DATA_STATE_LABELS = {
    "null": "Not listed in source",
    "source_label_absent": "Not listed in source",
    "source_artifact_unavailable": "Source unavailable",
    "explicit_unknown": "Unknown",
    "source_pending": "Source pending",
    "conflicting_sources": "Sources differ",
    "unsupported_layout": "Source format not supported",
    "present_but_not_extracted": "Data processing incomplete",
    "extracted_but_not_allocated": "Data processing incomplete",
    "allocated_but_not_imported": "Data processing incomplete",
    "stored_but_not_read": "Data processing incomplete",
    "read_but_not_rendered": "Data processing incomplete",
    "rendered_incorrectly": "Data processing incomplete",
    "invalid": "Invalid source value",
    "extraction_failed": "Data processing incomplete",
    "unresolved_raw_code": "Source code {value} — label not verified",
}
_WORKFLOW_LABELS = {
    "not_started": "Not started",
    "in_review": "In review",
    "needs_follow_up": "Needs follow-up",
    "reviewed": "Reviewed",
    "blocked": "Blocked",
}
_TIMING_CUE_LABELS = frozenset({"30+ day gap", "60+ day gap", "90+ day gap"})


def reviewer_semantic_presentation(
    domain: ReviewerSemanticDomain,
    value: object,
) -> ReviewerSemanticPresentation:
    """Return the approved presentation for a semantic domain/value pair."""

    text = _text(value)
    normalized = text.casefold()

    if domain == "finding":
        label = _CANONICAL_FINDINGS.get(normalized)
        if label is not None:
            return ReviewerSemanticPresentation(
                domain=domain,
                label=label,
                component_class=f"finding-badge finding-badge--{normalized} finding-badge--status",
                marker=normalized,
                is_canonical=True,
            )
        return reviewer_semantic_presentation("labeled_source_fact", f"Source finding: {text}")

    if domain == "complaint_status":
        return ReviewerSemanticPresentation(
            domain=domain,
            label=text,
            component_class="review-chip",
        )

    if domain == "review_topic":
        label = _REVIEW_TOPIC_LABELS.get(normalized)
        if label is not None:
            return ReviewerSemanticPresentation(
                domain=domain,
                label=label,
                component_class="review-chip",
                is_canonical=True,
            )
        if normalized == "possible keyword cue":
            return ReviewerSemanticPresentation(
                domain=domain,
                label="Possible keyword cue",
                component_class="review-chip",
            )
        return reviewer_semantic_presentation("labeled_source_fact", f"Source category: {text}")

    if domain == "source_availability":
        available = normalized in {"available", "source available", "ccld source available"}
        if available:
            return ReviewerSemanticPresentation(
                domain=domain,
                label="Source available",
                component_class="review-chip source-chip",
            )
        return ReviewerSemanticPresentation(
            domain=domain,
            label="Source unavailable",
            component_class="review-chip badge-danger",
        )

    if domain == "source_data_state":
        state, raw_value = _state_and_value(value)
        label = _SOURCE_DATA_STATE_LABELS.get(state, text)
        if state == "unresolved_raw_code":
            label = label.format(value=raw_value)
        return ReviewerSemanticPresentation(
            domain=domain,
            label=label,
            component_class="review-chip",
        )

    if domain == "reviewer_workflow_state":
        workflow_key = normalized.replace("-", "_").replace(" ", "_")
        label = _WORKFLOW_LABELS.get(workflow_key, text)
        return ReviewerSemanticPresentation(
            domain=domain,
            label=label,
            component_class="review-chip badge-info badge-info--status",
            marker="status",
            is_canonical=workflow_key in _WORKFLOW_LABELS,
        )

    if domain == "timing_screening_cue":
        if text not in _TIMING_CUE_LABELS:
            raise ValueError(f"Unsupported timing screening cue: {text!r}")
        return ReviewerSemanticPresentation(
            domain=domain,
            label=text,
            component_class="review-chip badge-attention badge-attention--warning",
            marker="warning",
            accessible_label=f"{text} — analytical timing screening cue",
            is_canonical=True,
        )

    return ReviewerSemanticPresentation(
        domain="labeled_source_fact",
        label=text,
        component_class="review-chip",
    )


def is_complaint_status_value(value: object) -> bool:
    """Whether a legacy finding slot contains an approved status-like value."""

    return _text(value).casefold() in _COMPLAINT_STATUS_VALUES


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _state_and_value(value: object) -> tuple[str, str]:
    if isinstance(value, tuple) and len(value) == 2:
        return _text(value[0]).casefold(), _text(value[1])
    text = _text(value)
    return text.casefold(), text
