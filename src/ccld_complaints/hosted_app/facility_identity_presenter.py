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


@dataclass(frozen=True)
class FacilityLocationPresentation:
    """A single readable location with its governing source state."""

    text: str
    state: FacilityValueState
    conflict: bool


_STATE_TEXT = {
    FacilityValueState.BLANK: "Blank in source",
    FacilityValueState.ABSENT: "Not found in source",
    FacilityValueState.UNAVAILABLE: "Source unavailable",
    FacilityValueState.CONFLICTING: "Conflicting source values",
    FacilityValueState.INTERNAL_ONLY: "Internal only",
    FacilityValueState.INVALID: "Invalid source value",
    FacilityValueState.EXTRACTION_FAILED: "Source extraction failed",
}

_CONTEXT_TEXT = {
    FacilityValueContext.CURRENT_REFERENCE: "Current facility reference",
    FacilityValueContext.SUPPLEMENTARY_REFERENCE: "Supplementary facility reference",
    FacilityValueContext.HISTORICAL_REFERENCE: "Historical facility reference",
    FacilityValueContext.HISTORICAL_COMPLAINT: "Complaint-time record",
    FacilityValueContext.INTERNAL: "Internal only",
}


def present_facility_field(result: FacilityFieldResult) -> FacilityFieldPresentation:
    value = result.display_value
    if result.state is FacilityValueState.UNRESOLVED_RAW_CODE and value is not None:
        text = unresolved_raw_code_text(value)
    elif value is not None:
        text = str(value)
    else:
        text = _STATE_TEXT[result.state]

    conflict_note = None
    if result.conflict:
        contexts = {alternative.context for alternative in result.alternatives}
        if value is None:
            conflict_note = "Eligible source records disagree; no value was selected."
        elif {
            FacilityValueContext.CURRENT_REFERENCE,
            FacilityValueContext.HISTORICAL_COMPLAINT,
        }.issubset(contexts):
            conflict_note = "Current facility reference and complaint-time records differ."
        else:
            conflict_note = "Governed facility source observations differ."
    return FacilityFieldPresentation(
        text=text,
        state=result.state,
        conflict=result.conflict,
        context=result.context,
        conflict_note=conflict_note,
    )


def unresolved_raw_code_text(value: object) -> str:
    """Present a source code without claiming an unverified descriptive label."""
    return f"Source code {value} — label not verified"


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


def present_facility_location(
    projection: FacilityIdentityProjection,
    *,
    include_street: bool,
) -> FacilityLocationPresentation:
    """Compose location fields without repeating missing-data labels.

    Compact contexts use city/state/ZIP, while Facility Overview includes the
    street field. A location with no selected values reports its strongest
    governing state once rather than assembling field-level placeholders.
    """

    fields = (
        (FacilityProjectionField.FULL_ADDRESS,)
        if include_street
        else ()
    ) + (
        FacilityProjectionField.CITY,
        FacilityProjectionField.STATE,
        FacilityProjectionField.ZIP,
    )
    results = tuple(projection.field(field) for field in fields)
    values = {
        field: projected_selected_text(projection, field)
        for field in fields
    }
    street = values.get(FacilityProjectionField.FULL_ADDRESS, "")
    city = values[FacilityProjectionField.CITY]
    state = values[FacilityProjectionField.STATE]
    zip_code = values[FacilityProjectionField.ZIP]
    state_zip = " ".join(part for part in (state, zip_code) if part)
    locality = ", ".join(part for part in (city, state_zip) if part)
    text = ", ".join(part for part in (street, locality) if part)
    conflict = any(result.conflict for result in results)
    if text:
        return FacilityLocationPresentation(
            text=(f"{text} (Conflicting source values)" if conflict else text),
            state=(FacilityValueState.CONFLICTING if conflict else FacilityValueState.POPULATED),
            conflict=conflict,
        )

    state_priority = (
        FacilityValueState.EXTRACTION_FAILED,
        FacilityValueState.INVALID,
        FacilityValueState.CONFLICTING,
        FacilityValueState.UNAVAILABLE,
        FacilityValueState.BLANK,
        FacilityValueState.ABSENT,
    )
    for state in state_priority:
        for result in results:
            if result.state is state:
                return FacilityLocationPresentation(
                    text=present_facility_field(result).text,
                    state=state,
                    conflict=conflict,
                )
    raise AssertionError("facility location fields must have a supported state")


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
