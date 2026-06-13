from __future__ import annotations

import json

from ccld_complaints.hosted_app.app import health_response, render_app_shell, route_response
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


def test_smoke_check_hits_health_route_and_app_shell() -> None:
    payload = run_scaffold_smoke_check()

    assert payload["status"] == "ok"
    assert payload["scaffold_only"] is True