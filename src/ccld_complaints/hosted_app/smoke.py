from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import threading
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ccld_complaints.hosted_app.app import create_server, format_host
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    reset_default_ccld_record_request_ui_context,
)
from ccld_complaints.hosted_app.reviewer_ui import reset_default_local_test_reviewer_ui_context


def _read_url(url: str) -> tuple[int, bytes]:
    try:
        with urlopen(url, timeout=5) as response:
            return response.status, response.read()
    except HTTPError as error:
        return int(error.code), error.read()


def _post_form_url(url: str, payload: dict[str, str]) -> tuple[int, bytes]:
    body = urlencode(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except HTTPError as error:
        return int(error.code), error.read()


def run_scaffold_smoke_check(host: str = "127.0.0.1", port: int = 0) -> dict[str, object]:
    previous_auth_mode = os.environ.get("CCLD_HOSTED_TESTER_AUTH_MODE")
    previous_local_dev_auth = os.environ.get("CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH")
    previous_page_data_mode = os.environ.get("CCLD_HOSTED_PAGE_DATA_MODE")
    previous_retrieval_enabled = os.environ.get("CCLD_RETRIEVAL_ENABLED")
    previous_retrieval_raw_dir = os.environ.get("CCLD_RETRIEVAL_RAW_DIR")
    previous_retrieval_max_range = os.environ.get("CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS")
    previous_retrieval_demo_mode = os.environ.get("CCLD_RETRIEVAL_DEMO_MODE")
    previous_facility_reference_csv = os.environ.get("CCLD_FACILITY_REFERENCE_CSV")
    os.environ["CCLD_HOSTED_TESTER_AUTH_MODE"] = "local-dev"
    os.environ["CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH"] = "enabled"
    os.environ["CCLD_HOSTED_PAGE_DATA_MODE"] = "fixture-demo"
    os.environ["CCLD_RETRIEVAL_ENABLED"] = "disabled"
    os.environ["CCLD_RETRIEVAL_RAW_DIR"] = ""
    os.environ["CCLD_RETRIEVAL_DEMO_MODE"] = ""
    os.environ["CCLD_FACILITY_REFERENCE_CSV"] = "__missing_smoke_facility_reference__.csv"
    reset_default_ccld_record_request_ui_context()
    reset_default_local_test_reviewer_ui_context()
    try:
        with (
            tempfile.TemporaryDirectory() as retrieval_raw_dir,
            create_server(host, port) as server,
        ):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            bound_host, bound_port = server.server_address[:2]
            base_url = f"http://{format_host(bound_host)}:{bound_port}"
            try:
                health_status, health_body = _read_url(f"{base_url}/health")
                root_status, root_body = _read_url(f"{base_url}/")
                records_status, records_body = _read_url(f"{base_url}/source-records")
                facilities_status, facilities_body = _read_url(f"{base_url}/facilities")
                ccld_facilities_status, ccld_facilities_body = _read_url(
                    f"{base_url}/ccld/facilities?q=orchard"
                )
                ccld_status, ccld_body = _read_url(f"{base_url}/ccld/records/request")
                ccld_retrieval_history_status, ccld_retrieval_history_body = _read_url(
                    f"{base_url}/ccld/retrieval/jobs"
                )
                ccld_retrieval_detail_status, ccld_retrieval_detail_body = _read_url(
                    f"{base_url}/ccld/retrieval/jobs/detail?job_id=missing-job"
                )
                (
                    ccld_retrieval_detail_invalid_status,
                    ccld_retrieval_detail_invalid_body,
                ) = _read_url(
                    f"{base_url}/ccld/retrieval/jobs/detail?job_id=..%2Fprivate"
                )
                ccld_queue_status, ccld_queue_body = _post_form_url(
                    f"{base_url}/ccld/records/request",
                    {
                        "facility_number": "157806098",
                        "start_date": "2022-08-01",
                        "end_date": "2022-08-31",
                    },
                )
                ccld_filtered_status, ccld_filtered_body = _post_form_url(
                    f"{base_url}/ccld/records/request",
                    {
                        "facility_number": "157806098",
                        "start_date": "2022-08-01",
                        "end_date": "2022-08-31",
                        "reviewer_status_filter": "blocked",
                    },
                )
                ccld_no_match_status, ccld_no_match_body = _post_form_url(
                    f"{base_url}/ccld/records/request",
                    {
                        "facility_number": "157806098",
                        "start_date": "2023-01-01",
                        "end_date": "2023-12-31",
                    },
                )
                ccld_retrieval_setup_status, ccld_retrieval_setup_body = _post_form_url(
                    f"{base_url}/ccld/records/request",
                    {
                        "facility_number": "157806098",
                        "record_type": "complaints",
                        "start_date": "2022-08-01",
                        "end_date": "2022-08-31",
                        "ccld_retrieval_action": "run_controlled_ccld_retrieval",
                    },
                )
                os.environ["CCLD_RETRIEVAL_ENABLED"] = "enabled"
                os.environ["CCLD_RETRIEVAL_RAW_DIR"] = retrieval_raw_dir
                os.environ["CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS"] = "30"
                os.environ["CCLD_RETRIEVAL_DEMO_MODE"] = "mock-success"
                ccld_retrieval_success_status, ccld_retrieval_success_body = _post_form_url(
                    f"{base_url}/ccld/records/request",
                    {
                        "facility_number": "157806098",
                        "record_type": "complaints",
                        "start_date": "2022-08-01",
                        "end_date": "2022-08-31",
                        "ccld_retrieval_action": "run_controlled_ccld_retrieval",
                    },
                )
                ccld_retrieval_history_after_status, (
                    ccld_retrieval_history_after_body
                ) = _read_url(f"{base_url}/ccld/retrieval/jobs")
                detail_match = re.search(
                    br"/ccld/retrieval/jobs/detail\?job_id=[A-Za-z0-9_.:-]+",
                    ccld_retrieval_history_after_body,
                )
                if detail_match is None:
                    ccld_retrieval_success_detail_status = 404
                    ccld_retrieval_success_detail_body = b""
                else:
                    (
                        ccld_retrieval_success_detail_status,
                        ccld_retrieval_success_detail_body,
                    ) = _read_url(f"{base_url}{detail_match.group(0).decode('ascii')}")
                reviewer_status, reviewer_body = _read_url(f"{base_url}/reviewer")
                reviewer_detail_status, reviewer_detail_body = _read_url(
                    f"{base_url}/reviewer/records/detail?"
                    "source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448"
                )
                packet_preview_status, packet_preview_body = _read_url(
                    f"{base_url}/reviewer/packet/preview?"
                    "facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31"
                )
                packet_draft_status, packet_draft_body = _read_url(
                    f"{base_url}/reviewer/packet/draft?"
                    "facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31"
                )
                packet_draft_empty_status, packet_draft_empty_body = _read_url(
                    f"{base_url}/reviewer/packet/draft"
                )
                reviewer_note_status, reviewer_note_body = _post_form_url(
                    f"{base_url}/reviewer/records/note",
                    {
                        "source_record_key": (
                            "complaint:ccld:complaint:32-CR-20220407124448"
                        ),
                        "note_text": "Smoke confirmation note.",
                    },
                )
                reviewer_saved_status, reviewer_saved_status_body = _post_form_url(
                    f"{base_url}/reviewer/records/status",
                    {
                        "source_record_key": (
                            "complaint:ccld:complaint:32-CR-20220407124448"
                        ),
                        "reviewer_status": "in_review",
                    },
                )
                feedback_status, feedback_body = _read_url(f"{base_url}/feedback")
                help_status, help_body = _read_url(f"{base_url}/ccld/help")
            finally:
                server.shutdown()
                thread.join(timeout=5)
    finally:
        _restore_env("CCLD_HOSTED_TESTER_AUTH_MODE", previous_auth_mode)
        _restore_env("CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH", previous_local_dev_auth)
        _restore_env("CCLD_HOSTED_PAGE_DATA_MODE", previous_page_data_mode)
        _restore_env("CCLD_RETRIEVAL_ENABLED", previous_retrieval_enabled)
        _restore_env("CCLD_RETRIEVAL_RAW_DIR", previous_retrieval_raw_dir)
        _restore_env("CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS", previous_retrieval_max_range)
        _restore_env("CCLD_RETRIEVAL_DEMO_MODE", previous_retrieval_demo_mode)
        _restore_env("CCLD_FACILITY_REFERENCE_CSV", previous_facility_reference_csv)

    payload = json.loads(health_body.decode("utf-8"))
    if health_status != 200 or payload.get("status") != "ok":
        raise RuntimeError("Hosted scaffold health check did not return ok.")
    if root_status != 200 or b"CCLD-only public-record review workspace" in root_body:
        raise RuntimeError("Hosted scaffold app shell returned removed workspace intro text.")
    if b"Facility intake" not in root_body:
        raise RuntimeError("Hosted scaffold app shell did not return facility intake label.")
    if b"Skip to main CCLD facility lookup content" not in root_body:
        raise RuntimeError("Hosted scaffold app shell did not return skip navigation.")
    if (
        b"Find the Facility ID"
        not in root_body
    ):
        raise RuntimeError("Hosted scaffold app shell did not return review session orientation.")
    if (
        records_status != 200
        or b"Fixture/sample source record list" not in records_body
        or b"Jurisdictions represented" not in records_body
    ):
        raise RuntimeError("Hosted scaffold source-record shell did not return the sample list.")
    if (
        facilities_status != 200
        or b"Read-only facility master sample view" not in facilities_body
        or b"Committed tiny public-source facility fixture rows" not in facilities_body
    ):
        raise RuntimeError("Hosted scaffold facility sample shell did not return the fixture list.")
    if (
        ccld_status != 200
        or b"Request Records" not in ccld_body
        or b'for="facility-search-input"' not in ccld_body
        or b"facility-suggestion-list" not in ccld_body
        or b"Which facility should be reviewed?" not in ccld_body
        or b"Use this Facility ID" not in ccld_body
        or b"Search by name, Facility ID, city, county, ZIP" not in ccld_body
        or b'<header class="civic-header">' not in ccld_body
        or b'<nav class="civic-nav" aria-label="Primary navigation">' not in ccld_body
        or b"Skip to main CCLD request content" not in ccld_body
    ):
        raise RuntimeError("Hosted scaffold CCLD request shell did not return the request page.")
    if (
        ccld_retrieval_history_status != 200
        or b"Job diagnostics" not in ccld_retrieval_history_body
        or b"No Request Records jobs have been submitted" not in ccld_retrieval_history_body
        or b"Controlled retrieval setup is missing" not in ccld_retrieval_history_body
        or b"Submit or change Request Records" not in ccld_retrieval_history_body
        or b"Send feedback" not in ccld_retrieval_history_body
        or b"Report confusing retrieval progress" in ccld_retrieval_history_body
    ):
        raise RuntimeError("Hosted scaffold retrieval job history did not return safe guidance.")
    if (
        ccld_retrieval_detail_status != 404
        or b"Job diagnostics detail not found" not in ccld_retrieval_detail_body
        or b"Return to job diagnostics" not in ccld_retrieval_detail_body
        or b"Submit or change a CCLD request" not in ccld_retrieval_detail_body
    ):
        raise RuntimeError("Hosted scaffold retrieval job detail did not return safe not-found.")
    if (
        ccld_retrieval_detail_invalid_status != 400
        or b"Job diagnostics detail needs a valid job ID"
        not in ccld_retrieval_detail_invalid_body
        or b"Return to job diagnostics" not in ccld_retrieval_detail_invalid_body
    ):
        raise RuntimeError(
            "Hosted scaffold retrieval job detail did not return safe invalid state."
        )
    if (
        ccld_queue_status != 200
        or (
            b"Complaint records ready for attorney review" not in ccld_queue_body
            and b"CCLD review queue" not in ccld_queue_body
        )
        or b"Do this next" not in ccld_queue_body
        or b"32-CR-20220407124448" not in ccld_queue_body
        or b"Review packet readiness before copying or printing" not in ccld_queue_body
    ):
        raise RuntimeError("Hosted scaffold CCLD request queue did not return triage guidance.")
    if (
        ccld_filtered_status != 200
        or b"Filtered queue recovery" not in ccld_filtered_body
        or b"No records match this active reviewer-created status filter"
        not in ccld_filtered_body
        or b"Show all reviewer statuses for this facility/date request"
        not in ccld_filtered_body
        or b"same facility/date request context" not in ccld_filtered_body
    ):
        raise RuntimeError("Hosted scaffold CCLD filtered queue did not return recovery guidance.")
    if (
        ccld_no_match_status != 200
        or b"No loaded records found" not in ccld_no_match_body
        or b"No loaded complaint records matched this facility and date range"
        not in ccld_no_match_body
        or b"A no-match result is not proof that no public CCLD record exists"
        not in ccld_no_match_body
        or b"Adjust date range" not in ccld_no_match_body
        or b"Send feedback" not in ccld_no_match_body
    ):
        raise RuntimeError("Hosted scaffold CCLD no-match result did not return load guidance.")
    if (
        ccld_retrieval_setup_status != 503
        or b"Request Records setup required" not in ccld_retrieval_setup_body
        or b"No Request Records job was created" not in ccld_retrieval_setup_body
        or b"Operator setup checklist" not in ccld_retrieval_setup_body
        or b"Send feedback" not in ccld_retrieval_setup_body
    ):
        raise RuntimeError("Hosted scaffold retrieval setup state did not return safe guidance.")
    if (
        ccld_retrieval_success_status != 200
        or b"Complaint records ready for attorney review" not in ccld_retrieval_success_body
        or b"Completed" not in ccld_retrieval_success_body
        or b"Records imported" not in ccld_retrieval_success_body
            or b"Open review queue" not in ccld_retrieval_success_body
        or b"Open job diagnostics" not in ccld_retrieval_success_body
            or b"View job details" not in ccld_retrieval_success_body
    ):
        raise RuntimeError("Hosted scaffold mock retrieval did not return completed status.")
    if (
        ccld_retrieval_history_after_status != 200
        or b"Job diagnostics" not in ccld_retrieval_history_after_body
        or b"View job details" not in ccld_retrieval_history_after_body
        or b"Review imported records in the CCLD queue" not in ccld_retrieval_history_after_body
    ):
        raise RuntimeError("Hosted scaffold mock retrieval did not appear in history.")
    if (
        ccld_retrieval_success_detail_status != 200
        or b"Job diagnostics detail" not in ccld_retrieval_success_detail_body
        or b"Completed" not in ccld_retrieval_success_detail_body
        or b"Records imported" not in ccld_retrieval_success_detail_body
        or b"Review imported records in the CCLD queue"
        not in ccld_retrieval_success_detail_body
    ):
        raise RuntimeError("Hosted scaffold mock retrieval detail did not return safe status.")
    if (
        ccld_facilities_status != 200
        or b"Find a facility" not in ccld_facilities_body
        or b"Skip to main CCLD facility lookup content" not in ccld_facilities_body
    ):
        raise RuntimeError("Hosted scaffold CCLD facility lookup did not return results.")
    if (
        help_status != 200
        or b"Help" not in help_body
            or b"Find a facility" not in help_body
        or b"Request Records" not in help_body
            or b"Review Queue" not in help_body
        or b"Reviewer Detail" not in help_body
            or b"Packet preview and preparation draft" not in help_body
    ):
        raise RuntimeError("Hosted scaffold CCLD help page did not return guided help.")
    if (
            feedback_status != 200
            or b"Send feedback" not in feedback_body
                or b"Send RecordsTracker feedback" not in feedback_body
            or b"Do not include private material" not in feedback_body
            or b"Feedback cannot be sent directly from this page" not in feedback_body
            or b"Submit feedback" not in feedback_body
        ):
        raise RuntimeError("Hosted scaffold feedback page did not return safe form state.")
    if (
        reviewer_status != 200
        or b"Complaint records ready for review" not in reviewer_body
        or b"Complaint worklist" not in reviewer_body
        or b"Skip to main reviewer content" not in reviewer_body
    ):
        raise RuntimeError("Hosted scaffold reviewer UI shell did not return the seeded list.")
    if (
        reviewer_detail_status != 200
        or b"Complaint overview" not in reviewer_detail_body
        or b"Why this may need closer review" not in reviewer_detail_body
        or b"inline-glossary-term" not in reviewer_detail_body
            or b"Status and note" not in reviewer_detail_body
        or b"Key dates" not in reviewer_detail_body
        or b"Allegations and findings" not in reviewer_detail_body
        or b"Reviewer-created notes and status history" in reviewer_detail_body
        or b"Source-derived value checks" in reviewer_detail_body
        or b"Full source-derived" + b" fields" in reviewer_detail_body
        or b"Technical and operator details" in reviewer_detail_body
        or b"Source traceability" in reviewer_detail_body
        or b"How to read this record" in reviewer_detail_body
        or b"Field-note guidance" in reviewer_detail_body
        or b"Check source" in reviewer_detail_body
        or b"Open CCLD source record" not in reviewer_detail_body
        or b"Return to review queue" not in reviewer_detail_body
        or b"32-CR-20220407124448" not in reviewer_detail_body
    ):
        raise RuntimeError("Hosted scaffold reviewer detail did not return usable guidance.")
    packet_blocked_terms = (
        b"Facility" + b" / license",
        b"Facility" + b"/license",
        b"Facility" + b"/License",
        b"facility" + b"/license",
        b"license" + b" number",
        b"source-derived" + b" fields",
        b"source-derived" + b" values",
        b"source-derived" + b" records",
        b"raw" + b" artifact",
        b"connector" + b" metadata",
        b"raw" + b" SHA-256",
        b"source" + b" traceability",
        b"source" + b"-traceability",
        b"Source" + b" Traceability",
        b"Full source" + b"-traceability details",
    )
    if (
        packet_preview_status != 200
        or b"Packet preview" not in packet_preview_body
        or b"Readiness checks" not in packet_preview_body
        or b"CCLD source availability" not in packet_preview_body
        or b"Notes/status summary" not in packet_preview_body
        or b"Copy-ready brief" not in packet_preview_body
        or b"Packet readiness checklist" not in packet_preview_body
        or b"Included complaint records" not in packet_preview_body
        or b"Before copying or printing" not in packet_preview_body
        or b"Needs date/source review" not in packet_preview_body
        or b"Review dates and source link" not in packet_preview_body
        or any(term in packet_preview_body for term in packet_blocked_terms)
        or b"Operator/runtime details" in packet_preview_body
        or b"Technical runtime details" in packet_preview_body
    ):
        raise RuntimeError("Hosted scaffold review packet preview did not return safe guidance.")
    if (
        packet_draft_status != 200
        or b"Attorney Review Packet Draft" not in packet_draft_body
        or b"Use browser copy or print only after review" not in packet_draft_body
        or b"Copyable packet summary" not in packet_draft_body
        or b"Copy-ready attorney review brief" not in packet_draft_body
        or b"Attorney review readiness checklist" not in packet_draft_body
        or b"Before using this draft" not in packet_draft_body
        or b"No export file is generated" not in packet_draft_body
        or b"Facility ID" not in packet_draft_body
        or any(term in packet_draft_body for term in packet_blocked_terms)
    ):
        raise RuntimeError("Hosted scaffold review packet draft did not return safe guidance.")
    if (
        packet_draft_empty_status != 200
        or b"No facility/date packet context was supplied" not in packet_draft_empty_body
        or b"Open Request Records" not in packet_draft_empty_body
        or b"Open Review queue" not in packet_draft_empty_body
    ):
        raise RuntimeError(
            "Hosted scaffold review packet draft did not return safe context-needed guidance."
        )
    if (
        reviewer_note_status != 200
        or b"Notes/status saved" not in reviewer_note_body
        or b"Note saved for this record." not in reviewer_note_body
        or b"What changed" not in reviewer_note_body
        or b"What did not change" not in reviewer_note_body
        or b"Return to facility queue" not in reviewer_note_body
        or b"Open next flagged record" not in reviewer_note_body
        or b"Saved notes and statuses" not in reviewer_note_body
        or b"feedback details" in reviewer_note_body
    ):
        raise RuntimeError("Hosted scaffold reviewer note did not return confirmation.")
    if (
        reviewer_saved_status != 200
        or b"Notes/status saved" not in reviewer_saved_status_body
        or b"Status saved for this record." not in reviewer_saved_status_body
        or b"What changed" not in reviewer_saved_status_body
        or b"What did not change" not in reviewer_saved_status_body
        or b"Return to facility queue" not in reviewer_saved_status_body
        or b"Open next flagged record" not in reviewer_saved_status_body
        or b"Saved notes and statuses" not in reviewer_saved_status_body
        or b"feedback details" in reviewer_saved_status_body
    ):
        raise RuntimeError("Hosted scaffold reviewer status did not return confirmation.")
    return payload if isinstance(payload, dict) else {}


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the hosted scaffold smoke check.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)

    payload: dict[str, Any] = run_scaffold_smoke_check(args.host, args.port)
    print(f"Hosted scaffold smoke check passed: {json.dumps(payload, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
