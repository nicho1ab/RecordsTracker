from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from ccld_complaints.hosted_app import reviewer_ui
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    load_seeded_corpus_artifact,
)

SOURCE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
    "?facNum=157806098&inx=3"
)
LOCAL_VISUAL_EVIDENCE_STATES = (
    (
        "complaint:ccld-complaint-32-CR-20240603151515-rt-src-002-supported-fixture",
        "supported",
        "06/12/2024",
        True,
    ),
    (
        "complaint:ccld-complaint-32-CR-20240610181818-rt-src-002-document-only-fixture",
        "document-only",
        "06/20/2024",
        True,
    ),
    (
        "complaint:ccld:complaint:32-CR-20220407124448",
        "field-partial",
        "04/14/2022",
        True,
    ),
    (
        "complaint:ccld-complaint-32-CR-20240120111111-rt-src-002-source-unavailable-fixture",
        "source-unavailable",
        "02/10/2024",
        False,
    ),
)


def test_local_fixture_exposes_all_visual_states_through_ordinary_detail_routes() -> None:
    context = reviewer_ui.build_local_test_reviewer_ui_context()
    assert context.engine is not None
    source_record_keys = [state[0] for state in LOCAL_VISUAL_EVIDENCE_STATES]
    assert len(source_record_keys) == len(set(source_record_keys))
    assert all(
        key.endswith("-fixture")
        for key in source_record_keys
        if key != "complaint:ccld:complaint:32-CR-20220407124448"
    )
    before_counts = _database_row_counts(context.engine)
    try:
        for source_record_key, state, displayed_date, has_source_action in (
            LOCAL_VISUAL_EVIDENCE_STATES
        ):
            status, content_type, body = reviewer_ui.route_reviewer_ui_response(
                f"{reviewer_ui.REVIEWER_UI_DETAIL_PATH}"
                f"?source_record_key={source_record_key}",
                context,
            )
            html = body.decode("utf-8")

            assert status == 200
            assert content_type == "text/html; charset=utf-8"
            assert f'data-evidence-state="{state}"' in html
            assert displayed_date in html
            assert ("Open original source" in html) is has_source_action

            if state == "supported":
                assert "VISIT DATE: 06/12/2024" in html
                assert "report header" in html
            elif state == "document-only":
                assert "Document-level source only." in html
                assert "verified by" not in html.casefold()
            elif state == "field-partial":
                assert "Field evidence incomplete." in html
                assert "supporting source event sentence is not available" in html
            elif state == "source-unavailable":
                assert "Source document unavailable." in html
                assert '<a class="button button-secondary source-evidence-original"' not in html

        assert _database_row_counts(context.engine) == before_counts
    finally:
        context.engine.dispose()


def test_local_visual_fixture_records_are_absent_from_production_style_context() -> None:
    base_artifact = load_seeded_corpus_artifact(reviewer_ui.LOCAL_REVIEWER_UI_FIXTURE)
    local_artifact = reviewer_ui._with_local_rt_src_002_visual_fixture_records(
        base_artifact
    )
    visual_records = local_artifact.records[-3:]
    assert local_artifact.record_counts["facility"] == base_artifact.record_counts[
        "facility"
    ]
    assert all("facility" not in record for record in visual_records)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    hosted_seeded_import_metadata.create_all(engine)
    assert all(count == 0 for count in _database_row_counts(engine).values())
    connection = engine.connect()
    actor = reviewer_ui.local_test_reviewer_actor(
        scopes=(reviewer_ui.POSTGRES_REVIEWER_UI_SCOPE,)
    )
    context = reviewer_ui.reviewer_ui_context_for_connection(
        connection,
        actor=actor,
        scope=reviewer_ui.POSTGRES_REVIEWER_UI_SCOPE,
    )
    try:
        for source_record_key, _state, _displayed_date, _has_source_action in (
            LOCAL_VISUAL_EVIDENCE_STATES
        ):
            status, _content_type, _body = reviewer_ui.route_reviewer_ui_response(
                f"{reviewer_ui.REVIEWER_UI_DETAIL_PATH}"
                f"?source_record_key={source_record_key}",
                context,
            )

            assert status == 404

        status, _content_type, body = reviewer_ui.route_reviewer_ui_response(
            reviewer_ui.REVIEWER_UI_RECORDS_PATH,
            context,
        )
        html = body.decode("utf-8")
        assert status == 200
        for source_record_key, _state, _date, _source_action in (
            LOCAL_VISUAL_EVIDENCE_STATES
        ):
            assert source_record_key not in html
    finally:
        connection.close()
        engine.dispose()


def test_supported_first_activity_evidence_is_bounded_and_action_separated() -> None:
    html = _render(
        _event(
            event_text=(
                "The investigator interviewed facility clients. "
                "A second sentence is omitted."
            ),
            source_section="investigation findings",
        )
    )

    assert 'data-evidence-state="supported"' in html
    assert "The investigator interviewed facility clients." in html
    assert "A second sentence is omitted." not in html
    assert "investigation findings" in html
    assert "Complaint/report 32-CR-20220407124448" in html
    assert "04/14/2022" in html
    assert 'data-copy-value="04/14/2022"' in html
    assert 'aria-label="Copy First investigation activity date"' in html
    assert '>Copy date</button>' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="first-investigation-evidence"' in html
    assert '>View source evidence</span>' in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert "Open original source" in html
    assert 'id="first-investigation-evidence"' in html
    assert 'role="region"' in html
    assert "hidden" in html


def test_first_activity_event_selection_rejects_unrelated_same_date_events() -> None:
    complaint_values = _source_record()["original_values"]
    unrelated = _event(
        complaint_id="ccld:complaint:other",
        event_text="An unrelated investigation activity occurred.",
    )
    wrong_semantics = _event(
        event_type="investigation_finding",
        event_text="A finding was recorded on the same date.",
    )

    assert (
        reviewer_ui._matching_first_activity_event(
            complaint_values,
            [unrelated, wrong_semantics],
        )
        is None
    )


def test_first_activity_event_selection_is_complete_then_stable() -> None:
    complaint_values = _source_record()["original_values"]
    partial = _event(stable_id="event-0", event_text="", source_section="report header")
    later = _event(stable_id="event-b", event_text="Later stable event.")
    selected = _event(stable_id="event-a", event_text="Selected stable event.")

    result = reviewer_ui._matching_first_activity_event(
        complaint_values,
        [later, partial, selected],
    )

    assert result is selected


@pytest.mark.parametrize(
    ("event_text", "source_section", "missing_message"),
    (
        ("", "investigation findings", "supporting source event sentence is not available"),
        ("Investigation activity occurred.", "", "source section is not available"),
    ),
)
def test_first_activity_field_partial_names_the_missing_element(
    event_text: str,
    source_section: str,
    missing_message: str,
) -> None:
    html = _render(_event(event_text=event_text, source_section=source_section))

    assert 'data-evidence-state="field-partial"' in html
    assert "Field evidence incomplete." in html
    assert missing_message in html.casefold()
    assert "source is complete" not in html.casefold()


def test_first_activity_document_only_does_not_imply_passage_verification() -> None:
    html = _render()

    assert 'data-evidence-state="document-only"' in html
    assert "Document-level source only." in html
    assert "A supporting source event sentence is not available for this date." in html
    assert "The source section is not available for this date." in html
    assert "Open original source" in html
    assert "verified by" not in html.casefold()


def test_first_activity_source_unavailable_has_no_active_original_action() -> None:
    source_record = _source_record(source_url="", raw_path="")
    html = reviewer_ui._render_overview_timeline(
        source_record,
        [_event(event_text="Investigation activity occurred.")],
    )

    assert 'data-evidence-state="source-unavailable"' in html
    assert "Source document unavailable." in html
    assert "A preserved source document is not available from this record." in html
    assert "Open original source" not in html
    assert '<a class="button button-secondary source-evidence-original"' not in html


def test_missing_first_activity_date_has_no_evidence_controls() -> None:
    html = reviewer_ui._render_overview_timeline(
        _source_record(first_activity_date=""),
        [_event(event_text="Investigation activity occurred.")],
    )

    assert "Blank in source" in html
    assert "Copy date" not in html
    assert "View source evidence" not in html
    assert "first-investigation-evidence" not in html


def test_first_activity_evidence_escapes_content_and_hides_traceability_internals() -> None:
    html = _render(
        _event(
            event_text='<script>alert("event")</script>.',
            source_section='<img src=x onerror="alert(1)">',
        )
    )

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html
    for forbidden in (
        "raw SHA-256",
        "raw_path",
        "connector_name",
        "source document ID",
        "database ID",
        "retrieval timestamp",
        "extraction audit",
    ):
        assert forbidden.casefold() not in html.casefold()


def test_first_activity_accessibility_focus_print_and_reflow_contract() -> None:
    html = _render(_event(event_text="Investigation activity occurred."))
    script = reviewer_ui._DETAIL_COPY_SCRIPT

    copy_index = html.index("Copy date")
    toggle_index = html.index("View source evidence")
    evidence_index = html.index('id="first-investigation-evidence"')
    source_index = html.index("Open original source")
    assert copy_index < toggle_index < evidence_index < source_index
    assert '<button class="source-evidence-copy" type="button"' in html
    assert (
        '<button id="first-investigation-evidence-toggle" '
        'class="source-evidence-toggle" type="button"'
        in html
    )
    assert "button.setAttribute('aria-expanded', expanded ? 'true' : 'false')" in script
    assert "region.hidden = !expanded" in script
    assert "button.focus()" in script
    assert "window.location.hash" in script
    assert 'id="first-investigation-evidence-toggle"' in html
    assert "window.location.hash === '#' + button.id" in script
    assert "@media (max-width: 760px)" in html
    assert "overflow-wrap: anywhere" in html
    assert "grid-template-columns: minmax(0, 1fr)" in html
    assert "@media print" in html
    assert ".source-evidence-region[hidden]" in html
    assert "Original source URL:" in html
    assert ".reviewer-detail-page .overview-side-panel" in html


def test_first_activity_evidence_stays_source_derived_and_separate() -> None:
    html = _render(_event(event_text="Investigation activity occurred."))
    start = html.index('id="first-investigation-evidence"')
    end = html.index("</div>", start)
    evidence_html = html[start:end]

    assert "Source-derived evidence" in evidence_html
    for reviewer_created in (
        "reviewer status",
        "reviewer note",
        "save status",
        "save note",
        "reviewer-created",
    ):
        assert reviewer_created not in evidence_html.casefold()


def _render(*events: Mapping[str, Any]) -> str:
    return reviewer_ui._render_overview_timeline(_source_record(), list(events))


def _source_record(
    *,
    first_activity_date: str = "2022-04-14",
    source_url: str = SOURCE_URL,
    raw_path: str = "tests/fixtures/ccld/raw/157806098_inx3.html",
) -> dict[str, Any]:
    return {
        "identity": {
            "source_record_key": "complaint:ccld:complaint:32-CR-20220407124448",
            "entity_type": "complaint",
            "stable_source_id": "ccld:complaint:32-CR-20220407124448",
            "facility_id": "ccld:facility:157806098",
        },
        "source_document": {
            "source_document_id": "ccld:document:157806098:3",
            "source_url": source_url,
            "raw_sha256": "not-rendered",
            "raw_path": raw_path,
            "connector_name": "not-rendered",
            "connector_version": "not-rendered",
            "retrieved_at": "not-rendered",
        },
        "original_values": {
            "complaint_id": "ccld:complaint:32-CR-20220407124448",
            "complaint_control_number": "32-CR-20220407124448",
            "complaint_received_date": "2022-04-07",
            "first_investigation_activity_date": first_activity_date,
            "visit_date": "2022-08-24",
            "report_date": "2022-08-24",
            "date_signed": "2022-08-26",
            "days_received_to_first_activity": 7,
            "days_received_to_visit": 139,
            "days_received_to_report": 139,
            "days_report_to_signed": 2,
        },
    }


def _event(
    *,
    stable_id: str = "ccld:event:32-CR-20220407124448:1",
    complaint_id: str = "ccld:complaint:32-CR-20220407124448",
    event_date: str = "2022-04-14",
    event_type: str = "investigation_activity",
    event_text: str = "Investigation activity occurred.",
    source_section: str = "investigation findings",
) -> dict[str, Any]:
    return {
        "source_record_key": f"event:{stable_id}",
        "entity_type": "event",
        "stable_source_id": stable_id,
        "source_document_id": "ccld:document:157806098:3",
        "facility_id": "ccld:facility:157806098",
        "original_values": {
            "complaint_id": complaint_id,
            "event_date": event_date,
            "event_type": event_type,
            "event_text": event_text,
            "extracted_from_section": source_section,
        },
    }


def _database_row_counts(engine: Any) -> dict[str, int]:
    with engine.connect() as connection:
        table_names = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).scalars()
        return {
            table_name: int(
                connection.exec_driver_sql(
                    f'SELECT COUNT(*) FROM "{table_name}"'
                ).scalar_one()
            )
            for table_name in table_names
        }
