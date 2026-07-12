from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import HostedAccessScope
from ccld_complaints.hosted_app.ccld_retrieval_jobs import hosted_ccld_retrieval_jobs
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    REVIEWER_UI_SERIOUS_TOPICS_PATH,
    _serious_topic_items,
    reviewer_ui_context_for_connection,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)

TEST_SCOPE = LOCAL_REVIEWER_UI_SCOPE
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "issue-417-other-corpus")
HASH_1 = "a" * 64
HASH_2 = "b" * 64


def test_serious_topics_worklist_lists_deterministic_categories_without_narrative() -> None:
    with _connection() as connection:
        for index, (category, _expected_topic) in enumerate(
            (
                ("Abuse or mistreatment", "Mistreatment-topic"),
                ("Neglect", "Care-omission topic"),
                ("Inadequate supervision", "Supervision topic"),
                ("Medication or medical care", "Medication/medical-care topic"),
                ("Runaway or AWOL", "Runaway/AWOL topic"),
                ("Staff conduct", "Staff-conduct topic"),
            ),
            start=1,
        ):
            _insert_bundle(
                connection,
                control_number=f"32-CR-2024010{index}000000",
                facility_number=f"41700000{index}",
                facility_name=f"Issue 417 Facility {index}",
                county="Kern",
                finding="Unsubstantiated",
                complaint_received_date=f"2024-01-0{index}",
                allegation_category=category,
                allegation_text=f"DO NOT SHOW deterministic narrative {index}",
            )
        before_counts = _counts(connection)

        status, content_type, body = route_response(
            REVIEWER_UI_SERIOUS_TOPICS_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        after_counts = _counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts == {"import_batches": 1, "source_records": 24}
    assert "Serious-topic complaint worklist" in html
    assert "Source category" in html
    assert "source-derived allegation_category" in html
    for expected in (
        "Mistreatment-topic",
        "Care-omission topic",
        "Supervision topic",
        "Medication/medical-care topic",
        "Runaway/AWOL topic",
        "Staff-conduct topic",
        "Abuse or mistreatment",
        "Neglect",
        "Inadequate supervision",
        "Medication or medical care",
        "Runaway or AWOL",
        "Staff conduct",
        "01/01/2024",
        "Open complaint review workspace",
        "Open original public report for 32-CR-20240101000000",
    ):
        assert expected in html
    assert "DO NOT SHOW deterministic narrative" not in html
    assert "raw_path" not in html
    assert "provider_subject" not in html
    assert "token" not in html.casefold()
    assert "legal conclusion" in html
    assert "facility-wide conclusions" in html


def test_serious_topics_keyword_cues_require_missing_or_unknown_category() -> None:
    with _connection() as connection:
        _insert_bundle(
            connection,
            control_number="32-CR-20240201000000",
            facility_number="417100001",
            allegation_category=None,
            allegation_text="DO NOT SHOW injury narrative for cue.",
        )
        _insert_bundle(
            connection,
            control_number="32-CR-20240202000000",
            facility_number="417100002",
            allegation_category="Unknown",
            allegation_text="DO NOT SHOW restraint narrative for cue.",
        )
        _insert_bundle(
            connection,
            control_number="32-CR-20240203000000",
            facility_number="417100003",
            allegation_category="Documentation",
            allegation_text="DO NOT SHOW injury narrative with structured non-serious category.",
        )
        _insert_bundle(
            connection,
            control_number="32-CR-20240204000000",
            facility_number="417100004",
            allegation_category="Unknown",
            allegation_text="DO NOT SHOW substance abuse policy false positive.",
        )
        _insert_bundle(
            connection,
            control_number="32-CR-20240205000000",
            facility_number="417100005",
            allegation_category="Unknown",
            allegation_text="DO NOT SHOW hurt synonym false negative.",
        )

        status, _content_type, body = route_response(
            f"{REVIEWER_UI_SERIOUS_TOPICS_PATH}?match_basis=keyword-cue",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert "Showing 1-2 of 2 matching serious-topic complaint record(s); 2 total qualifying" in html
    assert "Possible serious-topic cue" in html
    assert "Keyword-assisted cue" in html
    assert "keyword-assisted allegation_text: injury" in html
    assert "keyword-assisted allegation_text: restraint" in html
    assert "32-CR-20240201000000" in html
    assert "32-CR-20240202000000" in html
    assert "32-CR-20240203000000" not in html
    assert "32-CR-20240204000000" not in html
    assert "32-CR-20240205000000" not in html
    assert "DO NOT SHOW" not in html


def test_serious_topics_structured_category_takes_precedence_over_keyword_text() -> None:
    with _connection() as connection:
        _insert_bundle(
            connection,
            control_number="32-CR-20240301000000",
            facility_number="417200001",
            finding="Substantiated",
            allegation_category="Neglect",
            allegation_text="DO NOT SHOW injury text under structured category.",
        )

        source_status, _source_content_type, source_body = route_response(
            REVIEWER_UI_SERIOUS_TOPICS_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        cue_status, _cue_content_type, cue_body = route_response(
            f"{REVIEWER_UI_SERIOUS_TOPICS_PATH}?match_basis=keyword-cue",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    source_html = source_body.decode("utf-8")
    cue_html = cue_body.decode("utf-8")

    assert source_status == 200
    assert "Care-omission topic" in source_html
    assert "Source category" in source_html
    assert "keyword-assisted allegation_text" not in source_html
    assert "injury text" not in source_html
    assert cue_status == 200
    assert "No serious-topic complaint records matched." in cue_html


def test_serious_topics_combined_filters_links_and_dates() -> None:
    with _connection() as connection:
        _insert_bundle(
            connection,
            control_number="32-CR-20240401000000",
            facility_number="417300001",
            facility_name="Filtered Facility",
            facility_type="Foster Family Agency",
            county="Kern",
            finding="Substantiated",
            complaint_received_date="2024-04-01",
            allegation_category="Inadequate supervision",
            allegation_text="DO NOT SHOW matched supervision narrative.",
        )
        _insert_bundle(
            connection,
            control_number="32-CR-20240501000000",
            facility_number="417300002",
            facility_name="Other Facility",
            facility_type="Temporary Shelter",
            county="Sacramento",
            finding="Unsubstantiated",
            complaint_received_date="2024-05-01",
            allegation_category="Inadequate supervision",
            allegation_text="DO NOT SHOW other supervision narrative.",
        )

        status, _content_type, body = route_response(
            (
                f"{REVIEWER_UI_SERIOUS_TOPICS_PATH}?"
                "topic=Supervision+topic&finding=Substantiated&facility=Filtered"
                "&geography=Kern&start_date=2024-04-01&end_date=2024-04-30"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert "Showing 1-1 of 1 matching serious-topic complaint record(s); 2 total qualifying" in html
    assert "Filtered Facility" in html
    assert "417300001" in html
    assert "04/01/2024" in html
    assert "Substantiated" in html
    assert "Open original public report for 32-CR-20240401000000" in html
    assert "source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20240401000000" in html
    assert "Other Facility" not in html
    assert "DO NOT SHOW" not in html


def test_serious_topics_deduplicates_multiple_matching_allegations_for_one_complaint() -> None:
    with _connection() as connection:
        _insert_bundle(
            connection,
            control_number="32-CR-20240601000000",
            facility_number="417400001",
            allegation_category="Staff conduct",
            allegation_text="DO NOT SHOW first staff conduct narrative.",
            extra_allegations=(
                {
                    "allegation_category": "Staff conduct",
                    "allegation_text": "DO NOT SHOW second staff conduct narrative.",
                },
            ),
        )

        status, _content_type, body = route_response(
            REVIEWER_UI_SERIOUS_TOPICS_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert "Showing 1-1 of 1 matching serious-topic complaint record(s); 1 total qualifying" in html
    assert html.count("Open complaint review workspace") == 1
    assert "Staff-conduct topic" in html
    assert "DO NOT SHOW" not in html


def test_serious_topic_item_helper_deduplicates_stable_complaint_identity() -> None:
    complaint = _payload_record(
        entity_type="complaint",
        stable_id="ccld:complaint:duplicate",
        source_document_id="doc-1",
        facility_id="facility-1",
        original_values={
            "complaint_id": "ccld:complaint:duplicate",
            "complaint_control_number": "32-CR-20240701000000",
            "complaint_received_date": "2024-07-01",
            "finding": "Unsubstantiated",
        },
    )
    allegation = _payload_record(
        entity_type="allegation",
        stable_id="ccld:allegation:duplicate:1",
        source_document_id="doc-1",
        facility_id="facility-1",
        original_values={
            "allegation_id": "ccld:allegation:duplicate:1",
            "complaint_id": "ccld:complaint:duplicate",
            "allegation_category": "Runaway or AWOL",
            "allegation_text": "DO NOT SHOW runaway narrative.",
        },
    )
    records = [complaint, complaint, allegation]
    complaint_payloads = [
        {"source_record": _review_source_record_payload(record)}
        for record in (complaint, complaint)
    ]
    items = _serious_topic_items(complaint_payloads, _source_indexes_for_payload(records))

    assert len(items) == 1
    assert items[0]["category_labels"] == "Runaway/AWOL topic"


def test_serious_topics_authorization_scope_and_no_mutation() -> None:
    with _connection() as connection:
        _insert_bundle(
            connection,
            control_number="32-CR-20240801000000",
            facility_number="417500001",
            allegation_category="Abuse or mistreatment",
            allegation_text="DO NOT SHOW authorized narrative.",
        )
        _insert_bundle(
            connection,
            scope=OTHER_SCOPE,
            import_batch_id=OTHER_SCOPE.scope_id,
            control_number="32-CR-20240802000000",
            facility_number="417500002",
            allegation_category="Staff conduct",
            allegation_text="DO NOT SHOW unauthorized narrative.",
        )
        before_counts = _counts(connection)

        authorized_status, _authorized_content_type, authorized_body = route_response(
            REVIEWER_UI_SERIOUS_TOPICS_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        (
            unauthenticated_status,
            _unauthenticated_content_type,
            unauthenticated_body,
        ) = route_response(
            REVIEWER_UI_SERIOUS_TOPICS_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection, actor=None),
        )
        after_counts = _counts(connection)

    authorized_html = authorized_body.decode("utf-8")
    unauthenticated_html = unauthenticated_body.decode("utf-8")

    assert authorized_status == 200
    assert "32-CR-20240801000000" in authorized_html
    assert "32-CR-20240802000000" not in authorized_html
    assert "DO NOT SHOW" not in authorized_html
    assert unauthenticated_status == 401
    assert "requires an authenticated actor" in unauthenticated_html
    assert before_counts == after_counts == {"import_batches": 2, "source_records": 8}


def test_serious_topics_empty_state_is_cautious_and_accessible() -> None:
    with _connection() as connection:
        _insert_bundle(
            connection,
            control_number="32-CR-20240901000000",
            facility_number="417600001",
            allegation_category="Documentation",
            allegation_text="DO NOT SHOW documentation narrative.",
        )

        status, _content_type, body = route_response(
            REVIEWER_UI_SERIOUS_TOPICS_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert "No serious-topic complaint records matched." in html
    assert "No loaded authorized complaint records matched" in html
    assert "Clear filters" in html
    assert '<label for="serious-topics-topic">Review theme</label>' in html
    assert '<label for="serious-topics-match-basis">Match basis</label>' in html
    assert "no complaints found" not in html.casefold()
    assert "verified abuse" not in html.casefold()
    assert "DO NOT SHOW" not in html


def _connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    connection.execute(
        hosted_import_batches.insert().values(
            import_batch_id=TEST_SCOPE.scope_id,
            imported_at="2026-07-12T00:00:00+00:00",
            source_artifact_identity="issue-417-test-artifact",
            source_pipeline_version="issue-417-test",
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts={},
            warnings=[],
            errors=[],
        )
    )
    return connection


def _insert_batch_if_needed(
    connection: Connection,
    *,
    import_batch_id: str,
) -> None:
    exists = connection.execute(
        select(hosted_import_batches.c.import_batch_id).where(
            hosted_import_batches.c.import_batch_id == import_batch_id
        )
    ).first()
    if exists is not None:
        return
    connection.execute(
        hosted_import_batches.insert().values(
            import_batch_id=import_batch_id,
            imported_at="2026-07-12T00:00:00+00:00",
            source_artifact_identity=f"{import_batch_id}-artifact",
            source_pipeline_version="issue-417-test",
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts={},
            warnings=[],
            errors=[],
        )
    )


def _insert_bundle(
    connection: Connection,
    *,
    control_number: str,
    facility_number: str,
    facility_name: str = "Issue 417 Facility",
    facility_type: str = "Children's Center",
    county: str = "Kern",
    finding: str = "Unsubstantiated",
    complaint_received_date: str = "2024-01-01",
    allegation_category: str | None,
    allegation_text: str,
    scope: HostedAccessScope = TEST_SCOPE,
    import_batch_id: str | None = None,
    extra_allegations: tuple[Mapping[str, str | None], ...] = (),
) -> None:
    batch_id = import_batch_id or scope.scope_id
    _insert_batch_if_needed(connection, import_batch_id=batch_id)
    facility_id = f"ccld:facility:{facility_number}"
    document_id = f"ccld:document:{facility_number}:{control_number}"
    complaint_id = f"ccld:complaint:{control_number}"
    source_url = (
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        f"?facNum={facility_number}&inx={control_number[-2:]}"
    )
    traceability = {
        "source_document_id": document_id,
        "source_url": source_url,
        "raw_sha256": HASH_1,
        "raw_path": "data/raw/ccld/issue-417-private-path.html",
        "connector_name": "ccld_facility_reports",
        "connector_version": "issue-417-test",
        "retrieved_at": "2026-07-12T00:00:00+00:00",
    }
    _insert_source_row(
        connection,
        import_batch_id=batch_id,
        entity_type="facility",
        stable_source_id=facility_id,
        source_document_id=document_id,
        facility_id=facility_id,
        source_url=source_url,
        original_values={
            "facility_id": facility_id,
            "external_facility_number": facility_number,
            "facility_name": facility_name,
            "facility_type": facility_type,
            "county": county,
        },
        traceability=traceability,
    )
    _insert_source_row(
        connection,
        import_batch_id=batch_id,
        entity_type="source_document",
        stable_source_id=document_id,
        source_document_id=document_id,
        facility_id=facility_id,
        source_url=source_url,
        original_values={
            "document_id": document_id,
            "source_url": source_url,
            "document_type": "complaint_investigation_report",
            "report_index": control_number[-2:],
        },
        traceability=traceability,
    )
    _insert_source_row(
        connection,
        import_batch_id=batch_id,
        entity_type="complaint",
        stable_source_id=complaint_id,
        source_document_id=document_id,
        facility_id=facility_id,
        source_url=source_url,
        original_values={
            "complaint_id": complaint_id,
            "facility_id": facility_id,
            "document_id": document_id,
            "complaint_control_number": control_number,
            "complaint_received_date": complaint_received_date,
            "finding": finding,
        },
        traceability=traceability,
    )
    allegation_values = (
        {
            "allegation_category": allegation_category,
            "allegation_text": allegation_text,
        },
        *extra_allegations,
    )
    for index, values in enumerate(allegation_values, start=1):
        allegation_id = f"ccld:allegation:{control_number}:{index}"
        _insert_source_row(
            connection,
            import_batch_id=batch_id,
            entity_type="allegation",
            stable_source_id=allegation_id,
            source_document_id=document_id,
            facility_id=facility_id,
            source_url=source_url,
            original_values={
                "allegation_id": allegation_id,
                "complaint_id": complaint_id,
                "allegation_category": values.get("allegation_category"),
                "allegation_text": values.get("allegation_text"),
                "finding": finding,
            },
            traceability=traceability,
        )


def _insert_source_row(
    connection: Connection,
    *,
    import_batch_id: str,
    entity_type: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    source_url: str,
    original_values: Mapping[str, Any],
    traceability: Mapping[str, Any],
) -> None:
    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key=f"{entity_type}:{stable_source_id}",
            entity_type=entity_type,
            stable_source_id=stable_source_id,
            import_batch_id=import_batch_id,
            source_document_id=source_document_id,
            facility_id=facility_id,
            source_url=source_url,
            raw_sha256=HASH_1,
            raw_path="data/raw/ccld/issue-417-private-path.html",
            connector_name="ccld_facility_reports",
            connector_version="issue-417-test",
            retrieved_at="2026-07-12T00:00:00+00:00",
            original_values=dict(original_values),
            source_traceability=dict(traceability),
        )
    )


def _payload_record(
    *,
    entity_type: str,
    stable_id: str,
    source_document_id: str,
    facility_id: str,
    original_values: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_record_key": f"{entity_type}:{stable_id}",
        "entity_type": entity_type,
        "stable_source_id": stable_id,
        "source_document_id": source_document_id,
        "facility_id": facility_id,
        "source_url": "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=417&inx=1",
        "raw_sha256": HASH_2,
        "raw_path": "data/raw/ccld/issue-417-private-path.html",
        "connector_name": "ccld_facility_reports",
        "connector_version": "issue-417-test",
        "retrieved_at": "2026-07-12T00:00:00+00:00",
        "original_values": dict(original_values),
        "source_traceability": {},
        "import_batch": {"import_batch_id": TEST_SCOPE.scope_id},
    }


def _review_source_record_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "identity": {
            "source_record_key": record["source_record_key"],
            "entity_type": record["entity_type"],
            "stable_source_id": record["stable_source_id"],
            "facility_id": record["facility_id"],
        },
        "source_document": {
            "source_document_id": record["source_document_id"],
            "source_url": record["source_url"],
            "raw_sha256": record["raw_sha256"],
            "raw_path": record["raw_path"],
            "connector_name": record["connector_name"],
            "connector_version": record["connector_version"],
            "retrieved_at": record["retrieved_at"],
        },
        "original_values": record["original_values"],
        "source_traceability": record["source_traceability"],
        "import_batch": record["import_batch"],
    }


def _source_indexes_for_payload(records: list[Mapping[str, Any]]) -> Any:
    from ccld_complaints.hosted_app.reviewer_ui import _source_record_indexes

    return _source_record_indexes(list(records))


def _counts(connection: Connection) -> dict[str, int]:
    return {
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "source_records": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
    }


@pytest.fixture(autouse=True)
def _assert_retrieval_table_available() -> None:
    assert hosted_ccld_retrieval_jobs.name == "hosted_ccld_retrieval_jobs"
