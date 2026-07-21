from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal

from ccld_complaints.statewide_facility_source_evaluation import canonical_fingerprint

SOURCE_FAMILY_ID: Final = "ccld-transparencyapi-facility-reference"
CONNECTOR_VERSION: Final = "1.0.0"
SNAPSHOT_SCOPE: Final = "governed_transparencyapi"
OBSERVATION_KIND: Final = "bulk_export_family"
BASE_URL: Final = "https://www.ccld.dss.ca.gov/transparencyapi/api"

EXPORT_IDS: Final = (
    "FosterFamilyAgencies",
    "24HourResidentialCareforChildren",
    "ResidentialElderCareFacility",
    "ChildCareCenters",
    "CHILDCAREHOMEmorethan8",
    "AdultResidentialFacilities",
    "HomeCare",
)
RCFE_EXPORT_ID: Final = "ResidentialElderCareFacility"

STANDARD_HEADERS: Final = (
    "Facility Type",
    "Facility Number",
    "Facility Name",
    "Licensee",
    "Facility Administrator",
    "Facility Telephone Number",
    "Facility Address",
    "Facility City",
    "Facility State",
    "Facility Zip",
    "County Name",
    "Regional Office",
    "Facility Capacity",
    "Facility Status",
    "License First Date",
    "Closed Date",
    "Last Visit Date",
    "Inspection Visits",
    "Complaint Visits",
    "Other Visits",
    "Total Visits",
    "Citation Numbers",
    "POC Dates",
    "All Visit Dates",
    "Inspection Visit Dates",
    "Inspect TypeA",
    "Inspect TypeB",
    "Other Visit Dates",
    "Other TypeA",
    "Other TypeB",
    "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ...",
)
RCFE_HEADERS: Final = (
    *STANDARD_HEADERS[:30],
    "Complaint Type A",
    "Complaint Type B",
    "Total Allegations",
    "Inconclusive Allegations",
    "Substantiated Allegations",
    "Unsubstantiated Allegations",
    "Unfounded Allegations",
    "Complaint Info- Date, #Sub A, # Inc A, # Uns A, # Unf A, # TypeA, # TypeB ...",
)
STANDARD_COMPLAINT_FIELDS: Final = (
    "date",
    "substantiated_allegations",
    "inconclusive_allegations",
    "unsubstantiated_allegations",
    "type_a_citations",
    "type_b_citations",
)
RCFE_COMPLAINT_FIELDS: Final = (
    "date",
    "substantiated_allegations",
    "inconclusive_allegations",
    "unsubstantiated_allegations",
    "unfounded_allegations",
    "type_a_citations",
    "type_b_citations",
)

PLACEHOLDER_LITERALS: Final = frozenset(
    {"unavailable", "see faqs", "n/a", "na", "not available", "not provided"}
)
PRESERVE_POPULATED_FIELDS: Final = frozenset({"facility_address", "facility_telephone_number"})

SemanticState = Literal["populated", "blank", "placeholder", "absent"]


def expected_headers(export_id: str) -> tuple[str, ...]:
    if export_id not in EXPORT_IDS:
        raise ValueError(f"Unapproved TransparencyAPI export ID: {export_id}")
    return RCFE_HEADERS if export_id == RCFE_EXPORT_ID else STANDARD_HEADERS


def complaint_fields(export_id: str) -> tuple[str, ...]:
    return RCFE_COMPLAINT_FIELDS if export_id == RCFE_EXPORT_ID else STANDARD_COMPLAINT_FIELDS


def normalized_observation(raw: object = None, *, present: bool = True) -> dict[str, Any]:
    if not present:
        return {"state": "absent", "raw": None, "value": None}
    literal = "" if raw is None else str(raw)
    stripped = literal.strip()
    if not stripped:
        state: SemanticState = "blank"
        value: str | None = None
    elif stripped.casefold() in PLACEHOLDER_LITERALS:
        state = "placeholder"
        value = stripped
    else:
        state = "populated"
        value = stripped
    return {"state": state, "raw": literal, "value": value}


def normalize_bulk_row(raw_record: Mapping[str, str]) -> dict[str, Any]:
    sources = {
        "facility_type": "Facility Type",
        "facility_number": "Facility Number",
        "facility_name": "Facility Name",
        "licensee": "Licensee",
        "facility_administrator": "Facility Administrator",
        "facility_telephone_number": "Facility Telephone Number",
        "facility_address": "Facility Address",
        "facility_city": "Facility City",
        "facility_state": "Facility State",
        "facility_zip": "Facility Zip",
        "county_name": "County Name",
        "regional_office": "Regional Office",
        "facility_capacity": "Facility Capacity",
        "bulk_status": "Facility Status",
        "license_first_date": "License First Date",
        "closed_date": "Closed Date",
        "last_visit_date": "Last Visit Date",
    }
    return {
        name: normalized_observation(raw_record.get(source), present=source in raw_record)
        for name, source in sources.items()
    }


def preserve_prior_populated_values(
    current: Mapping[str, Any],
    prior: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolve only fields whose blank/placeholder non-overwrite rule is source-governed."""
    resolved = {
        key: dict(value) if isinstance(value, Mapping) else value for key, value in current.items()
    }
    if prior is None:
        return resolved
    for field_name in PRESERVE_POPULATED_FIELDS:
        current_value = resolved.get(field_name)
        prior_value = prior.get(field_name)
        if not isinstance(current_value, Mapping) or not isinstance(prior_value, Mapping):
            continue
        if current_value.get("state") not in {"blank", "placeholder", "absent"}:
            continue
        if prior_value.get("state") != "populated":
            continue
        preserved = dict(prior_value)
        preserved["preserved_from_prior"] = True
        preserved["superseding_observation"] = dict(current_value)
        resolved[field_name] = preserved
    return resolved


def schema_fingerprint(export_id: str) -> str:
    return canonical_fingerprint(list(expected_headers(export_id)))


def source_family_schema_fingerprint() -> str:
    return canonical_fingerprint(
        {export_id: list(expected_headers(export_id)) for export_id in EXPORT_IDS}
    )
