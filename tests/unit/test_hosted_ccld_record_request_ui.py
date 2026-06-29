from __future__ import annotations

import html as html_lib
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlencode

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import ccld_facility_lookup as facility_lookup
from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CCLD_FACILITY_LOOKUP_PATH,
    CCLD_FACILITY_REFERENCE_CSV_ENV,
    CCLD_FACILITY_REVIEW_HUB_PATH,
    CCLD_FACILITY_REVIEW_PRIORITY_PATH,
    no_reference_facility_source,
)
from ccld_complaints.hosted_app.ccld_import_reload import (
    DEFAULT_LOCAL_VALIDATED_CCLD_ARTIFACT,
    ccld_import_reload_context_for_connection,
)
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    CCLD_RECORD_REQUEST_PATH,
    CcldRecordRequestUiContext,
    route_ccld_record_request_ui_response,
)
from ccld_complaints.hosted_app.facility_review_signals import (
    FACILITY_REVIEW_SIGNALS_CSVS_ENV,
)
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import hosted_reviewer_created_state
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    REVIEWER_UI_DETAIL_PATH,
    REVIEWER_UI_MATRIX_EXPORT_PATH,
    REVIEWER_UI_NOTE_PATH,
    REVIEWER_UI_STATUS_PATH,
    reviewer_ui_context_for_connection,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_SCOPE = LOCAL_REVIEWER_UI_SCOPE
COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"


@pytest.fixture(autouse=True)
def _ignore_local_default_full_facility_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        facility_lookup,
        "DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH",
        tmp_path / "missing-facility-reference.csv",
    )
    monkeypatch.setenv(
        FACILITY_REVIEW_SIGNALS_CSVS_ENV,
        str(tmp_path / "missing-facility-signals.csv"),
    )


def _local_dev_auth_config() -> Any:
    return load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )


def test_ccld_record_request_page_renders_from_default_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CCLD_RETRIEVAL_DEMO_MODE", "mock-success")

    status, content_type, body = route_response(
        "/ccld",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Retrieve complaint records" in html
    assert "Skip to main CCLD request content" in html
    assert '<main id="main-content" class="ds-page-main app-page" tabindex="-1">' in html
    assert "Retrieve complaint records for a facility" in html
    assert "Start review" in html
    assert "Choose a facility and date range, then open the complaint queue." in html
    mode_panel = html.split('<div class="mode-panel" aria-label="Retrieval mode">', 1)[1].split(
        "</div>",
        1,
    )[0]
    assert html.count("Fixture/mock demo") == 1
    assert html.count('<span class="ds-badge ds-badge--info">Fixture/mock demo</span>') == 1
    assert '<span class="ds-badge ds-badge--info">Fixture/mock demo</span>' in mode_panel
    assert "Keyboard flow: move from facility selection to date range" not in html
    assert '<details class="quiet-section orientation-details" open>' in html
    assert "Start review request context" in html
    assert "Facility/license number identifies the CCLD facility" in html
    assert "Date range narrows the loaded complaint records" in html
    assert "When records are found, open the recommended record" in html
    assert "Choose complaint date range" in html or "Which facility should be reviewed?" in html
    assert 'for="facility-search-input"' in html
    assert "facility-suggestion-list" in html
    assert "Which facility should be reviewed?" in html
    assert CCLD_FACILITY_LOOKUP_PATH in html
    assert "Use this number" in html
    assert "Use this facility/license number" not in html
    assert "Search by name, license number, city, county, ZIP" in html
    assert "facility type, program type, or status code" in html
    assert "Keyboard flow: type a search or digit number" not in html
    assert "Attorney workflow" not in html
    assert "Current step:" not in html
    assert "See review guidance and next steps." in html
    assert "Live retrieval off" not in html
    assert "Search CCLD facilities" in html
    assert "provider" not in html.casefold()
    assert_no_secret_html(html)


def test_ccld_record_request_page_embeds_cdss_chhs_facility_directory_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    full_csv = tmp_path / "CDSS_CCL_Facilities_2065342970436235361.csv"
    _write_chhs_facility_directory_csv(
        full_csv,
        rows=(
            {
                "FAC_NBR": "214005552",
                "NAME": "SUSD- TOMALES PRESCHOOL",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "24",
                "RES_CITY": "TOMALES",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "94971",
                "COUNTY": "Marin",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
                "RES_STREET_ADDR": "40 JOHN STREET",
                "FAC_PHONE_NBR": "7078782214",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(full_csv))

    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert 'id="facility-reference-json"' in html
    assert '"num": "214005552"' in html
    assert '"n": "SUSD- TOMALES PRESCHOOL"' in html
    assert '"state": "CA"' in html
    assert '"p": "CHILD CARE"' in html
    assert '"cap": "24"' in html
    assert "40 JOHN STREET" not in html
    assert "7078782214" not in html
    assert_no_secret_html(html)


def test_ccld_trailing_slash_route_renders_request_start() -> None:
    status, content_type, body = route_response(
        "/ccld/",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Retrieve complaint records" in html
    assert "Start review request context" in html
    assert "Which facility should be reviewed?" in html
    assert_no_secret_html(html)


def test_ccld_help_page_explains_workflow_terms_and_feedback() -> None:
    status, content_type, body = route_response("/ccld/help")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Help" in html
    assert "What this tool helps you do" in html
    assert "How to review a facility" in html
    assert "What review flags mean" in html
    assert "How source traceability works" in html
    assert "What to do with source-confidence cues" in html
    assert "Source-confidence cues are review prompts" in normalized_html
    assert "Source-confidence cues are review prompts" in normalized_html
    assert "describe only what the page showed" in normalized_html
    assert "return to the same queue and continue with the suggested next record" in (
        normalized_html
    )
    assert "source URL, raw SHA-256 hash" in html
    assert "traceability value is missing" in normalized_html
    assert "present, not available locally, confusing, or proxy-related" in normalized_html
    assert "Before relying on a source-derived value" in html
    assert "source document/report marker" in normalized_html
    assert "How reviewer-created notes/status work" in html
    assert "How correction-readiness works" in html
    assert "Correction-readiness means a tester has noticed" in html
    assert "Check source traceability first" in html
    assert "possible correction concern in a reviewer-created note or feedback" in html
    assert "do not edit source-derived fields" in html
    assert "correction concern in a reviewer-created note or feedback" in normalized_html
    assert "Open source links from the detail page when a source check is needed" in html
    assert "Retrieval modes" in html
    assert "Show existing queue means the page searched already-loaded source-derived" in (
        normalized_html
    )
    assert "it did not submit a controlled retrieval job" in normalized_html
    assert "Retrieve complaint records means a configured controlled retrieval job" in (
        normalized_html
    )
    assert "status/progress pages show the current job state" in normalized_html
    assert "Loaded source-derived records can be ready for review" in normalized_html
    assert "Retrieval status/progress is operational metadata" in normalized_html
    assert "metadata for the current review workflow" in normalized_html
    assert "Review guidance and next steps" in html
    assert "How to send useful feedback" in html
    assert "How packet preparation fits in" in html
    assert "packet preview/draft are preparation" in normalized_html
    assert "feedback carries safe context" in normalized_html
    assert "Packet readiness means review readiness" in html
    assert "manual review, browser copy, or browser print" in normalized_html
    assert "source-derived values, source traceability" in normalized_html
    assert "possible correction-readiness concerns" in normalized_html
    assert (
        "Packet preview and packet draft summarize loaded source-derived complaint records"
        in html
    )
    assert "Use feedback when packet readiness wording is confusing" in normalized_html
    assert "source-derived records" in normalized_html.casefold()
    assert "reviewer-created notes/status" in normalized_html
    assert "How reviewer-created status filters work" in html
    assert "active reviewer-created status filter" in normalized_html
    assert "records shown under that filter" in normalized_html
    assert "total records in the same facility/date queue" in normalized_html
    assert "filtered-empty result can mean the filter is hiding records" in normalized_html
    assert "filtered-empty result can mean the filter is hiding records" in normalized_html
    assert "Correction-readiness" in html
    assert "possible correction concern in a reviewer-created note or feedback" in html
    assert 'action="/ccld/correction' not in normalized_html
    assert 'name="correction_status"' not in normalized_html
    assert "correction approved" not in normalized_html
    assert "correction applied" not in normalized_html
    assert "corrected source record" not in normalized_html
    assert "Retrieve complaint records" in html
    assert_no_secret_html(html)


def test_ccld_record_request_prefills_selected_facility_from_lookup() -> None:
    status, content_type, body = route_response(
        f"{CCLD_RECORD_REQUEST_PATH}?"
        "facility_number=900000001&request_context_origin=facility_lookup"
        "&lookup_facility_name=Synthetic+Orchard+Child+Care",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Selected request context" in html
    assert "Facility lookup result" in html
    assert "Facility context cue" in html
    assert "facility hub" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=900000001" in html
    assert "Open facility hub for this request context" in html
    assert CCLD_FACILITY_REVIEW_PRIORITY_PATH in html
    assert "Open facility review priority list" in html
    assert "Facility/license number being requested" in html
    assert "Synthetic Orchard Child Care" in html
    assert "Active facility reference source" in html
    assert "value=\"900000001\"" in html
    assert "name=\"request_context_origin\"" in html
    assert "value=\"facility_lookup\"" in html
    assert "name=\"lookup_facility_name\"" in html
    assert "Choose complaint date range" in html
    assert "Use a bounded date range" in html
    assert (
        "Use the date range to narrow complaint, visit, report, signed, or retrieval dates"
        in html
    )
    assert_no_secret_html(html)


def test_ccld_record_request_prefill_links_signal_only_facility_hub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    signals_csv = tmp_path / "24HourResidentialCareforChildren06072026.csv"
    _write_program_summary_signals_csv(
        signals_csv,
        facility_number="157806098",
        facility_name="A. MIRIAM JAMISON CHILDREN'S CENTER",
    )
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    status, content_type, body = route_response(
        f"{CCLD_RECORD_REQUEST_PATH}?"
        "facility_number=157806098&request_context_origin=manual_entry"
        "&start_date=2026-01-01&end_date=2026-01-31",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split()).casefold()

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Selected request context" in html
    assert "Facility context cue" in html
    assert "signal-only facility hub" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" in html
    assert "Check facility hub or signal-only facility hub for this request context" in html
    assert "Open facility review priority list" in html
    assert "Start a new complaint request flow" in html
    assert "manual request context" in normalized_html
    assert "use this request context to decide whether to retrieve records" in normalized_html
    assert "return to the facility hub, or change criteria" in normalized_html
    assert_no_secret_html(html)


def test_ccld_record_request_manual_entry_shows_context_confirmation() -> None:
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Which facility should be reviewed?" in html
    assert "type the digit facility/license number directly" in html
    assert "See review guidance and next steps." in html
    assert "Live retrieval off" not in html
    assert "Search by name, license number, city, county, ZIP" in normalized_html
    assert "facility type, program type, or status code" in normalized_html
    assert "name=\"request_context_origin\"" in html
    assert "value=\"manual_entry\"" in html
    assert_no_secret_html(html)


def test_ccld_record_request_validates_required_facility_and_digits() -> None:
    with _seeded_connection() as connection:
        missing_status, _content_type, missing_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes({}),
            ccld_record_request_ui_context=_context(connection),
        )
        alpha_status, _content_type, alpha_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes({"facility_number": "abc-157806098"}),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    missing_html = missing_body.decode("utf-8")
    alpha_html = alpha_body.decode("utf-8")

    assert missing_status == 400
    assert "Facility/license number is required." in missing_html
    assert alpha_status == 400
    assert "must contain digits only for this CCLD-only request" in alpha_html
    assert counts == _empty_reviewer_counts()
    assert_no_secret_html(missing_html)
    assert_no_secret_html(alpha_html)


def test_ccld_record_request_validates_date_format_and_order() -> None:
    with _seeded_connection() as connection:
        invalid_date_status, _content_type, invalid_date_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes({"facility_number": "157806098", "start_date": "08/24/2022"}),
            ccld_record_request_ui_context=_context(connection),
        )
        reversed_status, _content_type, reversed_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-27",
                    "end_date": "2022-08-24",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    invalid_date_html = invalid_date_body.decode("utf-8")
    reversed_html = reversed_body.decode("utf-8")

    assert invalid_date_status == 400
    assert "Start date must use YYYY-MM-DD format." in invalid_date_html
    assert reversed_status == 400
    assert "End date must not be before start date." in reversed_html
    assert counts == _empty_reviewer_counts()
    assert_no_secret_html(invalid_date_html)
    assert_no_secret_html(reversed_html)


def test_ccld_record_request_rejects_unknown_queue_status_filter() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "reviewer_status_filter": "source_checked",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 400
    assert "Choose a supported reviewer-status filter." in html
    assert counts == _empty_reviewer_counts()
    assert_no_secret_html(html)


def test_ccld_record_request_matches_seeded_facility_and_links_to_reviewer_detail() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())
    detail_href = f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert "Complaint records ready for attorney review" in html
    assert "Retrieval job submitted" in html
    assert "Already-loaded source-derived rows were searched" in html
    assert "no controlled retrieval job was submitted for this request" in html
    assert "Records ready" in html
    assert "1 complaint queue record(s) are ready for review" in html
    assert "Review the already-loaded source-derived records in the queue" in html
    assert "Facility case brief" in html
    assert "Complaint records visible/imported" in html
    assert "Records with review flags" in html
    assert "Reviewer-created notes/statuses" in html
    assert "Possible delay indicators" in html
    assert "Missing first activity date" in html
    assert "Missing local key dates" not in html
    assert "Needs source check" in html
    assert "Findings represented" in html
    assert "Findings are source-derived categories, not legal conclusions" in html
    assert "Suggested first record for review" in html
    assert "Why open this first" in html
    assert "No reviewer-created status recorded yet" in html
    assert "Needs source check: first activity date missing locally" in html
    assert "Original CCLD source link saved" in html
    assert "Open priority record" in html
    assert "Open full queue" in html
    assert "Review packet readiness before copying or printing" in html
    assert "/reviewer/packet/preview?facility_number=157806098" in html
    assert "Download complaint review matrix CSV" in html
    assert f"{REVIEWER_UI_MATRIX_EXPORT_PATH}?facility_number=157806098" in html
    assert "Open packet preparation draft for browser copy or print" in html
    assert "/reviewer/packet/draft?facility_number=157806098" in html
    assert "Matching source-derived rows shown" in html
    assert "facility/license number 157806098" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "Selected request context" in html
    assert "Request started from" in html
    assert "Manual facility/license entry" in html
    assert "Facility context cue" in html
    assert "manual request context" in normalized_html.casefold()
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" in html
    assert "Check facility hub or signal-only facility hub for this request context" in html
    assert "Open facility review priority list" in html
    assert "Facility/license number being requested" in html
    assert "Date range being requested" in html
    assert "Active facility reference source" in html
    assert "Change facility/date criteria for this request" in html
    assert "Start over with a different CCLD facility" in html
    assert "CCLD review queue" in html
    assert "Open the suggested complaint first" in normalized_html
    assert "check the original CCLD source link and key dates/finding" in normalized_html
    assert "adding an optional note or status" in normalized_html
    assert "Do this next" in html
    assert "Start with the suggested next record." in normalized_html
    assert "On detail, check the original CCLD source link and key dates/finding" in (
        normalized_html
    )
    assert "Add a note or status only if it helps" in normalized_html
    assert (
        "Return to this queue and refresh the same request if the queue needs updated cues"
        in normalized_html
    )
    assert "Table view and queue guidance" in html
    assert "Queue review steps" in html
    assert (
        "Check the original CCLD source link, dates, finding, and reason it was flagged"
        in normalized_html
    )
    assert (
        "Return to this same queue and continue with the next suggested record"
        in normalized_html
    )
    assert (
        "Use the feedback checklist only when the queue or detail page is confusing"
        in normalized_html
    )
    assert "Facility/date-scoped CCLD complaint records ready for review" in html
    assert "Queue progress summary" in html
    assert "Counts use existing reviewer-created status rows" in normalized_html
    assert "Total matching complaint records" in html
    assert "<dt>Not started</dt>" in html
    assert "<dd>1</dd>" in html
    assert "Queue triage summary" in html
    assert (
        "Queue summaries highlight loaded records for this facility/date context"
        in normalized_html
    )
    assert "Open detail before relying on a missing or confusing value" in normalized_html
    assert "Next action: check the detail page" in normalized_html
    assert "Use the feedback checklist below only for missing records" in normalized_html
    assert "Continue review guidance" in html
    assert "derived from this facility/date request context" in normalized_html
    assert "Use it as navigation help for choosing" in html
    assert "After reviewing detail or saving a note/status" in normalized_html
    assert "Next record guidance" in html
    assert "Records with notes" in html
    assert "Records with status" in html
    assert "Records with original source links saved" in html
    assert "Suggested next record to open" in html
    assert "Open complaint detail for 32-CR-20220407124448" in html
    assert "Complaint worklist" in html
    assert "Open the recommended record first" in normalized_html
    assert "Missing values on a card are review cues" in normalized_html
    assert "Check the detail page before relying on a missing or confusing value" in (
        normalized_html
    )
    assert "Active CCLD request context" in html
    assert "Request origin" in html
    assert "Active facility reference source" in html
    assert "Loaded complaint records" in html
    assert "Records with status or notes" in html
    assert "Records with review flags or possible delay indicators" in html
    assert "Recommended next record action" in html
    assert "Open next priority record: 32-CR-20220407124448" in html
    assert "Why this record is prioritized" in html
    assert "Prioritized worklist records" in html
    assert "Recommended next record: 32-CR-20220407124448" in html
    assert "Review need: flagged for review. Check the detail page" in html
    assert "Complaint/control identifier" in html
    assert "Date/finding/flag summary" in html
    assert "Note/status cue" in html
    assert "Original source link status" in html
    assert "Open complaint detail for 32-CR-20220407124448" in html
    assert "More queue and export actions" in html
    assert "Review packet readiness before copying or printing" in html
    assert "Open packet preparation draft for browser copy or print" in html
    assert "prepared for review before browser copy or print" in normalized_html
    assert "do not assign, claim, or change records" in normalized_html
    assert "Queue decision actions" in html
    assert "Open facility review priority list" in html
    assert "tester feedback for this queue context" in normalized_html
    assert "Report unclear loaded-record versus retrieval-job state" in html
    assert "workflow_area=request-result" in html
    assert "retrieval_context=already-loaded-records" in html
    assert "retrieval_status=not_submitted" in html
    assert "a missing or unexpected record" in normalized_html
    assert "a confusing value, wording, filter" in normalized_html
    assert "/feedback?feedback_type=Bug+report" in html
    assert "workflow_area=queue" in html
    assert "facility_number=157806098" in html
    assert "start_date=2022-08-01" in html
    assert "end_date=2022-08-31" in html
    assert "reviewer_status_filter=all" in html
    assert "Describe+what+was+confusing+about+this+queue+or+filter" in html
    assert "Find another CCLD facility" in html
    assert "Start a new CCLD request" in html
    assert "Open CCLD workflow help" in html
    assert "Copy tester feedback checklist" in html
    assert "Reviewer-status filter for this queue" in html
    assert "Apply reviewer-status filter" in html
    assert "Active reviewer-created status filter" in html
    assert "Active reviewer-created status filter: All queue records." in html
    assert "Showing 1 of 1 records for this same facility/date request." in html
    assert "Records shown under active filter" in html
    assert "Total records in this same facility/date queue" in html
    assert "Available reviewer-created status filters" in html
    assert "Records shown under active filter" in html
    assert "A. MIRIAM JAMISON" in html
    assert "32-CR-20220407124448" in html
    assert detail_href in html
    assert "return_facility_number=157806098" in html
    assert "return_start_date=2022-08-01" in html
    assert "return_end_date=2022-08-31" in html
    assert "Original CCLD source link saved" in html
    assert "Original CCLD source link saved" in html
    assert "Records with original source links saved</dt>" in html
    assert "Loaded record context" in html
    assert "No reviewer-created notes/status yet" in html
    assert "1 loaded complaint records in bundle" not in html
    assert "6 loaded complaint records in bundle" in html
    assert "Open detail before relying on missing or confusing fields" in html
    assert "Copyable tester feedback checklist" in html
    assert "Copy details for feedback" in html
    assert "Structured CCLD feedback checklist" in html
    assert "id=\"feedback-checklist-section\"" in html
    assert "Select the checklist text, copy it, paste it" in normalized_html
    assert "Use this same manual checklist for queue observations" in normalized_html
    assert "filtered-empty recovery, no-match/load guidance" in normalized_html
    assert "CCLD tester feedback checklist" in html
    assert "- Matching source-derived rows shown: 6" in html
    assert "- Matching complaint records in queue: 1" in html
    assert "- Not started: 1" in html
    assert "- Reviewer-created notes present: no" in html
    assert "- Reviewer-created statuses present: no" in html
    assert "- Facility lookup used or skipped:" in html
    assert "- Facility lookup used or skipped: Manual facility/license entry" in html
    assert "- Active facility reference source:" in html
    assert "- Original CCLD source link was easy to find:" in html
    assert "- Missing or confusing values to mention:" in html
    assert "- Next action was clear for missing or confusing values:" in html
    assert "- Saved confirmation appeared as expected:" in html
    assert "- Queue showed updated note/status after returning" in html
    assert "- Records that seemed missing:" in html
    assert "- Records that seemed unexpected:" in html
    assert "- Manual-copy only: copy this checklist" in html
    assert "Open reviewer records" in html
    assert "did not submit a controlled retrieval job for this request" in html
    assert "run-ccld-live-fetch.ps1 -FacilityNumber 157806098" in html
    assert "legally sufficient" not in normalized_html.casefold()
    assert "verified abuse" not in normalized_html.casefold()
    assert "confirmed harm" not in normalized_html.casefold()
    assert "complete source record" not in normalized_html.casefold()
    assert_no_secret_html(html)


def test_ccld_record_request_queue_filters_by_existing_reviewer_status() -> None:
    with _seeded_connection() as connection:
        reviewer_context = reviewer_ui_context_for_connection(
            connection,
            actor=_actor(roles=("tester_reviewer",), display_name="Fixture Queue Reviewer"),
        )
        note_status, _content_type, note_body = route_response(
            REVIEWER_UI_NOTE_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "note_text": "Queue filter note.",
                }
            ),
            reviewer_ui_context=reviewer_context,
        )
        status_status, _content_type, status_body = route_response(
            REVIEWER_UI_STATUS_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "reviewer_status": "reviewed",
                }
            ),
            reviewer_ui_context=reviewer_context,
        )

        reviewed_status, _content_type, reviewed_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                    "reviewer_status_filter": "reviewed",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        blocked_status, _content_type, blocked_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                    "reviewer_status_filter": "blocked",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    note_html = note_body.decode("utf-8")
    status_html = status_body.decode("utf-8")
    reviewed_html = reviewed_body.decode("utf-8")
    reviewed_normalized = " ".join(reviewed_html.split())
    blocked_html = blocked_body.decode("utf-8")
    blocked_normalized = " ".join(blocked_html.split())

    assert note_status == 200
    assert status_status == 200
    assert "Reviewer note saved for this record" in note_html
    assert "Reviewer status saved for this record" in status_html
    assert "Reviewer-created state saved" in note_html
    assert "Reviewer-created state saved" in status_html
    assert "Return to facility queue" in note_html
    assert "Return to facility queue" in status_html
    assert "Open next priority record" in note_html
    assert "Open next priority record" in status_html
    assert "Queue progress and note/status cues are derived from reviewer-created state" in (
        note_html
    )
    assert "Queue progress and note/status cues are derived from reviewer-created state" in (
        status_html
    )
    assert reviewed_status == 200
    assert '<div class="dense-section-header">' in reviewed_html
    assert 'class="technical-details dense-table-details"' in reviewed_html
    assert 'class="technical-details diagnostic-details"' in reviewed_html
    assert "Latest reviewer-created status: Reviewed" in reviewed_html
    assert "1 reviewer-created note(s)" in reviewed_html
    assert "Complaint worklist" in reviewed_html
    assert "Records with status or notes" in reviewed_html
    assert "Note/status cue" in reviewed_html
    assert "Open complaint detail for 32-CR-20220407124448" in reviewed_html
    assert "Records with notes" in reviewed_html
    assert "Records with status" in reviewed_html
    assert "Suggested next record to open" in reviewed_html
    assert "Continue review guidance" in reviewed_html
    assert "Use it as navigation help for choosing" in reviewed_normalized
    assert "- Reviewer-created rows read for this queue: 2" in reviewed_html
    assert "- Reviewer-created notes present: yes" in reviewed_html
    assert "- Reviewer-created statuses present: yes" in reviewed_html
    assert "- Reviewed: 1" in reviewed_html
    assert "Active reviewer-created status filter: Reviewed." in reviewed_html
    assert "Showing 1 of 1 records for this same facility/date request." in reviewed_html
    assert "Available reviewer-created status filters" in reviewed_html
    assert "Open reviewer detail for 32-CR-20220407124448" in reviewed_html
    assert blocked_status == 200
    assert "Active reviewer-created status filter: Blocked." in blocked_html
    assert "Showing 0 of 1 records for this same facility/date request." in blocked_html
    assert "No complaint records match the selected reviewer-status filter" in blocked_normalized
    assert "Filtered queue recovery" in blocked_html
    assert "No records match this active reviewer-created status filter" in blocked_html
    assert "same facility/date request context" in blocked_normalized
    assert "does not mean records are missing, deleted, absent" in blocked_normalized
    assert "Active request context" in blocked_html
    assert "facility/license number 157806098; date range 2022-08-01 to 2022-08-31" in (
        blocked_normalized
    )
    assert "Active reviewer-created status filter" in blocked_html
    assert "Records shown under active filter" in blocked_html
    assert "Total records in this same facility/date queue" in blocked_html
    assert "<dd>1</dd>" in blocked_html
    assert "Reviewer-status filters use existing reviewer-created state" in blocked_html
    assert "Records without a saved status are counted as not started" in blocked_normalized
    assert "Show all reviewer statuses for this facility/date request" in blocked_html
    assert "name=\"reviewer_status_filter\" value=\"all\"" in blocked_html
    assert "return to the full CCLD request queue" in blocked_normalized
    assert "manual feedback checklist" in blocked_html
    assert "what you expected to see" in blocked_normalized
    assert "choose All queue records" in blocked_normalized
    assert "filtered-empty result" in blocked_normalized
    assert "tester feedback for this filtered queue" in blocked_normalized
    assert "Open facility review priority list" in blocked_html
    assert "reviewer_status_filter=blocked" in blocked_html
    assert counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert_no_secret_html(reviewed_html)
    assert_no_secret_html(blocked_html)
    assert_no_secret_html(note_html)
    assert_no_secret_html(status_html)


def test_ccld_record_request_shows_no_match_plan_without_mutation() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert "Candidates may be outside the selected date range" in html
    assert "Rows available before date filtering" in html
    assert "<dd>6</dd>" in html
    normalized_html = " ".join(html.split())
    assert "Confirm the facility/date context" in normalized_html
    assert "No loaded source-derived records matched this request context" in html
    assert "Use the no-match result to confirm criteria" in normalized_html
    assert "Try one next step" in html
    assert "Check or change the facility/license number" in html
    assert "Adjust the complaint date range" in html
    assert "Use loaded records by changing the date range" in normalized_html
    assert "Skip retrieval/job troubleshooting for this result" in normalized_html
    assert "no controlled retrieval job was submitted" in normalized_html
    assert "Report confusion with the facility/license number, date range" in normalized_html
    assert "How to interpret this no-match result" in html
    assert "currently loaded source-derived rows only" in normalized_html
    assert "did not submit a controlled retrieval job for this request" in normalized_html
    assert "Retrieval job submitted" in html
    assert "Already-loaded source-derived rows were searched" in html
    assert "Change the facility/date criteria" in normalized_html
    assert "Facility/license number searched" in html
    assert "Date range searched" in html
    assert "Loaded source-derived rows for this facility before date filtering" in html
    assert "Local validated load state" in html
    assert "not submitted for this request" in html
    assert "Change the facility/license number or date range" in normalized_html
    assert "use the local validated CCLD load action" in html
    assert "outside-browser live fetch and artifact-builder workflow" in normalized_html
    assert "copy the feedback checklist" in html
    assert "Use the no-match result to confirm criteria" in html
    assert "Selected request context" in html
    assert "Change facility/date criteria for this request" in html
    assert "Copyable tester feedback checklist" in html
    assert "Technical retrieval details" in html
    assert "Copy details for feedback" in html
    assert 'class="technical-details diagnostic-details"' in html
    assert 'class="technical-details dense-table-details"' in html
    assert "Report unclear loaded-record versus retrieval-job state" in html
    assert "Open facility review priority list" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" in html
    assert "Check facility hub or signal-only facility hub for this request context" in html
    assert "workflow_area=request-result" in html
    assert "retrieval_context=already-loaded-records" in html
    assert "retrieval_status=not_submitted" in html
    assert "Advanced local/operator actions" in html
    assert "- Matching source-derived rows shown: 0" in html
    assert "- Matching complaint records in queue: 0" in html
    assert "- Local facility rows before date filtering: 6" in html
    assert "- None shown for this request." in html
    assert "Technical preparation path" in html
    assert "When controlled retrieval is configured" in html
    assert "use the browser retrieval action" in html
    assert "Server-side retrieval, raw preservation" in html
    assert "build-hosted-ccld-artifact.ps1" in html
    assert "The browser remains a trigger only" in html
    assert "SQLite conversion remains outside the browser path" in html
    assert_no_secret_html(html)


def test_ccld_record_request_queue_preserves_lookup_selected_context() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                    "request_context_origin": "facility_lookup",
                    "lookup_facility_name": "A. MIRIAM JAMISON",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")
    checklist = _feedback_checklist(html)

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert "Selected request context" in html
    assert "Facility lookup result" in html
    assert "Selected lookup facility name" in html
    assert "A. MIRIAM JAMISON" in html
    assert "Date range being requested" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "Open the suggested complaint first" in " ".join(html.split())
    assert "request_context_origin" in html
    assert "lookup_facility_name" in html
    assert "- Facility lookup used or skipped: Facility lookup result" in checklist
    assert "- Selected lookup facility name: A. MIRIAM JAMISON" in checklist
    assert "- Active facility reference source:" in checklist
    assert_no_secret_html(html)


def test_ccld_record_request_empty_hosted_records_offers_local_validated_load() -> None:
    with _empty_connection() as connection:
        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert counts == _empty_unloaded_counts()
    assert "No loaded complaint records match this request yet" in html
    assert "Load local validated CCLD records" in html
    assert "How to interpret this no-match result" in html
    normalized_html = " ".join(html.split())
    assert "currently loaded source-derived rows only" in normalized_html
    assert "Use the no-match result to confirm criteria" in normalized_html
    assert "Try one next step" in html
    assert "Check or change the facility/license number" in html
    assert "Adjust the complaint date range" in html
    assert "Load or refresh records" in html
    assert "Skip retrieval/job troubleshooting for this result" in normalized_html
    assert "Report confusion with the facility/license number, date range" in normalized_html
    assert "no controlled retrieval job was submitted for this request" in html
    assert "no</dd>" in html
    assert "Change the facility/date criteria" in " ".join(html.split())
    assert "Loaded source-derived rows for this facility before date filtering" in html
    assert "not submitted for this request" in html
    assert "Copyable tester feedback checklist" in html
    assert "Report unclear loaded-record versus retrieval-job state" in html
    assert "workflow_area=request-result" in html
    assert "retrieval_context=already-loaded-records" in html
    assert "retrieval_status=not_submitted" in html
    assert "- Local facility rows before date filtering: 0" in html
    assert "does not run live public web requests" in html
    assert "ccld_import_reload_action" in html
    assert_no_secret_html(html)


def test_ccld_record_request_loads_local_validated_output_then_shows_matches() -> None:
    with _empty_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                    "ccld_import_reload_action": "load_local_validated_ccld_records",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")
    detail_href = f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == []
    assert len(after_source_rows) == 6
    assert counts == _empty_reviewer_counts()
    assert "Local validated CCLD load result" in html
    assert "Load executed: yes." in html
    assert "New source-derived rows staged" in html
    assert "validated_seeded_corpus.json" in html
    assert "Complaint records ready for attorney review" in html
    assert "Retrieval job submitted" in html
    assert "no</dd>" in html
    assert "Already-loaded source-derived rows were searched" in html
    assert "Complaint records ready" in html
    assert "Review the already-loaded source-derived records in the queue" in html
    assert "Matching source-derived rows shown" in html
    assert "- Load action submitted on this request: yes" in html
    assert "- Local validated records loaded or refreshed: yes" in html
    assert "- New source-derived rows staged: 6" in html
    assert "- Existing source-derived rows refreshed: 0" in html
    assert detail_href in html
    assert "Refresh from local validated CCLD output" in html
    assert "run live public web requests" in html
    assert_no_secret_html(html)


def test_ccld_record_request_feedback_checklist_is_deterministic_and_non_persistent() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        first_status, _content_type, first_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        second_status, _content_type, second_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    first_html = first_body.decode("utf-8")
    second_html = second_body.decode("utf-8")
    first_checklist = _feedback_checklist(first_html)
    second_checklist = _feedback_checklist(second_html)

    assert first_status == 200
    assert second_status == 200
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert first_checklist == second_checklist
    assert first_checklist.startswith("CCLD tester feedback checklist")
    assert "- Source scope: CCLD public complaint records only" in first_checklist
    assert "- Facility/license number: 157806098" in first_checklist
    assert "- Facility lookup used or skipped: Manual facility/license entry" in first_checklist
    assert "- Selected lookup facility name: unknown" in first_checklist
    assert "- Active facility reference source:" in first_checklist
    assert "- Date range requested: 2022-08-01 to 2022-08-31" in first_checklist
    assert "- Request criteria that felt unclear:" in first_checklist
    assert "- Matching source-derived rows shown: 6" in first_checklist
    assert "- Matching complaint records in queue: 1" in first_checklist
    assert "Queue triage and filters" in first_checklist
    assert "- Local validated records loaded or refreshed: no" in first_checklist
    assert "- Reviewer-created rows read for this queue: 0" in first_checklist
    assert "Queue records to spot-check" in first_checklist
    assert "source traceability cue: Original CCLD source link saved" in first_checklist
    assert "source URL, raw SHA-256 hash" in first_checklist
    assert "Original CCLD source link saved" in first_checklist
    assert "reviewer note/status cue: No reviewer-created notes/status yet" in first_checklist
    assert "Reviewer detail and note/status confirmation" in first_checklist
    assert "- Review session path was clear from home/request/help:" in first_checklist
    assert "- Original CCLD source link was easy to find:" in first_checklist
    assert "- Missing or confusing values to mention:" in (
        first_checklist
    )
    assert "- Next action was clear for missing or confusing values:" in (
        first_checklist
    )
    assert "- Saved confirmation appeared as expected:" in first_checklist
    assert "- Return-to-queue link worked:" in first_checklist
    assert "- Queue showed updated note/status after returning and resubmitting:" in (
        first_checklist
    )
    assert "Retrieval status/progress clarity" in first_checklist
    assert (
        "- It was clear whether records were already loaded, a controlled retrieval job was "
        "submitted, or a job was still waiting:"
        in first_checklist
    )
    assert "- Retrieval job/status/progress wording that was confusing:" in first_checklist
    assert "- Next action after retrieval status was clear:" in first_checklist
    assert "Missing, unexpected, or confusing results" in first_checklist
    assert "- Records that seemed missing:" in first_checklist
    assert "- Records that seemed unexpected:" in first_checklist
    assert "- Facility lookup wording that was confusing:" in first_checklist
    assert "- Request, queue, or reviewer-detail wording that was confusing:" in (
        first_checklist
    )
    assert "- Keyboard, reading-order, or checklist-copy friction:" in first_checklist
    assert "- Suggested enhancements:" in first_checklist
    assert "- Manual-copy only: copy this checklist" in first_checklist
    assert "- The app does not store, send, email, export, or persist this feedback." in (
        first_checklist
    )
    assert "does not create a saved review session, persisted queue state, or second checklist" in (
        first_checklist
    )
    assert "Rendering this checklist does not change source-derived records" in first_checklist
    assert "Browser pages only trigger controlled server-side retrieval" in first_checklist
    assert "Include any records that seemed missing, unexpected, or confusing" in first_checklist
    assert "Select the checklist text, copy it, paste it" in " ".join(first_html.split())
    assert "Open source links from the detail page when a source check is needed" in (
        first_checklist
    )
    assert "provider" not in first_checklist.casefold()
    assert_no_secret_html(first_html)
    assert_no_secret_html(second_html)


def test_ccld_record_request_local_validated_load_defers_when_dates_do_not_match() -> None:
    with _empty_connection() as connection:
        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                    "ccld_import_reload_action": "load_local_validated_ccld_records",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert counts == _empty_unloaded_counts()
    assert "Local validated CCLD load result" in html
    assert "Load executed: no." in html
    assert "reads prepared hosted seeded-corpus JSON only" in " ".join(html.split())
    assert "No local validated CCLD records matched" in html
    assert "submitted, but no matching local validated rows were loaded" in html
    assert "No loaded complaint records match this request yet" in html
    assert "How to interpret this no-match result" in html
    assert "outside-browser live fetch and artifact-builder workflow" in " ".join(html.split())
    assert_no_secret_html(html)


def test_ccld_record_request_load_is_isolated_from_generated_corpus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load action uses the tracked fixture even when the generated corpus file exists locally.

    Regression: _default_local_validated_ccld_artifact_paths() returns the
    generated data/processed corpus when that file exists on disk.  This test
    confirms that unit tests using _context() pin to the tracked fixture and
    are unaffected, even with a generated corpus present at the CWD-relative
    generated path.
    """
    from ccld_complaints.hosted_app import ccld_import_reload as _import_reload_mod
    from ccld_complaints.hosted_app.ccld_import_reload import (
        _default_local_validated_ccld_artifact_paths,
    )

    # Create a fake generated corpus at an absolute tmp path and patch the
    # module-level constant so dynamic discovery treats it as if it existed
    # at data/processed/hosted_seeded_corpus/validated_ccld_seeded_corpus.json.
    fake_corpus = tmp_path / "validated_ccld_seeded_corpus.json"
    fake_corpus.write_text(
        '{"import_batch_id": "generated-batch-not-in-test-scope", "records": []}'
    )
    monkeypatch.setattr(_import_reload_mod, "DEFAULT_GENERATED_CCLD_HOSTED_ARTIFACT", fake_corpus)

    # Confirm the bug pre-condition: dynamic discovery now finds the fake file.
    discovered = _default_local_validated_ccld_artifact_paths()
    assert fake_corpus in discovered, (
        "pre-condition: dynamic discovery must find the patched fake generated corpus"
    )

    # Confirm the fix: _context() ignores the fake generated file.
    with _empty_connection() as connection:
        context = _context(connection)
        assert context.import_reload_context is not None
        assert fake_corpus not in context.import_reload_context.artifact_paths
        assert DEFAULT_LOCAL_VALIDATED_CCLD_ARTIFACT in context.import_reload_context.artifact_paths

        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                    "ccld_import_reload_action": "load_local_validated_ccld_records",
                }
            ),
            ccld_record_request_ui_context=context,
        )

    html = body.decode("utf-8")

    assert status == 200
    # Tracked fixture has exactly 6 records - not the large generated corpus count.
    assert "- New source-derived rows staged: 6" in html
    assert "validated_seeded_corpus.json" in html
    assert_no_secret_html(html)


def _context(connection: Connection) -> CcldRecordRequestUiContext:
    """Build a test request context pinned to the tracked small fixture.

    Explicitly passes artifact_paths so the context never falls back to
    _default_local_validated_ccld_artifact_paths(), which would discover the
    ignored generated data/processed corpus when it exists locally and cause
    import counts to diverge from fixture expectations.
    """
    reviewer_context = reviewer_ui_context_for_connection(
        connection,
        actor=_actor(roles=("tester_reviewer",)),
    )
    source_context = reviewer_context.workflow_shell_context.source_derived_api_context
    import_reload_context = ccld_import_reload_context_for_connection(
        source_context.connection,
        scope=source_context.scope,
        artifact_paths=(DEFAULT_LOCAL_VALIDATED_CCLD_ARTIFACT,),
    )
    return CcldRecordRequestUiContext(
        reviewer_ui_context=reviewer_context,
        import_reload_context=import_reload_context,
    )


def test_ccld_request_page_facility_selector_renders() -> None:
    """Facility selector must render on the request page with accessible structure."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert 'id="facility-selector-wrap"' in html
    assert 'for="facility-search-input"' in html
    assert 'id="facility-suggestion-list"' in html
    assert_no_secret_html(html)


def test_ccld_request_page_manual_facility_button_disabled_by_default() -> None:
    """Manual facility submit starts disabled until a non-empty value is entered."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert (
        '<button type="submit" id="facility-submit-btn" disabled>'
        "Use this number</button>"
    ) in html
    assert html.count("Use this number") == 1
    assert "Use this facility/license number" not in html
    assert_no_secret_html(html)


def test_ccld_request_page_manual_facility_button_uses_trimmed_input_state() -> None:
    """Whitespace-only manual input must keep the submit button disabled."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert "function updateSubmitState()" in html
    assert "if(sb)sb.disabled=!si.value.trim();" in html
    assert "si.addEventListener('input',function()" in html
    assert "updateSubmitState();" in html
    assert_no_secret_html(html)


def test_ccld_request_page_facility_selector_has_concise_placeholder() -> None:
    """Request page facility input placeholder must be short and not clipped."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert 'placeholder="Facility/license number"' in html
    assert "Search by name, license number, city, county, ZIP" in html
    assert "facility type, program type, or status code" in html
    # Placeholder must not be the full helper sentence
    assert 'placeholder="Search facility name' not in html
    assert_no_secret_html(html)


def test_ccld_request_page_limited_reference_note_appears_when_fallback_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Request page facility selector must show a limited-reference note when fallback is active."""
    monkeypatch.delenv(CCLD_FACILITY_REFERENCE_CSV_ENV, raising=False)

    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert "Limited reference list" in html
    assert "suggestions may not include every CCLD facility" in html
    assert_no_secret_html(html)


def test_ccld_request_page_no_internal_path_labels_in_primary_ui() -> None:
    """Internal scaffold/path labels must not appear in the primary request page UI."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert "Tiny committed CCLD facility fixture fallback" not in html
    assert "Full CCLD facility reference CSV" not in html
    assert_no_secret_html(html)


def test_request_page_with_no_reference_source_shows_not_configured_and_no_synthetic_data() -> None:
    """In live mode with no_reference, request page must not expose synthetic fixture data."""
    with _seeded_connection() as connection:
        status, content_type, body = route_ccld_record_request_ui_response(
            CCLD_RECORD_REQUEST_PATH,
            _context(connection),
            facility_reference=no_reference_facility_source(),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    # Manual entry is still available as the primary path
    assert "Which facility should be reviewed?" in html
    assert 'id="facility-search-input"' in html
    assert "Use this number" in html
    assert "Use this facility/license number" not in html
    # No synthetic fixture facility names in the HTML
    assert "Synthetic Orchard" not in html
    assert "Synthetic Valley" not in html
    assert "900000001" not in html
    assert "900000002" not in html
    # "Facility directory lookup is not configured" notice is shown
    assert "not configured" in html.lower() or "Facility directory lookup" in html
    assert_no_secret_html(html)


def test_live_postgres_mode_request_page_uses_source_derived_not_tiny_fixture() -> None:
    """In live postgres mode, the request page must use source-derived facility data."""
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            auth_runtime_config=_local_dev_auth_config(),
            page_data_mode="postgres",
            ccld_record_request_ui_context=_context(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    # No synthetic fixture facility names from the tiny fixture
    assert "Synthetic Orchard Child Care" not in html
    assert "Synthetic Valley Family Agency" not in html
    # Synthetic fixture facility numbers must not be in the embedded typeahead JSON
    assert '"900000001"' not in html
    assert '"900000002"' not in html
    assert_no_secret_html(html)


def test_fixture_demo_mode_request_page_still_allows_tiny_fixture_suggestions() -> None:
    """fixture-demo mode must continue to allow the tiny fixture for local/demo use."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    # In fixture-demo mode: tiny fixture is acceptable
    assert "Which facility should be reviewed?" in html
    assert "facility-reference-json" in html
    assert_no_secret_html(html)


def assert_no_secret_html(markup: str) -> None:
    lowered = markup.casefold()
    for marker in [
        "provider_subject",
        "secret",
        "token",
        "tester@example.invalid",
        "https://example.com",
    ]:
        assert marker not in lowered


def _feedback_checklist(markup: str) -> str:
    start_marker = '<textarea id="feedback-checklist"'
    start = markup.index(start_marker)
    content_start = markup.index(">", start) + 1
    content_end = markup.index("</textarea>", content_start)
    return html_lib.unescape(markup[content_start:content_end]).strip()


def _form_bytes(payload: dict[str, str]) -> bytes:
    return urlencode(payload).encode("utf-8")


def _write_chhs_facility_directory_csv(
    path: Path,
    *,
    rows: tuple[dict[str, str], ...],
) -> None:
    fieldnames = (
        "FAC_LATITUDE",
        "FAC_LONGITUDE",
        "FAC_NBR",
        "TYPE",
        "PROGRAM_TYPE",
        "STATUS",
        "CLIENT_SERVED",
        "CAPACITY",
        "NAME",
        "RES_STREET_ADDR",
        "RES_CITY",
        "RES_STATE",
        "RES_ZIP_CODE",
        "FAC_PHONE_NBR",
        "FAC_CO_NBR",
        "COUNTY",
        "FAC_DO_DESC",
        "FAC_TYPE_DESC",
        "ObjectId",
        "x",
        "y",
    )
    with path.open("w", encoding="utf-8", newline="") as fixture_file:
        fixture_file.write(",".join(fieldnames) + "\n")
        for row in rows:
            fixture_file.write(
                ",".join(row.get(fieldname, "") for fieldname in fieldnames) + "\n"
            )


def _write_program_summary_signals_csv(
    path: Path,
    *,
    facility_number: str,
    facility_name: str,
) -> None:
    fieldnames = (
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
    row = {
        "Facility Type": "TEMPORARY SHELTER CARE FACILITY",
        "Facility Number": facility_number,
        "Facility Name": facility_name,
        "Licensee": "Do Not Display Licensee",
        "Facility Administrator": "Do Not Display Admin",
        "Facility Telephone Number": "555-0199",
        "Facility Address": "1 Private Fixture Way",
        "Facility City": "BAKERSFIELD",
        "Facility State": "CA",
        "Facility Zip": "93307",
        "County Name": "KERN",
        "Regional Office": "Central Valley",
        "Facility Capacity": "48",
        "Facility Status": "LICENSED",
        "License First Date": "7/30/2018",
        "Closed Date": "",
        "Last Visit Date": "5/4/2026",
        "Inspection Visits": "0",
        "Complaint Visits": "12",
        "Other Visits": "31",
        "Total Visits": "43",
        "Citation Numbers": "84072(d)(14), 84665.5(f)",
        "POC Dates": "07/28/2021, 06/20/2024",
        "All Visit Dates": "",
        "Inspection Visit Dates": "",
        "Inspect TypeA": "",
        "Inspect TypeB": "",
        "Other Visit Dates": "",
        "Other TypeA": "A citation",
        "Other TypeB": "B citation",
        "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ...": "",
    }
    with path.open("w", encoding="utf-8", newline="") as fixture_file:
        fixture_file.write(",".join(f'"{fieldname}"' for fieldname in fieldnames) + "\n")
        fixture_file.write(
            ",".join(f'"{row.get(fieldname, "")}"' for fieldname in fieldnames)
            + "\n"
        )


def _seeded_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _empty_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    return engine.connect()


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
    actor_category: str = "tester",
    provider_subject: str = "fixture-ccld-request-reviewer",
    display_name: str = "Fixture CCLD Request Reviewer",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject=provider_subject,
        provider_issuer="fixture-managed-oidc-provider",
        display_name=display_name,
        email="tester@example.invalid",
        actor_category=cast(HostedActorCategory, actor_category),
        account_status=cast(HostedAccountStatus, account_status),
        roles=tuple(cast(HostedTesterRole, role) for role in roles),
        scopes=scopes,
    )


def _source_rows(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(hosted_source_derived_records).order_by(
            hosted_source_derived_records.c.source_record_key
        )
    ).mappings()
    return [dict(row) for row in rows]


def _table_counts(connection: Connection) -> dict[str, int]:
    import_batches = connection.execute(
        select(func.count()).select_from(hosted_import_batches)
    ).scalar_one()
    source_records = connection.execute(
        select(func.count()).select_from(hosted_source_derived_records)
    ).scalar_one()
    reviewer_created_state = connection.execute(
        select(func.count()).select_from(hosted_reviewer_created_state)
    ).scalar_one()
    audit_events = connection.execute(
        select(func.count()).select_from(hosted_audit_events)
    ).scalar_one()
    reset_reload_planning_metadata = connection.execute(
        select(func.count()).select_from(hosted_reset_reload_planning_metadata)
    ).scalar_one()
    return {
        "import_batches": import_batches,
        "source_records": source_records,
        "reviewer_created_state": reviewer_created_state,
        "audit_events": audit_events,
        "reset_reload_planning_metadata": reset_reload_planning_metadata,
    }


def _empty_reviewer_counts() -> dict[str, int]:
    return {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }


def _empty_unloaded_counts() -> dict[str, int]:
    return {
        "import_batches": 0,
        "source_records": 0,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
