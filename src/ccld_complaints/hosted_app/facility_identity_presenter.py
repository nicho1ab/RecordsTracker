from __future__ import annotations

from dataclasses import dataclass

from ccld_complaints.hosted_app.facility_identity_projection import (
    FacilityFieldResult,
    FacilityIdentityProjection,
    FacilityProjectionField,
    FacilityValueContext,
    FacilityValueState,
)


@dataclass(frozen=True)
class FacilityFieldPresentation:
    text: str
    state: FacilityValueState
    conflict: bool
    context: FacilityValueContext | None
    conflict_note: str | None = None


_STATE_TEXT = {
    FacilityValueState.BLANK: "Blank in source",
    FacilityValueState.ABSENT: "Not found in source",
    FacilityValueState.UNAVAILABLE: "Source unavailable",
    FacilityValueState.CONFLICTING: "Conflicting source values",
    FacilityValueState.INTERNAL_ONLY: "Internal only",
    FacilityValueState.INVALID: "Invalid source value",
}

_CONTEXT_TEXT = {
    FacilityValueContext.CURRENT_REFERENCE: "Current facility reference",
    FacilityValueContext.HISTORICAL_COMPLAINT: "Complaint-time record",
    FacilityValueContext.INTERNAL: "Internal only",
}


def present_facility_field(result: FacilityFieldResult) -> FacilityFieldPresentation:
    value = result.display_value
    if result.state is FacilityValueState.UNRESOLVED_RAW_CODE and value is not None:
        text = f"Source code {value} — label not verified"
    elif value is not None:
        text = str(value)
    else:
        text = _STATE_TEXT[result.state]

    conflict_note = None
    if result.conflict:
        conflict_note = (
            "Current facility reference and complaint-time records differ."
            if value is not None
            else "Eligible source records disagree; no value was selected."
        )
    return FacilityFieldPresentation(
        text=text,
        state=result.state,
        conflict=result.conflict,
        context=result.context,
        conflict_note=conflict_note,
    )


def projected_display_text(
    projection: FacilityIdentityProjection,
    field: FacilityProjectionField,
) -> str:
    return present_facility_field(projection.field(field)).text


def projected_selected_text(
    projection: FacilityIdentityProjection,
    field: FacilityProjectionField,
) -> str:
    value = projection.field(field).display_value
    return "" if value is None else str(value)


def projected_context_text(
    projection: FacilityIdentityProjection,
    field: FacilityProjectionField,
) -> str:
    context = projection.field(field).context
    return (
        _CONTEXT_TEXT[context]
        if context is not None
        else "No selected source context"
    )


def projected_conflict_text(
    projection: FacilityIdentityProjection,
    fields: tuple[FacilityProjectionField, ...],
) -> str:
    notes = tuple(
        dict.fromkeys(
            presentation.conflict_note
            for field in fields
            if (presentation := present_facility_field(projection.field(field))).conflict_note
        )
    )
    return "; ".join(notes) if notes else "No conflicting source values"
