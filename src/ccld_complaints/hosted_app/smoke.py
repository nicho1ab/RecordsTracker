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
    os.environ["CCLD_HOSTED_TESTER_AUTH_MODE"] = "local-dev"
    os.environ["CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH"] = "enabled"
    os.environ["CCLD_HOSTED_PAGE_DATA_MODE"] = "fixture-demo"
    os.environ["CCLD_RETRIEVAL_ENABLED"] = "disabled"
    os.environ["CCLD_RETRIEVAL_RAW_DIR"] = ""
    os.environ["CCLD_RETRIEVAL_DEMO_MODE"] = ""
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

    payload = json.loads(health_body.decode("utf-8"))
    if health_status != 200 or payload.get("status") != "ok":
        raise RuntimeError("Hosted scaffold health check did not return ok.")
    if root_status != 200 or b"Attorney public-record review workspace" not in root_body:
        raise RuntimeError("Hosted scaffold app shell did not return the guided launch notice.")
    if b"Skip to main CCLD review content" not in root_body:
        raise RuntimeError("Hosted scaffold app shell did not return skip navigation.")
    if (
        b"Start a facility complaint review"
        not in root_body
    ):
        raise RuntimeError("Hosted scaffold app shell did not return review session orientation.")
    if (
        records_status != 200
        or b"Fixture/sample source record list" not in records_body
        or b"Sample source traceability summary" not in records_body
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
        or b"Retrieve complaint records" not in ccld_body
        or b'for="facility-search-input"' not in ccld_body
        or b"facility-suggestion-list" not in ccld_body
        or b"Which facility should be reviewed?" not in ccld_body
        or b"Confirm facility" not in ccld_body
        or b"Search by name, license number, city, ZIP, type, or status." not in ccld_body
        or b"Retrieval not configured" not in ccld_body
        or b"Skip to main CCLD request content" not in ccld_body
    ):
        raise RuntimeError("Hosted scaffold CCLD request shell did not return the request page.")
    if (
        ccld_retrieval_history_status != 200
        or b"Retrieval status center" not in ccld_retrieval_history_body
        or b"No retrieval jobs have been submitted" not in ccld_retrieval_history_body
        or b"Controlled retrieval setup is missing" not in ccld_retrieval_history_body
        or b"Submit or change retrieval request" not in ccld_retrieval_history_body
        or b"Send tester feedback" not in ccld_retrieval_history_body
    ):
        raise RuntimeError("Hosted scaffold retrieval job history did not return safe guidance.")
    if (
        ccld_retrieval_detail_status != 404
        or b"Retrieval job detail not found" not in ccld_retrieval_detail_body
        or b"Return to retrieval job history" not in ccld_retrieval_detail_body
        or b"Submit or change a CCLD request" not in ccld_retrieval_detail_body
    ):
        raise RuntimeError("Hosted scaffold retrieval job detail did not return safe not-found.")
    if (
        ccld_retrieval_detail_invalid_status != 400
        or b"Retrieval job detail needs a valid job ID"
        not in ccld_retrieval_detail_invalid_body
        or b"Return to retrieval job history" not in ccld_retrieval_detail_invalid_body
    ):
        raise RuntimeError(
            "Hosted scaffold retrieval job detail did not return safe invalid state."
        )
    if (
        ccld_queue_status != 200
        or b"CCLD review queue" not in ccld_queue_body
        or b"source traceability" not in ccld_queue_body
        or b"Selected request context" not in ccld_queue_body
        or b"Change facility/date criteria for this request" not in ccld_queue_body
        or b"Queue triage summary" not in ccld_queue_body
        or b"Table view and queue guidance" not in ccld_queue_body
        or b"Suggested next record to open" not in ccld_queue_body
        or b"Open local/test packet preview" not in ccld_queue_body
        or b"Copy details for feedback" not in ccld_queue_body
        or b"Advanced retrieval and local load actions" not in ccld_queue_body
    ):
        raise RuntimeError("Hosted scaffold CCLD request queue did not return triage guidance.")
    if (
        ccld_filtered_status != 200
        or b"Filtered queue recovery" not in ccld_filtered_body
        or b"selected reviewer-status filter hides all queue rows" not in ccld_filtered_body
        or b"Show all queue records for this request" not in ccld_filtered_body
        or b"same facility/date request context" not in ccld_filtered_body
    ):
        raise RuntimeError("Hosted scaffold CCLD filtered queue did not return recovery guidance.")
    if (
        ccld_no_match_status != 200
        or (
            b"No loaded complaint records match this request yet" not in ccld_no_match_body
            and b"Candidates may be outside the selected date range" not in ccld_no_match_body
        )
        or b"How to interpret this no-match result" not in ccld_no_match_body
        or b"currently loaded local/test source-derived rows only" not in ccld_no_match_body
        or b"outside-browser live fetch and artifact-builder workflow" not in ccld_no_match_body
        or b"not a public-source absence" not in ccld_no_match_body
    ):
        raise RuntimeError("Hosted scaffold CCLD no-match result did not return load guidance.")
    if (
        ccld_retrieval_setup_status != 503
        or b"Controlled CCLD retrieval setup required" not in ccld_retrieval_setup_body
        or b"No retrieval job was created" not in ccld_retrieval_setup_body
        or b"Operator setup checklist" not in ccld_retrieval_setup_body
        or b"Send tester feedback" not in ccld_retrieval_setup_body
    ):
        raise RuntimeError("Hosted scaffold retrieval setup state did not return safe guidance.")
    if (
        ccld_retrieval_success_status != 200
        or b"Complaint records ready for attorney review" not in ccld_retrieval_success_body
        or b"Completed" not in ccld_retrieval_success_body
        or b"Records imported" not in ccld_retrieval_success_body
            or b"Open review queue" not in ccld_retrieval_success_body
        or b"View retrieval job history" not in ccld_retrieval_success_body
            or b"View job details" not in ccld_retrieval_success_body
    ):
        raise RuntimeError("Hosted scaffold mock retrieval did not return completed status.")
    if (
        ccld_retrieval_history_after_status != 200
        or b"Retrieval status center" not in ccld_retrieval_history_after_body
        or b"View retrieval job details" not in ccld_retrieval_history_after_body
        or b"Review imported records in the CCLD queue" not in ccld_retrieval_history_after_body
    ):
        raise RuntimeError("Hosted scaffold mock retrieval did not appear in history.")
    if (
        ccld_retrieval_success_detail_status != 200
        or b"Retrieval job detail" not in ccld_retrieval_success_detail_body
        or b"Completed" not in ccld_retrieval_success_detail_body
        or b"Records imported" not in ccld_retrieval_success_detail_body
        or b"Review imported records in the CCLD queue"
        not in ccld_retrieval_success_detail_body
    ):
        raise RuntimeError("Hosted scaffold mock retrieval detail did not return safe status.")
    if (
        ccld_facilities_status != 200
        or b"Find a facility" not in ccld_facilities_body
        or b"Synthetic Orchard Child Care" not in ccld_facilities_body
        or b"Review this facility" not in ccld_facilities_body
        or b"Skip to main CCLD facility lookup content" not in ccld_facilities_body
    ):
        raise RuntimeError("Hosted scaffold CCLD facility lookup did not return results.")
    if (
        help_status != 200
        or b"Help" not in help_body
            or b"How to review a facility" not in help_body
        or b"What review flags mean" not in help_body
        or b"How source traceability works" not in help_body
            or b"What the app does not prove" not in help_body
    ):
        raise RuntimeError("Hosted scaffold CCLD help page did not return guided help.")
    if (
        feedback_status != 200
        or b"Send feedback" not in feedback_body
        or b"What issue should be reported?" not in feedback_body
        or b"Do not include private material" not in feedback_body
        or b"GitHub issue intake is not configured" not in feedback_body
        or b"Submit feedback" not in feedback_body
    ):
        raise RuntimeError("Hosted scaffold feedback page did not return safe form state.")
    if (
        reviewer_status != 200
        or b"Complaint records ready for review" not in reviewer_body
            or b"Worklist" not in reviewer_body
        or b"Skip to main reviewer content" not in reviewer_body
    ):
        raise RuntimeError("Hosted scaffold reviewer UI shell did not return the seeded list.")
    if (
        reviewer_detail_status != 200
        or b"Complaint overview" not in reviewer_detail_body
        or b"Record review action" not in reviewer_detail_body
        or b"Key dates and finding" not in reviewer_detail_body
        or b"Record summary" not in reviewer_detail_body
        or b"Selected complaint source traceability fields" not in reviewer_detail_body
        or b"Source-confidence cues" not in reviewer_detail_body
        or b"Field-note guidance" not in reviewer_detail_body
        or b"Cautious wording for reviewer-created notes/status" not in reviewer_detail_body
        or b"not a source-confidence score" not in reviewer_detail_body
        or b"not available in this local/test record" not in reviewer_detail_body
        or b"does not make legal, facility-wide" not in reviewer_detail_body
        or b"Feedback clues for this record" not in reviewer_detail_body
        or b"Record-specific feedback handoff" not in reviewer_detail_body
        or b"Manual feedback checklist bridge" not in reviewer_detail_body
        or b"existing manual feedback checklist" not in reviewer_detail_body
        or b"same checklist for queue-level observations" not in reviewer_detail_body
        or b"Source traceability observations" not in reviewer_detail_body
        or b"suggested next record" not in reviewer_detail_body
        or b"not a persisted assignment" not in reviewer_detail_body
        or b"First-run detail steps" not in reviewer_detail_body
    ):
        raise RuntimeError("Hosted scaffold reviewer detail did not return usable guidance.")
    if (
        packet_preview_status != 200
        or b"Local/test packet preparation preview" not in packet_preview_body
        or b"Traceability readiness" not in packet_preview_body
        or b"Reviewer-created state summary" not in packet_preview_body
        or b"Included complaint records" not in packet_preview_body
        or b"Why included" not in packet_preview_body
        or b"not a legal report" not in packet_preview_body
        or b"No export file is generated" not in packet_preview_body
    ):
        raise RuntimeError("Hosted scaffold review packet preview did not return safe guidance.")
    if (
        packet_draft_status != 200
        or b"Attorney Review Packet Draft" not in packet_draft_body
        or b"Use browser copy or print only after review" not in packet_draft_body
        or b"Copyable packet summary" not in packet_draft_body
        or b"What this draft does not prove" not in packet_draft_body
        or b"No export file is generated" not in packet_draft_body
    ):
        raise RuntimeError("Hosted scaffold review packet draft did not return safe guidance.")
    if (
        packet_draft_empty_status != 200
        or b"No facility/date packet context was supplied" not in packet_draft_empty_body
        or b"Open Retrieve" not in packet_draft_empty_body
        or b"Open Review queue" not in packet_draft_empty_body
    ):
        raise RuntimeError(
            "Hosted scaffold review packet draft did not return safe context-needed guidance."
        )
    if (
        reviewer_note_status != 200
        or b"Reviewer-created state saved" not in reviewer_note_body
        or b"Reviewer note saved for this record" not in reviewer_note_body
        or b"What changed" not in reviewer_note_body
        or b"What did not change" not in reviewer_note_body
        or b"Return to facility queue" not in reviewer_note_body
        or b"Open next priority record" not in reviewer_note_body
        or b"Queue progress and note/status cues are derived" not in reviewer_note_body
        or b"suggested next record is not a persisted assignment" not in reviewer_note_body
        or b"field-note wording" not in reviewer_note_body
        or b"manual feedback checklist" not in reviewer_note_body
    ):
        raise RuntimeError("Hosted scaffold reviewer note did not return confirmation.")
    if (
        reviewer_saved_status != 200
        or b"Reviewer-created state saved" not in reviewer_saved_status_body
        or b"Reviewer status saved for this record" not in reviewer_saved_status_body
        or b"What changed" not in reviewer_saved_status_body
        or b"What did not change" not in reviewer_saved_status_body
        or b"Return to facility queue" not in reviewer_saved_status_body
        or b"Open next priority record" not in reviewer_saved_status_body
        or b"Queue progress and note/status cues are derived" not in reviewer_saved_status_body
        or b"suggested next record is not a persisted assignment" not in reviewer_saved_status_body
        or b"field-note wording" not in reviewer_saved_status_body
        or b"manual feedback checklist" not in reviewer_saved_status_body
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
