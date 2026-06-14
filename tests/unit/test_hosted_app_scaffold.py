from __future__ import annotations

import json

from ccld_complaints.hosted_app.app import (
    get_sample_source_record,
    health_response,
    render_app_shell,
    route_response,
)
from ccld_complaints.hosted_app.smoke import run_scaffold_smoke_check


def test_health_response_marks_scaffold_only() -> None:
    payload = health_response()

    assert payload["status"] == "ok"
    assert payload["service"] == "hosted-tester-mvp-scaffold"
    assert payload["scaffold_only"] is True
    assert payload["review_workflows_implemented"] is False
    assert payload["authentication_implemented"] is False
    assert payload["source_data_loaded"] is False


def test_app_shell_labels_placeholder_boundaries() -> None:
    html = render_app_shell()
    normalized_html = " ".join(html.split())

    assert "<main>" in html
    assert "Scaffold only: not a functioning reviewer workflow yet." in html
    assert "No records are loaded" in html
    assert "Authentication and authorization" in html
    assert "QNAP, Azure, AWS, public URLs, or deployment" in normalized_html
    assert "Sample source-derived records" in html


def test_routes_return_shell_health_and_not_found() -> None:
    root_status, root_content_type, root_body = route_response("/")
    health_status, health_content_type, health_body = route_response("/health")
    api_status, api_content_type, api_body = route_response("/api/health")
    missing_status, missing_content_type, missing_body = route_response("/missing")

    assert root_status == 200
    assert root_content_type == "text/html; charset=utf-8"
    assert b"not a functioning reviewer workflow yet" in root_body
    assert health_status == 200
    assert health_content_type == "application/json; charset=utf-8"
    assert json.loads(health_body)["status"] == "ok"
    assert api_status == 200
    assert api_content_type == "application/json; charset=utf-8"
    assert json.loads(api_body)["service"] == "hosted-tester-mvp-scaffold"
    assert missing_status == 404
    assert missing_content_type == "text/plain; charset=utf-8"
    assert missing_body == b"Not found"


def test_source_record_list_route_labels_sample_read_only_scope() -> None:
    status, content_type, body = route_response("/source-records")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Sample source-derived records" in html
    assert "Fixture/sample data only" in html
    assert "No live public-source data is loaded" in html
    assert "No reviewer workflow is active" in html
    assert "no authentication is implemented" in html
    assert "no reviewer-created state is persisted" in html
    assert "Source-derived sample records and future reviewer-created state remain separate" in (
        normalized_html
    )
    assert "Raw SHA-256" in html
    assert "sample-complaint-001" in html


def test_source_record_detail_route_displays_traceability_fields() -> None:
    status, content_type, body = route_response("/source-records/sample-complaint-001")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Read-only sample source-derived detail" in html
    assert "Sample source URL" in html
    assert "https://example.invalid/sample-ccld-source-document-001" in html
    assert "Raw SHA-256" in html
    assert "Connector name" in html
    assert "Retrieved at" in html
    assert "Extraction warning" in html
    assert "Sample-only value; not extracted from live public-source data." in html
    assert "Source-derived sample records and future reviewer-created state remain separate" in (
        normalized_html
    )


def test_unknown_source_record_detail_returns_not_found() -> None:
    status, content_type, body = route_response("/source-records/not-found")

    assert get_sample_source_record("not-found") is None
    assert status == 404
    assert content_type == "text/plain; charset=utf-8"
    assert body == b"Not found"


def test_smoke_check_hits_health_route_and_app_shell() -> None:
    payload = run_scaffold_smoke_check()

    assert payload["status"] == "ok"
    assert payload["scaffold_only"] is True