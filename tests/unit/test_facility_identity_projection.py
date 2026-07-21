from __future__ import annotations

import inspect as python_inspect
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, select

from ccld_complaints.connectors.arcgis_ccl_facilities.contract import (
    ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
    LIVE_QUERY_SCOPE,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import (
    OBSERVATION_KIND as TRANSPARENCY_OBSERVATION_KIND,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import (
    SNAPSHOT_SCOPE as TRANSPARENCY_SNAPSHOT_SCOPE,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import (
    SOURCE_FAMILY_ID as TRANSPARENCY_SOURCE_FAMILY_ID,
)
from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
    transparency_rows,
)
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
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    source_snapshot_metadata,
    source_snapshot_pointers,
    source_snapshot_rows,
    source_snapshots,
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
                source_kind=FacilitySourceKind.TRANSPARENCY_API_CURRENT,
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
                source_kind=FacilitySourceKind.TRANSPARENCY_API_CURRENT,
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
                source_kind=FacilitySourceKind.TRANSPARENCY_API_CURRENT,
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


def test_status_closed_date_contact_and_administrator_remain_distinct_fields() -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.TRANSPARENCY_API_CURRENT,
                row_identity="current-reference-row",
                observed_at="2026-07-21T00:00:00+00:00",
                context=FacilityValueContext.CURRENT_REFERENCE,
                values={
                    FacilityProjectionField.STATUS: "Licensed",
                    FacilityProjectionField.CLOSED_DATE: "2024-05-01",
                    FacilityProjectionField.CONTACT: "Source contact",
                    FacilityProjectionField.ADMINISTRATOR: "Facility administrator",
                },
            ),
        ),
    )

    assert projection.field(FacilityProjectionField.STATUS).display_value == "Licensed"
    assert (
        projection.field(FacilityProjectionField.CLOSED_DATE).display_value
        == "2024-05-01"
    )
    assert (
        projection.field(FacilityProjectionField.CONTACT).display_value
        == "Source contact"
    )
    assert (
        projection.field(FacilityProjectionField.ADMINISTRATOR).display_value
        == "Facility administrator"
    )


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
            source_kind=FacilitySourceKind.TRANSPARENCY_API_CURRENT,
            row_identity="reference-a",
            observed_at="2026-07-18T00:00:00+00:00",
            context=FacilityValueContext.CURRENT_REFERENCE,
            values={FacilityProjectionField.COUNTY: "Alameda"},
        ),
        _candidate(
            source_kind=FacilitySourceKind.TRANSPARENCY_API_CURRENT,
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
                source_kind=FacilitySourceKind.TRANSPARENCY_API_CURRENT,
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
                source_kind=FacilitySourceKind.TRANSPARENCY_API_CURRENT,
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


def test_extraction_failed_remains_distinct_from_invalid_and_unavailable() -> None:
    projection = project_facility_identity(
        FACILITY_ID,
        (
            _candidate(
                source_kind=FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
                row_identity="complaint-row",
                observed_at="2026-06-01T00:00:00+00:00",
                context=FacilityValueContext.HISTORICAL_COMPLAINT,
                values={FacilityProjectionField.ADMINISTRATOR: None},
                semantic_states={
                    FacilityProjectionField.ADMINISTRATOR: (
                        FacilityValueState.EXTRACTION_FAILED
                    )
                },
            ),
        ),
    )

    result = projection.field(FacilityProjectionField.ADMINISTRATOR)
    assert result.state is FacilityValueState.EXTRACTION_FAILED
    assert present_facility_field(result).text == "Source extraction failed"


def test_active_transparency_snapshot_is_primary_and_preserves_leading_zero_id() -> None:
    facility_id = "001234567"
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_projection_tables(engine)
    with engine.begin() as connection:
        _insert_reference(
            connection,
            facility_id=facility_id,
            facility_name="Historical CKAN name",
        )
        _insert_transparency_snapshot(
            connection,
            snapshot_id="transparency-active-leading-zero",
            facility_id=facility_id,
            recorded_at="2026-07-21T10:00:00+00:00",
            observations={
                "facility_name": _observation("Current Transparency name"),
                "facility_type": _observation("Child Care Center"),
                "bulk_status": _observation("Licensed"),
            },
        )

        projection = load_authorized_facility_identity_projection(
            connection,
            _actor(),
            scope=FIXTURE_SCOPE,
            public_facility_id=facility_id,
        )

    name = projection.field(FacilityProjectionField.FACILITY_NAME)
    assert projection.public_facility_id == facility_id
    assert projection.field(FacilityProjectionField.PUBLIC_FACILITY_ID).display_value == facility_id
    assert name.display_value == "Current Transparency name"
    assert name.context is FacilityValueContext.CURRENT_REFERENCE
    assert name.source_identity is not None
    assert (
        name.source_identity.source_kind
        is FacilitySourceKind.TRANSPARENCY_API_CURRENT
    )
    assert {item.raw_value for item in name.alternatives} == {
        "Current Transparency name",
        "Historical CKAN name",
    }


def test_prior_accepted_address_survives_active_placeholder_with_exact_provenance() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_projection_tables(engine)
    with engine.begin() as connection:
        _insert_transparency_snapshot(
            connection,
            snapshot_id="transparency-prior",
            facility_id=FACILITY_ID,
            recorded_at="2026-07-20T10:00:00+00:00",
            observations={
                "facility_name": _observation("Current name"),
                "facility_address": _observation("100 Preserved Way"),
                "facility_telephone_number": _observation("555-0100"),
            },
            promote=False,
        )
        _insert_transparency_snapshot(
            connection,
            snapshot_id="transparency-active-placeholder",
            facility_id=FACILITY_ID,
            recorded_at="2026-07-21T10:00:00+00:00",
            observations={
                "facility_name": _observation("Current name"),
                "facility_address": _observation("Unavailable", state="placeholder"),
                "facility_telephone_number": _observation("See FAQs", state="placeholder"),
            },
            prior_snapshot_id="transparency-prior",
        )

        projection = load_authorized_facility_identity_projection(
            connection,
            _actor(),
            scope=FIXTURE_SCOPE,
            public_facility_id=FACILITY_ID,
        )

    address = projection.field(FacilityProjectionField.FULL_ADDRESS)
    telephone = projection.field(FacilityProjectionField.TELEPHONE)
    assert address.display_value == "100 Preserved Way"
    assert telephone.display_value == "555-0100"
    assert address.context is FacilityValueContext.HISTORICAL_REFERENCE
    assert address.source_identity is not None
    assert address.source_identity.snapshot_identity == "transparency-prior"
    assert (
        address.source_identity.source_kind
        is FacilitySourceKind.TRANSPARENCY_API_PRIOR_ACCEPTED
    )
    assert FacilityValueState.UNAVAILABLE in {
        item.state for item in address.alternatives
    }


def test_arcgis_is_supplementary_and_ckan_and_complaint_remain_historical() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_projection_tables(engine)
    with engine.begin() as connection:
        _insert_reference(connection, facility_name="Historical CKAN name")
        _insert_transparency_snapshot(
            connection,
            snapshot_id="transparency-active-missing-name",
            facility_id=FACILITY_ID,
            recorded_at="2026-07-21T10:00:00+00:00",
            observations={"facility_name": _observation(None, state="absent")},
        )
        _insert_arcgis_snapshot(
            connection,
            facility_id=FACILITY_ID,
            facility_name="ArcGIS supplementary name",
        )

        projection = load_authorized_facility_identity_projection(
            connection,
            _actor(),
            scope=FIXTURE_SCOPE,
            public_facility_id=FACILITY_ID,
        )

    name = projection.field(FacilityProjectionField.FACILITY_NAME)
    assert name.display_value == "ArcGIS supplementary name"
    assert name.context is FacilityValueContext.SUPPLEMENTARY_REFERENCE
    assert name.source_identity is not None
    assert name.source_identity.source_kind is FacilitySourceKind.ARCGIS_SUPPLEMENT
    assert any(
        item.context is FacilityValueContext.HISTORICAL_REFERENCE
        and item.raw_value == "Historical CKAN name"
        for item in name.alternatives
    )


def test_quarantined_transparency_row_is_not_eligible_facility_truth() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_projection_tables(engine)
    with engine.begin() as connection:
        _insert_reference(connection, facility_name="Historical CKAN name")
        _insert_transparency_snapshot(
            connection,
            snapshot_id="transparency-active-quarantined",
            facility_id=FACILITY_ID,
            recorded_at="2026-07-21T10:00:00+00:00",
            observations={"facility_name": _observation("Quarantined name")},
            is_quarantined=True,
        )

        projection = load_authorized_facility_identity_projection(
            connection,
            _actor(),
            scope=FIXTURE_SCOPE,
            public_facility_id=FACILITY_ID,
        )

    name = projection.field(FacilityProjectionField.FACILITY_NAME)
    assert name.display_value == "Historical CKAN name"
    assert name.context is FacilityValueContext.HISTORICAL_REFERENCE
    assert all(item.raw_value != "Quarantined name" for item in name.alternatives)
    assert FacilitySourceKind.TRANSPARENCY_API_CURRENT in name.unavailable_sources


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
    assert name.display_value == "Historical program reference name"
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
        == "Historical program reference name"
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
    semantic_states: Mapping[FacilityProjectionField, FacilityValueState] | None = None,
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
        semantic_states=semantic_states or {},
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
    source_snapshot_metadata.create_all(engine)


def _insert_reference(
    connection: Any,
    *,
    facility_id: str = FACILITY_ID,
    facility_name: str = "Historical program reference name",
) -> None:
    connection.execute(
        hosted_facility_reference_records.insert().values(
            source_resource_id=APPROVED_RESOURCE_IDS[0],
            facility_number=facility_id,
            facility_name=facility_name,
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
                "Facility Number": facility_id,
                "Facility Name": facility_name,
            },
        )
    )


def _observation(value: object, *, state: str = "populated") -> dict[str, object]:
    return {"state": state, "raw": value, "value": value if state == "populated" else None}


def _snapshot_values(
    *,
    snapshot_id: str,
    source_family_id: str,
    fixture_scope: str,
    observation_kind: str,
    recorded_at: str,
) -> dict[str, object]:
    manifest_sha = f"{snapshot_id}-manifest".ljust(64, "0")[:64]
    raw_sha = f"{snapshot_id}-raw".ljust(64, "0")[:64]
    return {
        "snapshot_id": snapshot_id,
        "source_family_id": source_family_id,
        "fixture_scope": fixture_scope,
        "observation_kind": observation_kind,
        "lifecycle_state": "accepted",
        "manifest_ref": "ignored-evidence/manifest.json",
        "manifest_sha256": manifest_sha,
        "raw_payload_ref": "ignored-evidence/raw",
        "raw_payload_sha256": raw_sha,
        "normalized_content_sha256": "3" * 64,
        "schema_fingerprint": "4" * 64,
        "domain_fingerprint": "5" * 64,
        "row_count": 1,
        "stored_row_count": 1,
        "duplicate_object_id_count": 0,
        "duplicate_facility_number_count": 0,
        "omitted_field_count": 0,
        "invalid_field_count": 0,
        "warning_count": 0,
        "rejection_reason_count": 0,
        "validation_report": {},
        "recorded_at": recorded_at,
        "validated_at": recorded_at,
        "rejected_at": None,
        "accepted_at": recorded_at,
    }


def _insert_transparency_snapshot(
    connection: Any,
    *,
    snapshot_id: str,
    facility_id: str,
    recorded_at: str,
    observations: Mapping[str, object],
    prior_snapshot_id: str | None = None,
    promote: bool = True,
    is_quarantined: bool = False,
) -> None:
    connection.execute(
        source_snapshots.insert().values(
            **_snapshot_values(
                snapshot_id=snapshot_id,
                source_family_id=TRANSPARENCY_SOURCE_FAMILY_ID,
                fixture_scope=TRANSPARENCY_SNAPSHOT_SCOPE,
                observation_kind=TRANSPARENCY_OBSERVATION_KIND,
                recorded_at=recorded_at,
            )
        )
    )
    connection.execute(
        transparency_rows.insert().values(
            snapshot_id=snapshot_id,
            export_id="ChildCareCenters",
            row_ordinal=1,
            facility_number=facility_id,
            raw_row_sha256="6" * 64,
            raw_values=[],
            raw_record={"Facility Number": facility_id},
            normalized_record=dict(observations),
            resolved_current_reference=dict(observations),
            complaint_blocks=[],
            row_fingerprint="7" * 64,
            is_quarantined=is_quarantined,
        )
    )
    if promote:
        connection.execute(
            source_snapshot_pointers.insert().values(
                source_family_id=TRANSPARENCY_SOURCE_FAMILY_ID,
                active_snapshot_id=snapshot_id,
                prior_accepted_snapshot_id=prior_snapshot_id,
                updated_at=recorded_at,
            )
        )


def _insert_arcgis_snapshot(
    connection: Any,
    *,
    facility_id: str,
    facility_name: str,
) -> None:
    snapshot_id = "arcgis-active-supplement"
    recorded_at = "2026-07-21T09:00:00+00:00"
    connection.execute(
        source_snapshots.insert().values(
            **_snapshot_values(
                snapshot_id=snapshot_id,
                source_family_id=ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
                fixture_scope=LIVE_QUERY_SCOPE,
                observation_kind="live_query",
                recorded_at=recorded_at,
            )
        )
    )
    connection.execute(
        source_snapshot_rows.insert().values(
            snapshot_id=snapshot_id,
            source_object_id=1001,
            facility_number=facility_id,
            raw_record={"FAC_NBR": facility_id, "NAME": facility_name},
            normalized_record={
                "facility_number": {
                    "source_field": "FAC_NBR",
                    "state": "populated",
                    "value": facility_id,
                },
                "facility_name_source": {
                    "source_field": "NAME",
                    "state": "populated",
                    "value": facility_name,
                },
                "facility_type_description_source": {
                    "source_field": "FAC_TYPE_DESC",
                    "state": "absent",
                    "value": None,
                },
                "raw_type_code": {
                    "source_field": "TYPE",
                    "state": "absent",
                    "value": None,
                },
            },
            row_fingerprint="8" * 64,
        )
    )
    connection.execute(
        source_snapshot_pointers.insert().values(
            source_family_id=ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
            active_snapshot_id=snapshot_id,
            prior_accepted_snapshot_id=None,
            updated_at=recorded_at,
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
