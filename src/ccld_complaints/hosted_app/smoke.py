from __future__ import annotations

import argparse
import json
import threading
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ccld_complaints.hosted_app.app import create_server, format_host


def _read_url(url: str) -> tuple[int, bytes]:
    with urlopen(url, timeout=5) as response:
        return response.status, response.read()


def _post_form_url(url: str, payload: dict[str, str]) -> tuple[int, bytes]:
    body = urlencode(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return response.status, response.read()


def run_scaffold_smoke_check(host: str = "127.0.0.1", port: int = 0) -> dict[str, object]:
    with create_server(host, port) as server:
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
            reviewer_status, reviewer_body = _read_url(f"{base_url}/reviewer")
            reviewer_detail_status, reviewer_detail_body = _read_url(
                f"{base_url}/reviewer/records/detail?"
                "source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448"
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
            help_status, help_body = _read_url(f"{base_url}/ccld/help")
        finally:
            server.shutdown()
            thread.join(timeout=5)

    payload = json.loads(health_body.decode("utf-8"))
    if health_status != 200 or payload.get("status") != "ok":
        raise RuntimeError("Hosted scaffold health check did not return ok.")
    if root_status != 200 or b"not a production reviewer workflow" not in root_body:
        raise RuntimeError("Hosted scaffold app shell did not return the placeholder notice.")
    if b"Skip to main CCLD review content" not in root_body:
        raise RuntimeError("Hosted scaffold app shell did not return skip navigation.")
    if b"Start a CCLD review session here" not in root_body:
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
        or b"CCLD record request" not in ccld_body
        or b"CCLD facility/license number" not in ccld_body
        or b"Find a CCLD facility" not in ccld_body
        or b"Review session path" not in ccld_body
        or b"Facility lookup helps fill the facility/license number" not in ccld_body
        or b"Reviewer-status filter" not in ccld_body
        or b"Confirm request context" not in ccld_body
        or b"validated CCLD load" not in ccld_body
        or b"Feedback guidance" not in ccld_body
        or b"Skip to main CCLD request content" not in ccld_body
    ):
        raise RuntimeError("Hosted scaffold CCLD request shell did not return the request page.")
    if (
        ccld_queue_status != 200
        or b"CCLD review queue" not in ccld_queue_body
        or b"check source traceability, source-confidence cues" not in ccld_queue_body
        or b"Confirm request context" not in ccld_queue_body
        or b"Request started from" not in ccld_queue_body
        or b"Change facility/date criteria for this request" not in ccld_queue_body
        or b"Queue triage summary" not in ccld_queue_body
        or b"Continue review guidance" not in ccld_queue_body
        or b"Suggested next record to open" not in ccld_queue_body
        or b"official workflow state" not in ccld_queue_body
        or b"source-confidence cues" not in ccld_queue_body
        or b"same manual feedback checklist for queue and reviewer-detail" not in ccld_queue_body
        or b"Copy tester feedback checklist" not in ccld_queue_body
        or b"Reviewer detail and note/status confirmation" not in ccld_queue_body
        or b"Manual-copy only" not in ccld_queue_body
        or b"First-run queue steps" not in ccld_queue_body
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
        or b"No matching local/test CCLD records found" not in ccld_no_match_body
        or b"How to interpret this no-match result" not in ccld_no_match_body
        or b"currently loaded local/test source-derived rows only" not in ccld_no_match_body
        or b"outside-browser live fetch and artifact-builder workflow" not in ccld_no_match_body
        or b"not a public-source absence" not in ccld_no_match_body
    ):
        raise RuntimeError("Hosted scaffold CCLD no-match result did not return load guidance.")
    if (
        ccld_facilities_status != 200
        or b"Find CCLD facility" not in ccld_facilities_body
        or b"Synthetic Orchard Child Care" not in ccld_facilities_body
        or b"Use this facility for CCLD request" not in ccld_facilities_body
        or b"Skip to main CCLD facility lookup content" not in ccld_facilities_body
    ):
        raise RuntimeError("Hosted scaffold CCLD facility lookup did not return results.")
    if (
        help_status != 200
        or b"How CCLD review works" not in help_body
        or b"CCLD review queue" not in help_body
        or b"Review session path" not in help_body
        or b"Feedback guidance" not in help_body
    ):
        raise RuntimeError("Hosted scaffold CCLD help page did not return guided help.")
    if (
        reviewer_status != 200
        or b"Local/test reviewer records" not in reviewer_body
        or b"Seeded source-derived review list" not in reviewer_body
        or b"Skip to main reviewer content" not in reviewer_body
    ):
        raise RuntimeError("Hosted scaffold reviewer UI shell did not return the seeded list.")
    if (
        reviewer_detail_status != 200
        or b"Local/test reviewer detail" not in reviewer_detail_body
        or b"Record summary" not in reviewer_detail_body
        or b"reviewer detail step of the same CCLD review session" not in reviewer_detail_body
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
        or b"suggested next record to continue" not in reviewer_detail_body
        or b"not a persisted assignment" not in reviewer_detail_body
        or b"First-run detail steps" not in reviewer_detail_body
    ):
        raise RuntimeError("Hosted scaffold reviewer detail did not return usable guidance.")
    if (
        reviewer_note_status != 200
        or b"Reviewer update saved" not in reviewer_note_body
        or b"Reviewer note saved for this record" not in reviewer_note_body
        or b"Return to CCLD request queue" not in reviewer_note_body
        or b"Return and refresh queue progress" not in reviewer_note_body
        or b"Queue progress and note/status cues are derived" not in reviewer_note_body
        or b"suggested next record is not a persisted assignment" not in reviewer_note_body
        or b"field-note wording" not in reviewer_note_body
        or b"manual feedback checklist" not in reviewer_note_body
    ):
        raise RuntimeError("Hosted scaffold reviewer note did not return confirmation.")
    if (
        reviewer_saved_status != 200
        or b"Reviewer update saved" not in reviewer_saved_status_body
        or b"Reviewer status saved for this record" not in reviewer_saved_status_body
        or b"Return to CCLD request queue" not in reviewer_saved_status_body
        or b"Return and refresh queue progress" not in reviewer_saved_status_body
        or b"Queue progress and note/status cues are derived" not in reviewer_saved_status_body
        or b"suggested next record is not a persisted assignment" not in reviewer_saved_status_body
        or b"field-note wording" not in reviewer_saved_status_body
        or b"manual feedback checklist" not in reviewer_saved_status_body
    ):
        raise RuntimeError("Hosted scaffold reviewer status did not return confirmation.")
    return payload if isinstance(payload, dict) else {}


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
