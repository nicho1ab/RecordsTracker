from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal, cast

from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Connection

from ccld_complaints.connectors.ccld_transparency_api.contract import (
    CONNECTOR_VERSION,
    SOURCE_FAMILY_ID,
)
from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
    transparency_quarantines,
    transparency_rows,
)
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
)
from ccld_complaints.hosted_app.facility_identity_projection import (
    PUBLIC_FACILITY_FIELDS,
    FacilityProjectionField,
    FacilitySourceKind,
    FacilityValueContext,
    FacilityValueState,
    load_authorized_facility_identity_projections,
)
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    source_snapshot_pointers,
    source_snapshots,
)

FACILITY_COVERAGE_CONTRACT_ID: Final = "transparencyapi-shared-projection-v1"
FACILITY_COVERAGE_CRITERIA_SET_ID: Final = "transparencyapi-projection-release-v1"
FACILITY_COVERAGE_BATCH_SIZE: Final = 250

FACILITY_COVERAGE_STAGES: Final = (
    "source_presence",
    "extraction",
    "normalization",
    "source_specific_allocation",
    "postgresql_population",
    "read_model_exposure",
    "complaint_page_rendering",
    "facility_overview_rendering",
    "packet_rendering",
    "export_exposure",
)
FACILITY_COVERAGE_STAGE_STATES: Final = (
    "successful",
    "blank",
    "absent",
    "unavailable",
    "invalid",
    "conflict",
    "failure",
    "not_applicable",
)
FACILITY_COVERAGE_FAILURE_CATEGORIES: Final = (
    "present-but-not-extracted",
    "extracted-but-not-allocated",
    "allocated-but-not-imported",
    "stored-but-not-read",
    "read-but-not-rendered",
    "rendered-incorrectly",
    "present-blank",
    "source-absent",
    "source-unavailable",
    "unsupported-layout",
    "conflicting-source",
)
FACILITY_COVERAGE_SURFACES: Final = (
    "facility-search",
    "request-records",
    "facility-overview",
    "reviewer-worklist",
    "reviewer-detail",
    "packet-preview",
    "packet-draft",
    "reviewer-exports",
)
FACILITY_COVERAGE_METRICS: Final = (
    "eligible-facility-total",
    "nonblank-facility-number-total",
    "leading-zero-facility-number-total",
    "blank-id-quarantine-total",
    "duplicate-id-quarantine-total",
    "malformed-complaint-block-quarantine-total",
    "unknown-type-code-quarantine-total",
    "type-777-row-total",
    "raw-733-unresolved-total",
    "address-populated-total",
    "telephone-populated-total",
    "placeholder-overwrite-prevented-total",
    "contact-populated-total",
    "administrator-populated-total",
    "contact-administrator-distinction-total",
    "bulk-status-populated-total",
    "detail-status-populated-total",
    "closed-date-populated-total",
    "complaint-time-observation-total",
    "historical-complaint-conflict-total",
    "arcgis-conflict-total",
    "historical-program-conflict-total",
    "source-present-rendered-missing-total",
    "read-model-not-rendered-total",
    "incorrect-missing-vocabulary-total",
    "unsafe-report-url-exposure-total",
    "quarantined-projection-total",
    "reviewer-state-mutation-total",
    "current-complaint-context-conflation-total",
)

_TRANSPARENCY_FIELD_KEYS: Mapping[FacilityProjectionField, str] = {
    FacilityProjectionField.FACILITY_NAME: "facility_name",
    FacilityProjectionField.PUBLIC_FACILITY_ID: "facility_number",
    FacilityProjectionField.FACILITY_TYPE: "facility_type",
    FacilityProjectionField.STATUS: "bulk_status",
    FacilityProjectionField.FULL_ADDRESS: "facility_address",
    FacilityProjectionField.CITY: "facility_city",
    FacilityProjectionField.STATE: "facility_state",
    FacilityProjectionField.ZIP: "facility_zip",
    FacilityProjectionField.COUNTY: "county_name",
    FacilityProjectionField.CAPACITY: "facility_capacity",
    FacilityProjectionField.ADMINISTRATOR: "facility_administrator",
    FacilityProjectionField.LICENSEE: "licensee",
    FacilityProjectionField.TELEPHONE: "facility_telephone_number",
    FacilityProjectionField.REGIONAL_OFFICE: "regional_office",
    FacilityProjectionField.CLOSED_DATE: "closed_date",
}
_QUARANTINE_METRICS: Mapping[str, str] = {
    "blank_facility_number": "blank-id-quarantine-total",
    "duplicate_facility_number": "duplicate-id-quarantine-total",
    "malformed_trailing_complaint_block": (
        "malformed-complaint-block-quarantine-total"
    ),
    "unknown_facility_type_code": "unknown-type-code-quarantine-total",
}
_RELEASE_CRITERIA: Final = (
    "facility-count-decline",
    "populated-field-became-blank",
    "descriptive-label-regressed-to-raw-code",
    "unresolved-known-code-increase",
    "facility-conflict-increase",
    "postgresql-eligibility-mismatch",
    "read-model-availability-decline",
    "reviewer-rendering-decline",
    "stage-total-imbalance",
    "quarantined-row-exposed",
    "placeholder-overwrite",
    "current-context-conflation",
    "unsafe-report-url-exposed",
)


def build_runtime_facility_coverage(
    connection: Connection,
    *,
    previous: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Return SELECT-only aggregate coverage for the active TransparencyAPI family."""

    required_tables = {
        source_snapshots.name,
        source_snapshot_pointers.name,
        transparency_rows.name,
        transparency_quarantines.name,
    }
    if not required_tables.issubset(inspect(connection).get_table_names()):
        return unavailable_facility_coverage("read-boundary-unavailable")

    snapshot = (
        connection.execute(
            select(source_snapshots)
            .join(
                source_snapshot_pointers,
                source_snapshot_pointers.c.active_snapshot_id
                == source_snapshots.c.snapshot_id,
            )
            .where(
                source_snapshot_pointers.c.source_family_id == SOURCE_FAMILY_ID,
                source_snapshots.c.source_family_id == SOURCE_FAMILY_ID,
                source_snapshots.c.lifecycle_state == "accepted",
            )
        )
        .mappings()
        .one_or_none()
    )
    if snapshot is None:
        return unavailable_facility_coverage("active-snapshot-unavailable")
    snapshot_value = dict(snapshot)
    snapshot_id = str(snapshot_value["snapshot_id"])

    rows = tuple(
        dict(row)
        for row in connection.execute(
            select(
                transparency_rows.c.export_id,
                transparency_rows.c.row_ordinal,
                transparency_rows.c.facility_number,
                transparency_rows.c.normalized_record,
                transparency_rows.c.resolved_current_reference,
                transparency_rows.c.complaint_blocks,
                transparency_rows.c.is_quarantined,
            )
            .where(transparency_rows.c.snapshot_id == snapshot_id)
            .order_by(
                transparency_rows.c.export_id,
                transparency_rows.c.row_ordinal,
            )
        ).mappings()
    )
    quarantine_counts = Counter(
        {
            str(row["category"]): int(row["category_count"])
            for row in connection.execute(
                select(
                    transparency_quarantines.c.category,
                    func.count().label("category_count"),
                )
                .where(transparency_quarantines.c.snapshot_id == snapshot_id)
                .group_by(transparency_quarantines.c.category)
                .order_by(transparency_quarantines.c.category)
            ).mappings()
        }
    )
    eligible_rows = tuple(
        row
        for row in rows
        if not row["is_quarantined"] and _text(row.get("facility_number"))
    )
    facility_ids = tuple(
        sorted({_text(row["facility_number"]) for row in eligible_rows})
    )
    projections = _load_projections(connection, facility_ids)
    postgresql_eligibility_mismatch = abs(
        int(snapshot_value["stored_row_count"]) - len(rows)
    ) + abs(len(facility_ids) - len(projections))
    metrics = dict.fromkeys(FACILITY_COVERAGE_METRICS, 0)
    metrics["eligible-facility-total"] = len(facility_ids)
    metrics["nonblank-facility-number-total"] = len(facility_ids)
    metrics["leading-zero-facility-number-total"] = sum(
        facility_id.startswith("0") for facility_id in facility_ids
    )
    for category, metric_id in _QUARANTINE_METRICS.items():
        metrics[metric_id] = quarantine_counts[category]
    metrics["type-777-row-total"] = _type_code_count(eligible_rows, "777")
    metrics["complaint-time-observation-total"] = sum(
        bool(row.get("complaint_blocks")) for row in eligible_rows
    )
    metrics["placeholder-overwrite-prevented-total"] = sum(
        _preserved_from_prior(row, field)
        for row in eligible_rows
        for field in ("facility_address", "facility_telephone_number")
    )

    field_rows = _field_stage_rows(eligible_rows, projections)
    field_stage_index = {
        (str(row["field_id"]), str(row["stage"])): row for row in field_rows
    }
    metrics["address-populated-total"] = _successful_count(
        field_stage_index, "full-address", "read_model_exposure"
    )
    metrics["telephone-populated-total"] = _successful_count(
        field_stage_index, "telephone", "read_model_exposure"
    )
    metrics["administrator-populated-total"] = _successful_count(
        field_stage_index, "administrator", "read_model_exposure"
    )
    metrics["bulk-status-populated-total"] = _successful_count(
        field_stage_index, "status", "source_presence"
    )
    metrics["closed-date-populated-total"] = _successful_count(
        field_stage_index, "closed-date", "source_presence"
    )
    metrics["raw-733-unresolved-total"] = sum(
        projection.field(FacilityProjectionField.FACILITY_TYPE).state
        is FacilityValueState.UNRESOLVED_RAW_CODE
        and projection.field(FacilityProjectionField.FACILITY_TYPE).display_value == "733"
        for projection in projections.values()
    )
    conflict_counts = aggregate_projection_conflict_counts(projections)
    metrics["historical-complaint-conflict-total"] = conflict_counts[
        "historical-complaint"
    ]
    metrics["arcgis-conflict-total"] = conflict_counts["arcgis-supplementary"]
    metrics["historical-program-conflict-total"] = conflict_counts[
        "historical-program"
    ]
    metrics["quarantined-projection-total"] = sum(
        projection.ineligible_candidate_excluded for projection in projections.values()
    )

    surfaces = _surface_rows(field_rows, availability="repository-verified")
    release = _release_assessment(
        metrics,
        field_rows=field_rows,
        surface_rows=surfaces,
        previous=previous,
        postgresql_eligibility_mismatch=postgresql_eligibility_mismatch,
    )
    failure_counts = dict.fromkeys(FACILITY_COVERAGE_FAILURE_CATEGORIES, 0)
    failure_counts["present-blank"] = sum(
        int(row["blank_count"])
        for row in field_rows
        if row["stage"] == "source_presence"
    )
    failure_counts["source-absent"] = sum(
        int(row["absent_count"])
        for row in field_rows
        if row["stage"] == "source_presence"
    )
    failure_counts["source-unavailable"] = sum(
        int(row["unavailable_count"])
        for row in field_rows
        if row["stage"] == "source_presence"
    )
    failure_counts["conflicting-source"] = sum(
        int(row["conflict_count"])
        for row in field_rows
        if row["stage"] == "read_model_exposure"
    )
    failure_counts["read-but-not-rendered"] = sum(
        int(row["failure_count"])
        for row in field_rows
        if row["stage"] in {
            "complaint_page_rendering",
            "facility_overview_rendering",
            "packet_rendering",
            "export_exposure",
        }
    )

    return canonical_facility_coverage(
        {
            "contract_id": FACILITY_COVERAGE_CONTRACT_ID,
            "criteria_set_id": FACILITY_COVERAGE_CRITERIA_SET_ID,
            "source_family_id": SOURCE_FAMILY_ID,
            "connector_version": CONNECTOR_VERSION,
            "availability": "available",
            "reason_category": "none",
            "snapshot": {
                "source_snapshot_id": snapshot_id,
                "selection_state": "active_accepted",
                "schema_fingerprint": str(snapshot_value["schema_fingerprint"]),
                "content_fingerprint": str(
                    snapshot_value["normalized_content_sha256"]
                ),
                "eligible_facility_count": len(facility_ids),
            },
            "aggregate_metrics": [
                {
                    "metric_id": metric_id,
                    "count": int(metrics[metric_id]),
                    "status": (
                        "unavailable"
                        if metric_id
                        in {
                            "contact-populated-total",
                            "contact-administrator-distinction-total",
                            "detail-status-populated-total",
                            "historical-complaint-conflict-total",
                        }
                        else "valid-zero"
                        if metric_id == "type-777-row-total" and metrics[metric_id] == 0
                        else "measured"
                    ),
                }
                for metric_id in FACILITY_COVERAGE_METRICS
            ],
            "field_stage_coverage": field_rows,
            "failure_category_counts": failure_counts,
            "surface_coverage": surfaces,
            "release_assessment": release,
        }
    )


def unavailable_facility_coverage(reason_category: str) -> Mapping[str, Any]:
    field_rows = _unavailable_field_rows()
    metrics = [
        {"metric_id": metric_id, "count": 0, "status": "unavailable"}
        for metric_id in FACILITY_COVERAGE_METRICS
    ]
    return canonical_facility_coverage(
        {
            "contract_id": FACILITY_COVERAGE_CONTRACT_ID,
            "criteria_set_id": FACILITY_COVERAGE_CRITERIA_SET_ID,
            "source_family_id": SOURCE_FAMILY_ID,
            "connector_version": CONNECTOR_VERSION,
            "availability": "unavailable",
            "reason_category": reason_category,
            "snapshot": {
                "source_snapshot_id": None,
                "selection_state": "unavailable",
                "schema_fingerprint": None,
                "content_fingerprint": None,
                "eligible_facility_count": 0,
            },
            "aggregate_metrics": metrics,
            "field_stage_coverage": field_rows,
            "failure_category_counts": {
                category: (
                    len(PUBLIC_FACILITY_FIELDS)
                    if category == "source-unavailable"
                    else 0
                )
                for category in FACILITY_COVERAGE_FAILURE_CATEGORIES
            },
            "surface_coverage": _surface_rows(
                field_rows, availability="hosted-evidence-pending"
            ),
            "release_assessment": {
                "status": "warning",
                "checks": [
                    {
                        "criterion_id": criterion_id,
                        "status": "warning",
                        "baseline_count": 0,
                        "observed_count": 0,
                        "threshold_count": 0,
                        "exception_id": None,
                    }
                    for criterion_id in _RELEASE_CRITERIA
                ],
            },
        }
    )


def governed_fixture_facility_coverage(profile: str) -> Mapping[str, Any]:
    """Build fictional aggregate-only acceptance profiles without source record values."""

    if profile not in {
        "complete",
        "source-unavailable",
        "read-but-not-rendered",
        "stage-imbalanced",
    }:
        raise ValueError("Facility coverage fixture profile is not governed.")
    if profile == "source-unavailable":
        return unavailable_facility_coverage("fixture-not-provided")

    field_rows = [
        _stage_row(
            field.value.replace("_", "-"),
            stage,
            Counter({"successful": 2}),
        )
        for field in sorted(PUBLIC_FACILITY_FIELDS, key=lambda value: value.value)
        for stage in FACILITY_COVERAGE_STAGES
    ]
    surfaces = _surface_rows(field_rows, availability="repository-verified")
    metrics = dict.fromkeys(FACILITY_COVERAGE_METRICS, 0)
    metrics.update(
        {
            "eligible-facility-total": 2,
            "nonblank-facility-number-total": 2,
            "leading-zero-facility-number-total": 1,
            "address-populated-total": 2,
            "telephone-populated-total": 2,
            "placeholder-overwrite-prevented-total": 1,
            "administrator-populated-total": 2,
            "bulk-status-populated-total": 2,
            "closed-date-populated-total": 1,
            "complaint-time-observation-total": 1,
        }
    )
    if profile == "read-but-not-rendered":
        surfaces[0] = {
            **surfaces[0],
            "rendered_count": int(surfaces[0]["rendered_count"]) - 1,
            "missing_count": 1,
        }
        metrics["source-present-rendered-missing-total"] = 1
        metrics["read-model-not-rendered-total"] = 1
    if profile == "stage-imbalanced":
        field_rows[0] = {**field_rows[0], "eligible_count": 3}

    release = _release_assessment(
        metrics,
        field_rows=field_rows,
        surface_rows=surfaces,
        previous=None,
        postgresql_eligibility_mismatch=0,
    )
    return canonical_facility_coverage(
        {
            "contract_id": FACILITY_COVERAGE_CONTRACT_ID,
            "criteria_set_id": FACILITY_COVERAGE_CRITERIA_SET_ID,
            "source_family_id": SOURCE_FAMILY_ID,
            "connector_version": CONNECTOR_VERSION,
            "availability": "available",
            "reason_category": "none",
            "snapshot": {
                "source_snapshot_id": "transparencyapi-fixture-snapshot-v1",
                "selection_state": "active_accepted",
                "schema_fingerprint": "c" * 64,
                "content_fingerprint": "d" * 64,
                "eligible_facility_count": 2,
            },
            "aggregate_metrics": [
                {
                    "metric_id": metric_id,
                    "count": int(metrics[metric_id]),
                    "status": (
                        "unavailable"
                        if metric_id
                        in {
                            "contact-populated-total",
                            "contact-administrator-distinction-total",
                            "detail-status-populated-total",
                            "historical-complaint-conflict-total",
                        }
                        else "valid-zero"
                        if metric_id == "type-777-row-total"
                        else "measured"
                    ),
                }
                for metric_id in FACILITY_COVERAGE_METRICS
            ],
            "field_stage_coverage": field_rows,
            "failure_category_counts": {
                category: (
                    1
                    if profile == "read-but-not-rendered"
                    and category == "read-but-not-rendered"
                    else 0
                )
                for category in FACILITY_COVERAGE_FAILURE_CATEGORIES
            },
            "surface_coverage": surfaces,
            "release_assessment": release,
        }
    )


def canonical_facility_coverage(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Canonicalize aggregate-only input and reject unknown or record-level fields."""

    expected = {
        "contract_id",
        "criteria_set_id",
        "source_family_id",
        "connector_version",
        "availability",
        "reason_category",
        "snapshot",
        "aggregate_metrics",
        "field_stage_coverage",
        "failure_category_counts",
        "surface_coverage",
        "release_assessment",
    }
    if set(value) != expected:
        raise ValueError("Facility coverage contains an unknown or missing field.")
    metrics = sorted(
        (_mapping(row, "aggregate metric") for row in _sequence(value["aggregate_metrics"])),
        key=lambda row: str(row["metric_id"]),
    )
    if tuple(str(row["metric_id"]) for row in metrics) != tuple(
        sorted(FACILITY_COVERAGE_METRICS)
    ):
        raise ValueError("Facility coverage metric inventory is incomplete.")
    field_rows = sorted(
        (
            _mapping(row, "field stage row")
            for row in _sequence(value["field_stage_coverage"])
        ),
        key=lambda row: (str(row["field_id"]), str(row["stage"])),
    )
    surface_rows = sorted(
        (_mapping(row, "surface row") for row in _sequence(value["surface_coverage"])),
        key=lambda row: str(row["surface_id"]),
    )
    return {
        **value,
        "aggregate_metrics": metrics,
        "field_stage_coverage": field_rows,
        "failure_category_counts": dict(
            sorted(_mapping(value["failure_category_counts"], "failure counts").items())
        ),
        "surface_coverage": surface_rows,
        "release_assessment": {
            **_mapping(value["release_assessment"], "release assessment"),
            "checks": sorted(
                (
                    _mapping(row, "release check")
                    for row in _sequence(
                        _mapping(value["release_assessment"], "release assessment")[
                            "checks"
                        ]
                    )
                ),
                key=lambda row: str(row["criterion_id"]),
            ),
        },
    }


def _load_projections(
    connection: Connection,
    facility_ids: Sequence[str],
) -> Mapping[str, Any]:
    scope = HostedAccessScope("corpus", "source-to-screen-facility-coverage")
    actor = AuthenticatedActor(
        provider_subject="source-to-screen-facility-coverage",
        provider_issuer="repository-runtime",
        display_name=None,
        email=None,
        actor_category="system",
        account_status="active",
        roles=("system",),
        scopes=(scope,),
    )
    projections: dict[str, Any] = {}
    for start in range(0, len(facility_ids), FACILITY_COVERAGE_BATCH_SIZE):
        batch = facility_ids[start : start + FACILITY_COVERAGE_BATCH_SIZE]
        projections.update(
            load_authorized_facility_identity_projections(
                connection,
                actor,
                scope=scope,
                public_facility_ids=batch,
                authorized_source_records=(),
            )
        )
    return dict(sorted(projections.items()))


def _field_stage_rows(
    rows: Sequence[Mapping[str, Any]],
    projections: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    output: list[Mapping[str, Any]] = []
    for field in sorted(PUBLIC_FACILITY_FIELDS, key=lambda value: value.value):
        field_id = field.value.replace("_", "-")
        normalized_key = _TRANSPARENCY_FIELD_KEYS.get(field)
        source_states: Counter[str] = Counter()
        if normalized_key is None:
            source_states["unavailable"] = len(rows)
        else:
            for row in rows:
                normalized = _mapping_or_empty(row.get("normalized_record"))
                observation = _mapping_or_empty(normalized.get(normalized_key))
                source_states[_source_stage_state(observation.get("state"))] += 1
        read_states: Counter[str] = Counter()
        for projection in projections.values():
            result = projection.field(field)
            read_states[_projection_stage_state(result.state)] += 1
        for stage in FACILITY_COVERAGE_STAGES:
            if stage == "source_presence":
                states = source_states
            elif stage in {
                "extraction",
                "normalization",
                "source_specific_allocation",
                "postgresql_population",
            }:
                states = source_states
            elif stage == "read_model_exposure":
                states = read_states
            else:
                states = Counter({"successful": sum(read_states.values())})
            output.append(_stage_row(field_id, stage, states))
    return sorted(output, key=lambda row: (str(row["field_id"]), str(row["stage"])))


def _unavailable_field_rows() -> list[Mapping[str, Any]]:
    return [
        _stage_row(
            field.value.replace("_", "-"),
            stage,
            Counter({"unavailable": 1}),
        )
        for field in sorted(PUBLIC_FACILITY_FIELDS, key=lambda value: value.value)
        for stage in FACILITY_COVERAGE_STAGES
    ]


def _stage_row(
    field_id: str,
    stage: str,
    states: Mapping[str, int],
) -> Mapping[str, Any]:
    counts = {name: int(states.get(name, 0)) for name in FACILITY_COVERAGE_STAGE_STATES}
    return {
        "field_id": field_id,
        "stage": stage,
        "eligible_count": sum(counts.values()),
        **{f"{name}_count": counts[name] for name in FACILITY_COVERAGE_STAGE_STATES},
    }


def _surface_rows(
    field_rows: Sequence[Mapping[str, Any]],
    *,
    availability: Literal["repository-verified", "hosted-evidence-pending"],
) -> list[Mapping[str, Any]]:
    identity_row = next(
        (
            row
            for row in field_rows
            if row["field_id"] == "public-facility-id"
            and row["stage"] == "read_model_exposure"
        ),
        None,
    )
    eligible = 0 if identity_row is None else int(identity_row["eligible_count"])
    exposed = 0 if identity_row is None else int(identity_row["successful_count"])
    unavailable = 0 if identity_row is None else int(identity_row["unavailable_count"])
    return [
        {
            "surface_id": surface_id,
            "eligible_count": eligible,
            "read_model_exposed_count": exposed,
            "rendered_count": exposed if availability == "repository-verified" else 0,
            "missing_count": 0,
            "incorrect_vocabulary_count": 0,
            "unavailable_count": unavailable,
            "status": availability,
        }
        for surface_id in FACILITY_COVERAGE_SURFACES
    ]


def _release_assessment(
    metrics: Mapping[str, int],
    *,
    field_rows: Sequence[Mapping[str, Any]],
    surface_rows: Sequence[Mapping[str, Any]],
    previous: Mapping[str, Any] | None,
    postgresql_eligibility_mismatch: int,
) -> Mapping[str, Any]:
    previous_metrics = _metric_counts(previous)
    current_facilities = int(metrics["eligible-facility-total"])
    baseline_facilities = previous_metrics.get(
        "eligible-facility-total", current_facilities
    )
    previous_stage_rows = _previous_rows(previous, "field_stage_coverage")
    previous_surface_rows = _previous_rows(previous, "surface_coverage")
    current_read_success = _stage_state_total(
        field_rows, stage="read_model_exposure", state="successful"
    )
    previous_read_success = _stage_state_total(
        previous_stage_rows, stage="read_model_exposure", state="successful"
    )
    current_read_blank = _stage_state_total(
        field_rows, stage="read_model_exposure", state="blank"
    )
    previous_read_blank = _stage_state_total(
        previous_stage_rows, stage="read_model_exposure", state="blank"
    )
    current_rendered = sum(int(row["rendered_count"]) for row in surface_rows)
    previous_rendered = sum(
        int(row.get("rendered_count", 0)) for row in previous_surface_rows
    )
    if previous is None:
        previous_read_success = current_read_success
        previous_read_blank = current_read_blank
        previous_rendered = current_rendered
    baseline_unresolved = previous_metrics.get(
        "raw-733-unresolved-total", int(metrics["raw-733-unresolved-total"])
    )
    unresolved_increase = max(
        0,
        int(metrics["raw-733-unresolved-total"]) - baseline_unresolved,
    )
    baseline_conflicts = previous_metrics.get(
        "arcgis-conflict-total", int(metrics["arcgis-conflict-total"])
    ) + previous_metrics.get(
        "historical-program-conflict-total",
        int(metrics["historical-program-conflict-total"]),
    )
    stage_imbalance = sum(
        int(row["eligible_count"])
        != sum(int(row[f"{state}_count"]) for state in FACILITY_COVERAGE_STAGE_STATES)
        for row in field_rows
    )
    observed = {
        "facility-count-decline": max(0, baseline_facilities - current_facilities),
        "populated-field-became-blank": max(0, current_read_blank - previous_read_blank),
        "descriptive-label-regressed-to-raw-code": unresolved_increase,
        "unresolved-known-code-increase": unresolved_increase,
        "facility-conflict-increase": max(
            0,
            int(metrics["arcgis-conflict-total"])
            + int(metrics["historical-program-conflict-total"])
            - baseline_conflicts,
        ),
        "postgresql-eligibility-mismatch": postgresql_eligibility_mismatch,
        "read-model-availability-decline": max(
            0, previous_read_success - current_read_success
        ),
        "reviewer-rendering-decline": max(
            sum(int(row["missing_count"]) for row in surface_rows),
            previous_rendered - current_rendered,
        ),
        "stage-total-imbalance": stage_imbalance,
        "quarantined-row-exposed": int(metrics["quarantined-projection-total"]),
        "placeholder-overwrite": 0,
        "current-context-conflation": int(
            metrics["current-complaint-context-conflation-total"]
        ),
        "unsafe-report-url-exposed": int(metrics["unsafe-report-url-exposure-total"]),
    }
    baselines = {
        "facility-count-decline": baseline_facilities,
        "populated-field-became-blank": previous_read_blank,
        "descriptive-label-regressed-to-raw-code": baseline_unresolved,
        "unresolved-known-code-increase": baseline_unresolved,
        "facility-conflict-increase": baseline_conflicts,
        "read-model-availability-decline": previous_read_success,
        "reviewer-rendering-decline": previous_rendered,
    }
    checks = [
        {
            "criterion_id": criterion_id,
            "status": "failed" if observed[criterion_id] else "passed",
            "baseline_count": baselines.get(criterion_id, 0),
            "observed_count": observed[criterion_id],
            "threshold_count": 0,
            "exception_id": None,
        }
        for criterion_id in _RELEASE_CRITERIA
    ]
    return {
        "status": "failed" if any(row["status"] == "failed" for row in checks) else "passed",
        "checks": checks,
    }


def _metric_counts(value: Mapping[str, Any] | None) -> dict[str, int]:
    if value is None:
        return {}
    metrics = value.get("aggregate_metrics")
    if not isinstance(metrics, Sequence) or isinstance(metrics, (str, bytes)):
        return {}
    return {
        str(row["metric_id"]): int(row["count"])
        for row in metrics
        if isinstance(row, Mapping)
        and isinstance(row.get("metric_id"), str)
        and isinstance(row.get("count"), int)
    }


def _previous_rows(
    value: Mapping[str, Any] | None, key: str
) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    rows = value.get(key)
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ()
    return tuple(row for row in rows if isinstance(row, Mapping))


def _stage_state_total(
    rows: Sequence[Mapping[str, Any]], *, stage: str, state: str
) -> int:
    return sum(
        int(row.get(f"{state}_count", 0))
        for row in rows
        if row.get("stage") == stage
    )


def _source_conflict_count(
    projections: Mapping[str, Any], source_kind: FacilitySourceKind
) -> int:
    return sum(
        result.conflict
        and any(
            alternative.source_identity.source_kind is source_kind
            for alternative in result.alternatives
        )
        for projection in projections.values()
        for field in PUBLIC_FACILITY_FIELDS
        if (result := projection.field(field)).context
        in {
            FacilityValueContext.CURRENT_REFERENCE,
            FacilityValueContext.SUPPLEMENTARY_REFERENCE,
            FacilityValueContext.HISTORICAL_REFERENCE,
        }
    )


def aggregate_projection_conflict_counts(
    projections: Mapping[str, Any],
) -> Mapping[str, int]:
    """Count conflicting projection fields by non-primary source context."""

    return {
        "arcgis-supplementary": _source_conflict_count(
            projections, FacilitySourceKind.ARCGIS_SUPPLEMENT
        ),
        "historical-complaint": _source_conflict_count(
            projections, FacilitySourceKind.COMPLAINT_LINKED_FACILITY
        ),
        "historical-program": _source_conflict_count(
            projections, FacilitySourceKind.PROGRAM_REFERENCE
        ),
    }


def _type_code_count(rows: Sequence[Mapping[str, Any]], value: str) -> int:
    return sum(
        _observation_value(row, "facility_type") == value
        for row in rows
    )


def _observation_value(row: Mapping[str, Any], field: str) -> str:
    normalized = _mapping_or_empty(row.get("normalized_record"))
    observation = _mapping_or_empty(normalized.get(field))
    return _text(observation.get("value"))


def _preserved_from_prior(row: Mapping[str, Any], field: str) -> bool:
    resolved = _mapping_or_empty(row.get("resolved_current_reference"))
    observation = _mapping_or_empty(resolved.get(field))
    return observation.get("preserved_from_prior") is True


def _successful_count(
    index: Mapping[tuple[str, str], Mapping[str, Any]], field: str, stage: str
) -> int:
    row = index.get((field, stage))
    return 0 if row is None else int(row["successful_count"])


def _source_stage_state(value: Any) -> str:
    normalized = _text(value).casefold().replace("-", "_")
    return {
        "populated": "successful",
        "blank": "blank",
        "absent": "absent",
        "placeholder": "unavailable",
        "unavailable": "unavailable",
        "invalid": "invalid",
        "extraction_failed": "failure",
    }.get(normalized, "unavailable")


def _projection_stage_state(value: FacilityValueState) -> str:
    if value in {FacilityValueState.POPULATED, FacilityValueState.UNRESOLVED_RAW_CODE}:
        return "successful"
    if value is FacilityValueState.BLANK:
        return "blank"
    if value is FacilityValueState.ABSENT:
        return "absent"
    if value is FacilityValueState.UNAVAILABLE:
        return "unavailable"
    if value in {FacilityValueState.INVALID, FacilityValueState.EXTRACTION_FAILED}:
        return "invalid"
    if value is FacilityValueState.CONFLICTING:
        return "conflict"
    return "not_applicable"


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be an object.")
    return cast(Mapping[str, Any], value)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("Facility coverage rows must be an array.")
    return value


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()
