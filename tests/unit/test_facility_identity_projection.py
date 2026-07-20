from __future__ import annotations

import inspect as python_inspect
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, select

from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAuthenticationRequiredError,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    hosted_ccld_retrieval_jobs,
)
from ccld_complaints.hosted_app.facility_identity_presenter import (
    present_facility_field,
)
from ccld_complaints.hosted_app.facility_identity_projection import (
    PUBLIC_FACILITY_FIELDS,
    FacilityFieldResult,
    FacilityProjectionCandidate,
    FacilityProjectionField,
    FacilityProjectionSourceAvailability,
    FacilitySourceKind,
    FacilityValueContext,
    FacilityValueState,
    load_authorized_facility_identity_projection,
    project_facility_identity,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_DATASET_SLUG,
    FACILITY_REFERENCE_DATASET_URL,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FACILITY_ID = "157806098"
FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
FIXTURE_SCOPE = HostedAccessScope("seeded_corpus", "seeded-ccld-fixture-2026-06-13")
APPROVED_RESOURCE_IDS = (
    "c9df723a-437f-4dcd-be37-ec73ae518bb9",
    "2099c65e-138b-4116-93d3-8b70d82a6f16",
)


def test_matching_observations_reconcile_and_keep_every_provenance() -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
                row_identity="reference-row",
                observed_at="2026-07-18T00:00:00+00:00",
                context=FacilityValueContext.CURRENT_REFERENCE,
                values={FacilityProjectionField.FACILITY_NAME: "Example Home"},
            ),
            _candidate(
                source_kind=FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
                row_identity="complaint-row",
                observed_at="2026-06-01T00:00:00+00:00",
                context=FacilityValueContext.HISTORICAL_COMPLAINT,
                values={FacilityProjectionField.FACILITY_NAME: "  example   home  "},
                canonical_internal_identity="facility-record:internal-17",
            ),
        ),
    )

    result = projection.field(FacilityProjectionField.FACILITY_NAME)
    assert result.display_value == "Example Home"
    assert result.normalized_value == "example home"
    assert result.state is FacilityValueState.POPULATED
    assert result.conflict is False
    assert len(result.alternatives) == 2
    assert {item.context for item in result.alternatives} == {
        FacilityValueContext.CURRENT_REFERENCE,
        FacilityValueContext.HISTORICAL_COMPLAINT,
    }


@pytest.mark.parametrize(
    ("reference_value", "canonical_value", "expected", "expected_context"),
    (
        (
            "",
            "Complaint-time name",
            "Complaint-time name",
            FacilityValueContext.HISTORICAL_COMPLAINT,
        ),
        (
            "Current reference name",
            "",
            "Current reference name",
            FacilityValueContext.CURRENT_REFERENCE,
        ),
    ),
)
def test_blank_never_erases_populated_value(
    reference_value: str,
    canonical_value: str,
    expected: str,
    expected_context: FacilityValueContext,
) -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
                row_identity="reference-row",
                observed_at="2026-07-18T00:00:00+00:00",
                context=FacilityValueContext.CURRENT_REFERENCE,
                values={FacilityProjectionField.FACILITY_NAME: reference_value},
            ),
            _candidate(
                source_kind=FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
                row_identity="complaint-row",
                observed_at="2026-06-01T00:00:00+00:00",
                context=FacilityValueContext.HISTORICAL_COMPLAINT,
                values={FacilityProjectionField.FACILITY_NAME: canonical_value},
            ),
        ),
    )

    result = projection.field(FacilityProjectionField.FACILITY_NAME)
    assert result.display_value == expected
    assert result.context is expected_context
    blank = next(
        item for item in result.alternatives if item.state is FacilityValueState.BLANK
    )
    assert blank.raw_value == ""


def test_conflicting_current_and_historical_values_keep_selected_context_and_originals() -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
                row_identity="current-reference-row",
                observed_at="2026-07-18T00:00:00+00:00",
                context=FacilityValueContext.CURRENT_REFERENCE,
                values={FacilityProjectionField.STATUS: "Licensed"},
            ),
            _candidate(
                source_kind=FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
                row_identity="historical-complaint-row",
                observed_at="2024-04-25T00:00:00+00:00",
                context=FacilityValueContext.HISTORICAL_COMPLAINT,
                values={FacilityProjectionField.STATUS: "Pending"},
            ),
        ),
    )

    result = projection.field(FacilityProjectionField.STATUS)
    assert result.display_value == "Licensed"
    assert result.state is FacilityValueState.CONFLICTING
    assert result.conflict is True
    assert result.context is FacilityValueContext.CURRENT_REFERENCE
    assert {item.raw_value for item in result.alternatives} == {"Licensed", "Pending"}


def test_raw_733_remains_an_unresolved_type_code() -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
                row_identity="complaint-row",
                observed_at="2026-06-01T00:00:00+00:00",
                context=FacilityValueContext.HISTORICAL_COMPLAINT,
                values={FacilityProjectionField.FACILITY_TYPE: "733"},
            ),
        ),
    )

    result = projection.field(FacilityProjectionField.FACILITY_TYPE)
    assert result.display_value == "733"
    assert result.normalized_value == "733"
    assert result.state is FacilityValueState.UNRESOLVED_RAW_CODE
    assert result.conflict is False
    assert present_facility_field(result).text == "Source code 733 — label not verified"


@pytest.mark.parametrize(
    ("state", "expected"),
    (
        (FacilityValueState.BLANK, "Blank in source"),
        (FacilityValueState.ABSENT, "Not found in source"),
        (FacilityValueState.UNAVAILABLE, "Source unavailable"),
        (FacilityValueState.CONFLICTING, "Conflicting source values"),
        (FacilityValueState.INTERNAL_ONLY, "Internal only"),
        (FacilityValueState.INVALID, "Invalid source value"),
    ),
)
def test_presenter_uses_one_approved_phrase_for_each_empty_state(
    state: FacilityValueState,
    expected: str,
) -> None:
    presentation = present_facility_field(
        FacilityFieldResult(
            field=FacilityProjectionField.FACILITY_NAME,
            display_value=None,
            normalized_value=None,
            state=state,
            source_identity=None,
            observed_at=None,
            conflict=state is FacilityValueState.CONFLICTING,
            alternatives=(),
            context=None,
        )
    )

    assert presentation.text == expected


def test_multiple_same_id_rows_are_insertion_order_independent_and_never_first_row_wins() -> None:
    candidates = (
        _candidate(
            source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
            row_identity="reference-a",
            observed_at="2026-07-18T00:00:00+00:00",
            context=FacilityValueContext.CURRENT_REFERENCE,
            values={FacilityProjectionField.COUNTY: "Alameda"},
        ),
        _candidate(
            source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
            row_identity="reference-b",
            observed_at="2026-07-18T00:00:00+00:00",
            context=FacilityValueContext.CURRENT_REFERENCE,
            values={FacilityProjectionField.COUNTY: "Contra Costa"},
        ),
    )

    forward = project_facility_identity(FACILITY_ID, candidates)
    reverse = project_facility_identity(FACILITY_ID, tuple(reversed(candidates)))

    assert forward == reverse
    result = forward.field(FacilityProjectionField.COUNTY)
    assert result.state is FacilityValueState.CONFLICTING
    assert result.display_value is None
    assert result.source_identity is None
    assert {item.raw_value for item in result.alternatives} == {
        "Alameda",
        "Contra Costa",
    }


def test_public_internal_source_row_and_snapshot_identities_stay_separate() -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
                row_identity="source-row:facility:17",
                snapshot_identity="snapshot:2026-07-18",
                observed_at="2026-07-18T00:00:00+00:00",
                context=FacilityValueContext.HISTORICAL_COMPLAINT,
                values={FacilityProjectionField.FACILITY_NAME: "Example Home"},
                canonical_internal_identity="canonical-db-key:987",
            ),
        ),
    )

    identity = projection.field(FacilityProjectionField.PUBLIC_FACILITY_ID)
    internal = projection.canonical_internal_identity
    assert projection.public_facility_id == FACILITY_ID
    assert identity.display_value == FACILITY_ID
    assert identity.source_identity is not None
    assert identity.source_identity.source_row_identity == "source-row:facility:17"
    assert identity.source_identity.snapshot_identity == "snapshot:2026-07-18"
    assert internal.display_value is None
    assert internal.normalized_value == "canonical-db-key:987"
    assert internal.state is FacilityValueState.INTERNAL_ONLY
    assert FACILITY_ID != internal.normalized_value


def test_projection_has_no_query_carried_name_authority() -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
                row_identity="reference-row",
                observed_at="2026-07-18T00:00:00+00:00",
                context=FacilityValueContext.CURRENT_REFERENCE,
                values={FacilityProjectionField.FACILITY_NAME: "Resolved source name"},
            ),
        ),
    )

    assert "query_name" not in python_inspect.signature(project_facility_identity).parameters
    assert (
        projection.field(FacilityProjectionField.FACILITY_NAME).display_value
        == "Resolved source name"
    )


def test_blank_absent_unavailable_and_internal_states_are_semantic() -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
                row_identity="reference-row",
                observed_at="2026-07-18T00:00:00+00:00",
                context=FacilityValueContext.CURRENT_REFERENCE,
                values={FacilityProjectionField.CITY: ""},
            ),
        ),
        availability=FacilityProjectionSourceAvailability(
            program_reference=True,
            complaint_linked_facility=False,
        ),
    )

    assert projection.field(FacilityProjectionField.CITY).state is FacilityValueState.BLANK
    assert (
        projection.field(FacilityProjectionField.ADMINISTRATOR).state
        is FacilityValueState.UNAVAILABLE
    )
    assert (
        project_facility_identity(FACILITY_ID, ()).field(
            FacilityProjectionField.ADMINISTRATOR
        ).state
        is FacilityValueState.ABSENT
    )
    assert (
        projection.canonical_internal_identity.state
        is FacilityValueState.INTERNAL_ONLY
    )
    assert set(projection.fields) == set(PUBLIC_FACILITY_FIELDS)


def test_production_service_excludes_synthetic_candidates_as_unavailable() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_projection_tables(engine)
    with engine.begin() as connection:
        import_seeded_corpus_artifact(connection, load_seeded_corpus_artifact(FIXTURE))
        projection = load_authorized_facility_identity_projection(
            connection,
            _actor(),
            scope=FIXTURE_SCOPE,
            public_facility_id=FACILITY_ID,
            import_batch_id=FIXTURE_SCOPE.scope_id,
        )

    name = projection.field(FacilityProjectionField.FACILITY_NAME)
    assert name.display_value is None
    assert name.state is FacilityValueState.UNAVAILABLE
    assert name.alternatives == ()
    assert FacilitySourceKind.COMPLAINT_LINKED_FACILITY in name.unavailable_sources
    assert projection.ineligible_candidate_excluded is True


def test_eligible_reference_remains_visible_when_complaint_candidate_is_unsafe() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_projection_tables(engine)
    with engine.begin() as connection:
        import_seeded_corpus_artifact(connection, load_seeded_corpus_artifact(FIXTURE))
        _insert_reference(connection)

        projection = load_authorized_facility_identity_projection(
            connection,
            _actor(),
            scope=FIXTURE_SCOPE,
            public_facility_id=FACILITY_ID,
            import_batch_id=FIXTURE_SCOPE.scope_id,
        )

    name = projection.field(FacilityProjectionField.FACILITY_NAME)
    assert name.display_value == "Current program reference name"
    assert name.state is FacilityValueState.POPULATED
    assert FacilitySourceKind.COMPLAINT_LINKED_FACILITY in name.unavailable_sources
    assert projection.ineligible_candidate_excluded is False


def test_service_requires_an_authorized_actor_before_candidate_reads() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_projection_tables(engine)
    with engine.begin() as connection:
        with pytest.raises(HostedAuthenticationRequiredError):
            load_authorized_facility_identity_projection(
                connection,
                None,
                scope=FIXTURE_SCOPE,
                public_facility_id=FACILITY_ID,
                import_batch_id=FIXTURE_SCOPE.scope_id,
            )


def test_authorized_service_is_select_only_and_preserves_reviewer_created_state() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_projection_tables(engine)
    with engine.begin() as connection:
        import_seeded_corpus_artifact(connection, load_seeded_corpus_artifact(FIXTURE))
        facility_source_record_key = connection.execute(
            select(hosted_source_derived_records.c.source_record_key).where(
                hosted_source_derived_records.c.entity_type == "facility"
            )
        ).scalar_one()
        connection.execute(
            hosted_reviewer_created_state.insert().values(
                reviewer_state_id="reviewer-state-projection-read-only",
                source_record_key=facility_source_record_key,
                scope_type=FIXTURE_SCOPE.scope_type,
                scope_id=FIXTURE_SCOPE.scope_id,
                state_kind="review_item_state_scaffold",
                state_payload={"payload_kind": "reviewer_status_scaffold", "status": "in_review"},
                created_at="2026-07-19T00:00:00+00:00",
                created_by_provider_subject="projection-test-reviewer",
                created_by_provider_issuer="managed-test-provider",
                created_by_display_name="Projection Test Reviewer",
                created_by_actor_category="tester",
                authorization_permission="reviewer_state_write",
            )
        )
        _insert_reference(connection)
        before = _reviewer_state_rows(connection)

        projection = load_authorized_facility_identity_projection(
            connection,
            _actor(),
            scope=FIXTURE_SCOPE,
            public_facility_id=FACILITY_ID,
            import_batch_id=FIXTURE_SCOPE.scope_id,
            allow_test_candidates=True,
        )

        after = _reviewer_state_rows(connection)

    assert before == after
    assert (
        projection.field(FacilityProjectionField.FACILITY_NAME).display_value
        == "Current program reference name"
    )
    capacity = projection.field(FacilityProjectionField.CAPACITY)
    assert capacity.display_value == 48
    assert isinstance(capacity.display_value, int)
    assert projection.canonical_internal_identity.display_value is None


def _candidate(
    *,
    source_kind: FacilitySourceKind,
    row_identity: str,
    observed_at: str,
    context: FacilityValueContext,
    values: Mapping[FacilityProjectionField, Any],
    snapshot_identity: str = "snapshot:one",
    canonical_internal_identity: str | None = None,
) -> FacilityProjectionCandidate:
    candidate_values = {
        FacilityProjectionField.PUBLIC_FACILITY_ID: FACILITY_ID,
        **values,
    }
    return FacilityProjectionCandidate(
        source_kind=source_kind,
        source_row_identity=row_identity,
        snapshot_identity=snapshot_identity,
        observed_at=observed_at,
        context=context,
        values=candidate_values,
        present_fields=frozenset(candidate_values),
        source_fields={field: f"source.{field.value}" for field in candidate_values},
        canonical_internal_identity=canonical_internal_identity,
    )


def _actor() -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="projection-test-reviewer",
        provider_issuer="managed-test-provider",
        display_name="Projection Test Reviewer",
        email="reviewer@example.invalid",
        actor_category="tester",
        account_status="active",
        roles=("read_only_tester",),
        scopes=(FIXTURE_SCOPE,),
    )


def _create_projection_tables(engine: Any) -> None:
    hosted_ccld_retrieval_jobs.metadata.create_all(engine)
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)


def _insert_reference(connection: Any) -> None:
    connection.execute(
        hosted_facility_reference_records.insert().values(
            source_resource_id=APPROVED_RESOURCE_IDS[0],
            facility_number=FACILITY_ID,
            facility_name="Current program reference name",
            facility_type="Children's Residential Facility",
            program_type="Residential",
            client_served=None,
            licensee_name="Reference licensee",
            facility_administrator=None,
            telephone="555-0100",
            address="100 Current Way",
            city="Sacramento",
            state="CA",
            zip="95814",
            county="Sacramento",
            regional_office="Regional Office",
            capacity=48,
            status="Licensed",
            license_first_date=None,
            closed_date=None,
            all_visit_dates=None,
            inspection_visit_dates=None,
            other_visit_dates=None,
            snapshot_date="2026-07-18",
            source_resource_name="24-Hour Residential Care for Children",
            source_dataset_slug=FACILITY_REFERENCE_DATASET_SLUG,
            source_dataset_url=FACILITY_REFERENCE_DATASET_URL,
            source_accessed_at="2026-07-18T00:00:00+00:00",
            source_file_name="24HourResidentialCareforChildren07182026.csv",
            original_row_json={
                "Facility Number": FACILITY_ID,
                "Facility Name": "Current program reference name",
            },
        )
    )


def _reviewer_state_rows(connection: Any) -> tuple[dict[str, Any], ...]:
    return tuple(
        dict(row)
        for row in connection.execute(
            select(hosted_reviewer_created_state).order_by(
                hosted_reviewer_created_state.c.reviewer_state_id
            )
        ).mappings()
    )
