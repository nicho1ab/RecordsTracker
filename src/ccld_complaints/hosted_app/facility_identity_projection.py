from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, TypeAlias

from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.auth import (
    SOURCE_DERIVED_READ_PERMISSION,
    AuthenticatedActor,
    AuthorizationTarget,
    HostedAccessScope,
    list_authorized_source_derived_records,
    require_permission,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_source_derived_records,
)
from ccld_complaints.hosted_app.source_derived_reads import SourceDerivedRecordRead
from ccld_complaints.source_profiling import FACILITY_SOURCE_REGISTRY

FacilityValue: TypeAlias = str | int


class FacilityProjectionField(StrEnum):
    FACILITY_NAME = "facility_name"
    PUBLIC_FACILITY_ID = "public_facility_id"
    FACILITY_TYPE = "facility_type"
    STATUS = "status"
    FULL_ADDRESS = "full_address"
    CITY = "city"
    STATE = "state"
    ZIP = "zip"
    COUNTY = "county"
    CAPACITY = "capacity"
    ADMINISTRATOR = "administrator"
    LICENSEE = "licensee"
    TELEPHONE = "telephone"
    REGIONAL_OFFICE = "regional_office"
    CANONICAL_INTERNAL_IDENTITY = "canonical_internal_identity"


PUBLIC_FACILITY_FIELDS = tuple(
    field
    for field in FacilityProjectionField
    if field is not FacilityProjectionField.CANONICAL_INTERNAL_IDENTITY
)


class FacilityValueState(StrEnum):
    POPULATED = "populated"
    BLANK = "blank"
    ABSENT = "absent"
    UNAVAILABLE = "unavailable"
    UNRESOLVED_RAW_CODE = "unresolved_raw_code"
    CONFLICTING = "conflicting"
    INTERNAL_ONLY = "internal_only"
    INVALID = "invalid"


class FacilityValueContext(StrEnum):
    CURRENT_REFERENCE = "current_reference"
    HISTORICAL_COMPLAINT = "historical_complaint"
    INTERNAL = "internal"


class FacilitySourceKind(StrEnum):
    PROGRAM_REFERENCE = "program_reference"
    COMPLAINT_LINKED_FACILITY = "complaint_linked_facility"


@dataclass(frozen=True)
class FacilitySourceIdentity:
    source_kind: FacilitySourceKind
    source_row_identity: str
    snapshot_identity: str
    source_field: str


@dataclass(frozen=True)
class FacilityValueAlternative:
    raw_value: FacilityValue | None
    normalized_value: FacilityValue | None
    state: FacilityValueState
    source_identity: FacilitySourceIdentity
    observed_at: str | None
    context: FacilityValueContext


@dataclass(frozen=True)
class FacilityFieldResult:
    field: FacilityProjectionField
    display_value: FacilityValue | None
    normalized_value: FacilityValue | None
    state: FacilityValueState
    source_identity: FacilitySourceIdentity | None
    observed_at: str | None
    conflict: bool
    alternatives: tuple[FacilityValueAlternative, ...]
    context: FacilityValueContext | None
    unavailable_sources: tuple[FacilitySourceKind, ...] = ()


@dataclass(frozen=True)
class FacilityIdentityProjection:
    public_facility_id: str
    fields: Mapping[FacilityProjectionField, FacilityFieldResult]
    canonical_internal_identity: FacilityFieldResult
    ineligible_candidate_excluded: bool = False

    def field(self, field: FacilityProjectionField) -> FacilityFieldResult:
        if field is FacilityProjectionField.CANONICAL_INTERNAL_IDENTITY:
            return self.canonical_internal_identity
        return self.fields[field]


@dataclass(frozen=True)
class FacilityProjectionSourceAvailability:
    program_reference: bool = True
    complaint_linked_facility: bool = True


@dataclass(frozen=True)
class FacilityProjectionCandidate:
    source_kind: FacilitySourceKind
    source_row_identity: str
    snapshot_identity: str
    observed_at: str | None
    context: FacilityValueContext
    values: Mapping[FacilityProjectionField, Any]
    present_fields: frozenset[FacilityProjectionField]
    source_fields: Mapping[FacilityProjectionField, str]
    canonical_internal_identity: str | None = None


_FIELD_PRECEDENCE: Mapping[
    FacilityProjectionField, tuple[FacilitySourceKind, ...]
] = {
    FacilityProjectionField.FACILITY_NAME: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.PUBLIC_FACILITY_ID: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.FACILITY_TYPE: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.STATUS: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.FULL_ADDRESS: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.CITY: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.STATE: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.ZIP: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.COUNTY: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.CAPACITY: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.ADMINISTRATOR: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.LICENSEE: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.TELEPHONE: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
    FacilityProjectionField.REGIONAL_OFFICE: (
        FacilitySourceKind.PROGRAM_REFERENCE,
        FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
    ),
}

_REFERENCE_FIELD_ALIASES: Mapping[FacilityProjectionField, tuple[str, ...]] = {
    FacilityProjectionField.FACILITY_NAME: ("Facility Name", "NAME"),
    FacilityProjectionField.PUBLIC_FACILITY_ID: ("Facility Number", "FAC_NBR"),
    FacilityProjectionField.FACILITY_TYPE: ("Facility Type", "FAC_TYPE_DESC"),
    FacilityProjectionField.STATUS: ("Facility Status", "STATUS"),
    FacilityProjectionField.FULL_ADDRESS: (
        "Facility Address",
        "RES_STREET_ADDR",
        "ADDRESS",
    ),
    FacilityProjectionField.CITY: ("Facility City", "RES_CITY", "CITY"),
    FacilityProjectionField.STATE: ("Facility State", "RES_STATE", "STATE"),
    FacilityProjectionField.ZIP: ("Facility Zip", "RES_ZIP_CODE", "ZIP"),
    FacilityProjectionField.COUNTY: ("County Name", "COUNTY"),
    FacilityProjectionField.CAPACITY: ("Facility Capacity", "CAPACITY"),
    FacilityProjectionField.ADMINISTRATOR: (
        "Facility Administrator",
        "ADMINISTRATOR",
    ),
    FacilityProjectionField.LICENSEE: ("Licensee", "LICENSEE"),
    FacilityProjectionField.TELEPHONE: (
        "Facility Telephone Number",
        "FAC_PHONE_NBR",
        "PHONE",
    ),
    FacilityProjectionField.REGIONAL_OFFICE: (
        "Regional Office",
        "FAC_DO_DESC",
    ),
}

_REFERENCE_TYPED_COLUMNS: Mapping[FacilityProjectionField, str] = {
    FacilityProjectionField.FACILITY_NAME: "facility_name",
    FacilityProjectionField.PUBLIC_FACILITY_ID: "facility_number",
    FacilityProjectionField.FACILITY_TYPE: "facility_type",
    FacilityProjectionField.STATUS: "status",
    FacilityProjectionField.FULL_ADDRESS: "address",
    FacilityProjectionField.CITY: "city",
    FacilityProjectionField.STATE: "state",
    FacilityProjectionField.ZIP: "zip",
    FacilityProjectionField.COUNTY: "county",
    FacilityProjectionField.CAPACITY: "capacity",
    FacilityProjectionField.ADMINISTRATOR: "facility_administrator",
    FacilityProjectionField.LICENSEE: "licensee_name",
    FacilityProjectionField.TELEPHONE: "telephone",
    FacilityProjectionField.REGIONAL_OFFICE: "regional_office",
}

_CANONICAL_FIELD_ALIASES: Mapping[FacilityProjectionField, tuple[str, ...]] = {
    FacilityProjectionField.FACILITY_NAME: ("facility_name", "name"),
    FacilityProjectionField.PUBLIC_FACILITY_ID: (
        "external_facility_number",
        "facility_number",
        "license_number",
    ),
    FacilityProjectionField.FACILITY_TYPE: (
        "facility_type",
        "facility_type_description",
        "type",
    ),
    FacilityProjectionField.STATUS: ("status", "facility_status"),
    FacilityProjectionField.FULL_ADDRESS: (
        "full_address",
        "facility_address",
        "address",
        "res_street_addr",
    ),
    FacilityProjectionField.CITY: ("city", "facility_city"),
    FacilityProjectionField.STATE: ("state", "facility_state"),
    FacilityProjectionField.ZIP: ("zip", "zip_code", "facility_zip"),
    FacilityProjectionField.COUNTY: ("county", "county_name"),
    FacilityProjectionField.CAPACITY: ("capacity", "facility_capacity"),
    FacilityProjectionField.ADMINISTRATOR: (
        "facility_administrator",
        "administrator",
    ),
    FacilityProjectionField.LICENSEE: ("licensee_name", "licensee"),
    FacilityProjectionField.TELEPHONE: (
        "telephone",
        "facility_telephone_number",
        "phone",
    ),
    FacilityProjectionField.REGIONAL_OFFICE: (
        "regional_office",
        "fac_do_desc",
    ),
}

_APPROVED_REFERENCE_RESOURCE_IDS = frozenset(
    str(resource["resource_id"])
    for resource in FACILITY_SOURCE_REGISTRY["target_resources"]
    if resource.get("resource_id")
)
_UNSAFE_SOURCE_MARKERS = frozenset(
    {"fixture", "mock", "synthetic", "sample", "tiny", "test-only", "test_only"}
)
_SPACE_PATTERN = re.compile(r"\s+")


def project_facility_identity(
    public_facility_id: str,
    candidates: Sequence[FacilityProjectionCandidate],
    *,
    availability: FacilityProjectionSourceAvailability | None = None,
    ineligible_candidate_excluded: bool = False,
) -> FacilityIdentityProjection:
    facility_id = _validated_public_facility_id(public_facility_id)
    source_availability = availability or FacilityProjectionSourceAvailability()
    eligible = tuple(
        candidate
        for candidate in candidates
        if _candidate_matches_public_facility_id(candidate, facility_id)
    )
    fields: dict[FacilityProjectionField, FacilityFieldResult] = {
        field: _project_field(field, eligible, source_availability)
        for field in PUBLIC_FACILITY_FIELDS
    }
    return FacilityIdentityProjection(
        public_facility_id=facility_id,
        fields=MappingProxyType(fields),
        canonical_internal_identity=_project_internal_identity(eligible),
        ineligible_candidate_excluded=ineligible_candidate_excluded,
    )


def facility_projection_candidate_from_values(
    values: Mapping[str, Any],
    *,
    source_kind: FacilitySourceKind,
    source_row_identity: str,
    snapshot_identity: str,
    observed_at: str | None,
    canonical_internal_identity: str | None = None,
) -> FacilityProjectionCandidate:
    """Adapt an existing governed facility observation to the shared projector.

    Callers provide observation identity and provenance context, while this
    adapter owns the canonical/reference aliases and field-presence rules. It
    intentionally does not select a winner or translate presentation wording.
    """

    aliases: Mapping[FacilityProjectionField, tuple[str, ...]] = (
        {
            field: (_REFERENCE_TYPED_COLUMNS[field], *_REFERENCE_FIELD_ALIASES[field])
            for field in PUBLIC_FACILITY_FIELDS
        }
        if source_kind is FacilitySourceKind.PROGRAM_REFERENCE
        else _CANONICAL_FIELD_ALIASES
    )
    candidate_values: dict[FacilityProjectionField, Any] = {}
    present_fields: set[FacilityProjectionField] = set()
    source_fields: dict[FacilityProjectionField, str] = {}
    for field in PUBLIC_FACILITY_FIELDS:
        source_value = _present_alias_value(values, aliases[field])
        if source_value is None:
            continue
        source_field, value = source_value
        candidate_values[field] = value
        present_fields.add(field)
        source_fields[field] = source_field
    return FacilityProjectionCandidate(
        source_kind=source_kind,
        source_row_identity=_clean_text(source_row_identity),
        snapshot_identity=_clean_text(snapshot_identity),
        observed_at=_optional_text(observed_at),
        context=(
            FacilityValueContext.CURRENT_REFERENCE
            if source_kind is FacilitySourceKind.PROGRAM_REFERENCE
            else FacilityValueContext.HISTORICAL_COMPLAINT
        ),
        values=candidate_values,
        present_fields=frozenset(present_fields),
        source_fields=source_fields,
        canonical_internal_identity=canonical_internal_identity,
    )


def load_authorized_facility_identity_projection(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    public_facility_id: str,
    import_batch_id: str | None = None,
    allow_test_candidates: bool = False,
) -> FacilityIdentityProjection:
    facility_id = _validated_public_facility_id(public_facility_id)
    return load_authorized_facility_identity_projections(
        connection,
        actor,
        scope=scope,
        public_facility_ids=(facility_id,),
        import_batch_id=import_batch_id,
        allow_test_candidates=allow_test_candidates,
    )[facility_id]


def load_authorized_facility_identity_projections(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    public_facility_ids: Sequence[str],
    import_batch_id: str | None = None,
    allow_test_candidates: bool = False,
    authorized_source_records: Sequence[SourceDerivedRecordRead] | None = None,
) -> Mapping[str, FacilityIdentityProjection]:
    from ccld_complaints.hosted_app.facility_reference_preload import (
        FACILITY_REFERENCE_TABLE_NAME,
        hosted_facility_reference_records,
    )

    facility_ids = tuple(
        dict.fromkeys(_validated_public_facility_id(value) for value in public_facility_ids)
    )
    if not facility_ids:
        return MappingProxyType({})
    require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("source_derived_record_list", ",".join(facility_ids)),
    )
    inspector = inspect(connection)

    complaint_candidates: dict[str, list[FacilityProjectionCandidate]] = {
        facility_id: [] for facility_id in facility_ids
    }
    complaint_matching_counts = dict.fromkeys(facility_ids, 0)
    complaint_available = (
        True
        if authorized_source_records is not None
        else inspector.has_table(hosted_source_derived_records.name)
    )
    if complaint_available:
        source_records = (
            authorized_source_records
            if authorized_source_records is not None
            else list_authorized_source_derived_records(
                connection,
                actor,
                scope=scope,
                entity_type="facility",
                import_batch_id=import_batch_id,
            )
        )
        facility_id_set = set(facility_ids)
        for record in source_records:
            matching_id = _source_record_public_facility_id(record)
            if matching_id not in facility_id_set:
                continue
            complaint_matching_counts[matching_id] += 1
            if allow_test_candidates or not _unsafe_source_record(record):
                complaint_candidates[matching_id].append(
                    _candidate_from_source_record(record)
                )

    reference_candidates: dict[str, list[FacilityProjectionCandidate]] = {
        facility_id: [] for facility_id in facility_ids
    }
    reference_matching_counts = dict.fromkeys(facility_ids, 0)
    reference_available = inspector.has_table(FACILITY_REFERENCE_TABLE_NAME)
    if reference_available:
        reference_rows = tuple(
            dict(row)
            for row in connection.execute(
                select(hosted_facility_reference_records).where(
                    hosted_facility_reference_records.c.facility_number.in_(facility_ids)
                )
            ).mappings()
        )
        for row in reference_rows:
            matching_id = _clean_text(row.get("facility_number"))
            if matching_id not in reference_candidates:
                continue
            reference_matching_counts[matching_id] += 1
            if _eligible_reference_row(row) and (
                allow_test_candidates or not _unsafe_reference_row(row)
            ):
                reference_candidates[matching_id].append(
                    _candidate_from_reference_row(row)
                )

    return MappingProxyType(
        {
            facility_id: project_facility_identity(
                facility_id,
                (
                    *reference_candidates[facility_id],
                    *complaint_candidates[facility_id],
                ),
                availability=FacilityProjectionSourceAvailability(
                    program_reference=(
                        reference_available
                        and not (
                            reference_matching_counts[facility_id]
                            and not reference_candidates[facility_id]
                        )
                    ),
                    complaint_linked_facility=(
                        complaint_available
                        and not (
                            complaint_matching_counts[facility_id]
                            and not complaint_candidates[facility_id]
                        )
                    ),
                ),
                ineligible_candidate_excluded=(
                    not reference_candidates[facility_id]
                    and not complaint_candidates[facility_id]
                    and (
                        reference_matching_counts[facility_id] > 0
                        or complaint_matching_counts[facility_id] > 0
                    )
                ),
            )
            for facility_id in facility_ids
        }
    )


def _project_field(
    field: FacilityProjectionField,
    candidates: Sequence[FacilityProjectionCandidate],
    availability: FacilityProjectionSourceAvailability,
) -> FacilityFieldResult:
    alternatives = tuple(
        sorted(
            (
                alternative
                for candidate in candidates
                if (alternative := _alternative(candidate, field)) is not None
            ),
            key=_alternative_sort_key,
        )
    )
    unavailable_sources = _unavailable_sources(availability)
    populated = tuple(
        alternative
        for alternative in alternatives
        if alternative.normalized_value is not None
        and alternative.state
        in {FacilityValueState.POPULATED, FacilityValueState.UNRESOLVED_RAW_CODE}
    )
    distinct_values = {alternative.normalized_value for alternative in populated}
    conflict = len(distinct_values) > 1
    selected = _select_alternative(field, populated)

    if conflict:
        state = FacilityValueState.CONFLICTING
    elif selected is not None and selected.state is FacilityValueState.UNRESOLVED_RAW_CODE:
        state = FacilityValueState.UNRESOLVED_RAW_CODE
    elif selected is not None:
        state = FacilityValueState.POPULATED
    elif any(item.state is FacilityValueState.INVALID for item in alternatives):
        state = FacilityValueState.INVALID
    elif any(item.state is FacilityValueState.BLANK for item in alternatives):
        state = FacilityValueState.BLANK
    elif unavailable_sources:
        state = FacilityValueState.UNAVAILABLE
    else:
        state = FacilityValueState.ABSENT

    return FacilityFieldResult(
        field=field,
        display_value=(
            _selected_display_value(field, selected) if selected is not None else None
        ),
        normalized_value=selected.normalized_value if selected is not None else None,
        state=state,
        source_identity=selected.source_identity if selected is not None else None,
        observed_at=selected.observed_at if selected is not None else None,
        conflict=conflict,
        alternatives=alternatives,
        context=selected.context if selected is not None else None,
        unavailable_sources=unavailable_sources,
    )


def _project_internal_identity(
    candidates: Sequence[FacilityProjectionCandidate],
) -> FacilityFieldResult:
    alternatives = tuple(
        sorted(
            (
                FacilityValueAlternative(
                    raw_value=candidate.canonical_internal_identity,
                    normalized_value=candidate.canonical_internal_identity,
                    state=FacilityValueState.INTERNAL_ONLY,
                    source_identity=FacilitySourceIdentity(
                        source_kind=candidate.source_kind,
                        source_row_identity=candidate.source_row_identity,
                        snapshot_identity=candidate.snapshot_identity,
                        source_field="canonical_internal_identity",
                    ),
                    observed_at=candidate.observed_at,
                    context=FacilityValueContext.INTERNAL,
                )
                for candidate in candidates
                if candidate.canonical_internal_identity
            ),
            key=_alternative_sort_key,
        )
    )
    distinct_values = {item.normalized_value for item in alternatives}
    selected = alternatives[0] if len(distinct_values) == 1 and alternatives else None
    return FacilityFieldResult(
        field=FacilityProjectionField.CANONICAL_INTERNAL_IDENTITY,
        display_value=None,
        normalized_value=selected.normalized_value if selected is not None else None,
        state=FacilityValueState.INTERNAL_ONLY,
        source_identity=selected.source_identity if selected is not None else None,
        observed_at=selected.observed_at if selected is not None else None,
        conflict=len(distinct_values) > 1,
        alternatives=alternatives,
        context=FacilityValueContext.INTERNAL,
    )


def _alternative(
    candidate: FacilityProjectionCandidate,
    field: FacilityProjectionField,
) -> FacilityValueAlternative | None:
    if field not in candidate.present_fields:
        return None
    raw_value = candidate.values.get(field)
    normalized_value, state = _normalize_value(field, raw_value)
    return FacilityValueAlternative(
        raw_value=_observation_value(field, raw_value),
        normalized_value=normalized_value,
        state=state,
        source_identity=FacilitySourceIdentity(
            source_kind=candidate.source_kind,
            source_row_identity=candidate.source_row_identity,
            snapshot_identity=candidate.snapshot_identity,
            source_field=candidate.source_fields.get(field, field.value),
        ),
        observed_at=candidate.observed_at,
        context=candidate.context,
    )


def _normalize_value(
    field: FacilityProjectionField,
    raw_value: Any,
) -> tuple[FacilityValue | None, FacilityValueState]:
    if raw_value is None:
        return None, FacilityValueState.BLANK
    if field is FacilityProjectionField.CAPACITY:
        if isinstance(raw_value, bool):
            return None, FacilityValueState.INVALID
        if isinstance(raw_value, int):
            return raw_value, FacilityValueState.POPULATED
        capacity = _clean_text(raw_value).replace(",", "")
        if not capacity:
            return None, FacilityValueState.BLANK
        if capacity.isdigit():
            return int(capacity), FacilityValueState.POPULATED
        return None, FacilityValueState.INVALID

    text = _clean_text(raw_value)
    if not text:
        return None, FacilityValueState.BLANK
    normalized = text.casefold()
    if field is FacilityProjectionField.PUBLIC_FACILITY_ID:
        if not text.isdigit():
            return None, FacilityValueState.INVALID
        normalized = text
    if field in {
        FacilityProjectionField.FACILITY_TYPE,
        FacilityProjectionField.STATUS,
    } and text.isdigit():
        return normalized, FacilityValueState.UNRESOLVED_RAW_CODE
    return normalized, FacilityValueState.POPULATED


def _observation_value(
    field: FacilityProjectionField,
    raw_value: Any,
) -> FacilityValue | None:
    if raw_value is None:
        return None
    if field is FacilityProjectionField.CAPACITY and isinstance(raw_value, int):
        return raw_value
    return _clean_text(raw_value)


def _selected_display_value(
    field: FacilityProjectionField,
    alternative: FacilityValueAlternative,
) -> FacilityValue | None:
    if field is FacilityProjectionField.CAPACITY:
        return alternative.normalized_value
    return alternative.raw_value


def _select_alternative(
    field: FacilityProjectionField,
    alternatives: Sequence[FacilityValueAlternative],
) -> FacilityValueAlternative | None:
    if not alternatives:
        return None
    precedence = _FIELD_PRECEDENCE[field]
    for source_kind in precedence:
        source_alternatives = tuple(
            alternative
            for alternative in alternatives
            if alternative.source_identity.source_kind is source_kind
        )
        if not source_alternatives:
            continue
        newest_observed_at = max(
            (alternative.observed_at or "" for alternative in source_alternatives),
            default="",
        )
        newest = tuple(
            alternative
            for alternative in source_alternatives
            if (alternative.observed_at or "") == newest_observed_at
        )
        if len({alternative.normalized_value for alternative in newest}) == 1:
            return min(newest, key=_alternative_sort_key)
        return None
    return None


def _candidate_from_reference_row(
    row: Mapping[str, Any],
) -> FacilityProjectionCandidate:
    from ccld_complaints.hosted_app.facility_reference_preload import (
        FACILITY_REFERENCE_TABLE_NAME,
    )

    original_values = row.get("original_row_json")
    original = original_values if isinstance(original_values, Mapping) else {}
    values: dict[str, Any] = dict(original)
    for field in PUBLIC_FACILITY_FIELDS:
        typed_column = _REFERENCE_TYPED_COLUMNS[field]
        typed_value = row.get(typed_column)
        if typed_value is not None:
            values[_REFERENCE_FIELD_ALIASES[field][0]] = typed_value
    source_resource_id = str(row.get("source_resource_id") or "").strip()
    snapshot_marker = str(row.get("snapshot_date") or row.get("source_accessed_at") or "")
    candidate = facility_projection_candidate_from_values(
        values,
        source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
        source_row_identity=(
            f"{source_resource_id}:{str(row.get('facility_number') or '').strip()}"
        ),
        snapshot_identity=f"{source_resource_id}:{snapshot_marker}",
        observed_at=_optional_text(row.get("source_accessed_at")),
    )
    return replace(
        candidate,
        source_fields=MappingProxyType(
            {
                field: (
                    f"{FACILITY_REFERENCE_TABLE_NAME}.{_REFERENCE_TYPED_COLUMNS[field]}"
                    if row.get(_REFERENCE_TYPED_COLUMNS[field]) is not None
                    else f"original_row_json.{candidate.source_fields[field]}"
                )
                for field in candidate.present_fields
            }
        ),
    )


def _candidate_from_source_record(
    record: SourceDerivedRecordRead,
) -> FacilityProjectionCandidate:
    candidate = facility_projection_candidate_from_values(
        record.original_values,
        source_kind=FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
        source_row_identity=record.stable_source_id,
        snapshot_identity=record.import_batch.source_artifact_identity,
        observed_at=record.retrieved_at,
        canonical_internal_identity=record.source_record_key,
    )
    return replace(
        candidate,
        source_fields=MappingProxyType(
            {
                field: f"original_values.{source_field}"
                for field, source_field in candidate.source_fields.items()
            }
        ),
    )


def _candidate_matches_public_facility_id(
    candidate: FacilityProjectionCandidate,
    facility_id: str,
) -> bool:
    source_value = candidate.values.get(FacilityProjectionField.PUBLIC_FACILITY_ID)
    return _clean_text(source_value) == facility_id


def _source_record_public_facility_id(
    record: SourceDerivedRecordRead,
) -> str | None:
    for alias in _CANONICAL_FIELD_ALIASES[
        FacilityProjectionField.PUBLIC_FACILITY_ID
    ]:
        if alias in record.original_values:
            facility_id = _clean_text(record.original_values.get(alias))
            return facility_id if facility_id.isdigit() else None
    return None


def _eligible_reference_row(row: Mapping[str, Any]) -> bool:
    from ccld_complaints.hosted_app.facility_reference_preload import (
        FACILITY_REFERENCE_DATASET_SLUG,
    )

    return (
        _clean_text(row.get("source_resource_id")) in _APPROVED_REFERENCE_RESOURCE_IDS
        and _clean_text(row.get("source_dataset_slug"))
        == FACILITY_REFERENCE_DATASET_SLUG
    )


def _unsafe_reference_row(row: Mapping[str, Any]) -> bool:
    inspected = " ".join(
        _clean_text(row.get(key)).casefold()
        for key in (
            "source_resource_id",
            "source_resource_name",
            "source_file_name",
            "source_dataset_slug",
        )
    )
    return any(marker in inspected for marker in _UNSAFE_SOURCE_MARKERS)


def _unsafe_source_record(record: SourceDerivedRecordRead) -> bool:
    inspected = " ".join(
        (
            record.source_url,
            record.raw_path or "",
            record.import_batch.source_artifact_identity,
            record.import_batch.import_batch_id,
        )
    ).casefold()
    return any(marker in inspected for marker in _UNSAFE_SOURCE_MARKERS)


def _present_alias_value(
    values: Mapping[str, Any],
    aliases: Sequence[str],
) -> tuple[str, Any] | None:
    normalized_keys = {_normalized_key(str(key)): str(key) for key in values}
    for alias in aliases:
        original_key = normalized_keys.get(_normalized_key(alias))
        if original_key is not None:
            return original_key, values.get(original_key)
    return None


def _unavailable_sources(
    availability: FacilityProjectionSourceAvailability,
) -> tuple[FacilitySourceKind, ...]:
    unavailable: list[FacilitySourceKind] = []
    if not availability.program_reference:
        unavailable.append(FacilitySourceKind.PROGRAM_REFERENCE)
    if not availability.complaint_linked_facility:
        unavailable.append(FacilitySourceKind.COMPLAINT_LINKED_FACILITY)
    return tuple(unavailable)


def _alternative_sort_key(
    alternative: FacilityValueAlternative,
) -> tuple[str, str, str, str, str]:
    return (
        alternative.source_identity.source_kind.value,
        alternative.observed_at or "",
        alternative.source_identity.snapshot_identity,
        alternative.source_identity.source_row_identity,
        repr(alternative.normalized_value),
    )


def _validated_public_facility_id(value: str) -> str:
    facility_id = _clean_text(value)
    if not facility_id or not facility_id.isdigit():
        raise ValueError("public_facility_id must contain digits only.")
    return facility_id


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _optional_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return _SPACE_PATTERN.sub(" ", str(value)).strip()
