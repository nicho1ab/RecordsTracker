from __future__ import annotations

from ccld_complaints.hosted_app.local_check import (
    LocalCheck,
    check_python_version,
    format_text_report,
    has_failed_required_check,
    informational_boundary,
)


def test_python_version_check_requires_python_311_or_newer() -> None:
    assert check_python_version(3, 11, 0).status == "pass"
    assert check_python_version(3, 14, 3).status == "pass"

    failed_check = check_python_version(3, 10, 9)

    assert failed_check.status == "fail"
    assert failed_check.required is True
    assert "older than 3.11" in failed_check.detail


def test_failed_required_check_ignores_informational_boundaries() -> None:
    report = [
        LocalCheck("Required", "pass", "available", True),
        informational_boundary("Docker", "Not required."),
    ]

    assert has_failed_required_check(report) is False
    assert has_failed_required_check([LocalCheck("Required", "fail", "missing", True)]) is True


def test_text_report_includes_commands_and_non_install_boundary() -> None:
    report = [
        LocalCheck("Python version", "pass", "Python 3.11.0 meets >= 3.11.", True),
        informational_boundary("Node/npm", "Not required for the Python stdlib hosted scaffold."),
    ]

    text = format_text_report(report)

    assert "Hosted scaffold local setup check" in text
    assert "This check does not install software" in text
    assert "does not require admin rights" in text
    assert ".\\scripts\\run-hosted-scaffold.ps1 -Port 8000" in text
    assert ".\\scripts\\smoke-hosted-scaffold.ps1" in text
    assert "pytest tests/unit/test_hosted_app_scaffold.py" in text
    assert "tests/unit/test_hosted_auth_provider_integration_plan.py" in text
    assert "tests/unit/test_hosted_reviewer_created_state.py" in text
    assert "tests/unit/test_hosted_reviewer_created_state_routes.py" in text
    assert "tests/unit/test_hosted_audit_coverage_plan.py" in text
    assert "tests/unit/test_hosted_audit_events.py" in text
    assert "tests/unit/test_hosted_audit_event_routes.py" in text
    assert "tests/unit/test_hosted_reset_reload_dry_run.py" in text
    assert "tests/unit/test_hosted_reset_reload_execution_plan.py" in text
    assert "tests/unit/test_hosted_reset_reload_operational_metadata.py" in text
    assert "tests/unit/test_hosted_reset_reload_planning_routes.py" in text
    assert "tests/unit/test_hosted_reviewer_ui.py" in text


def test_text_report_can_include_database_scaffold_boundary() -> None:
    report = [
        LocalCheck("Alembic migration tooling", "pass", "alembic is importable.", True),
        informational_boundary(
            "PostgreSQL server",
            "Not required for local smoke, boundary tests, or artifact parsing tests.",
        ),
    ]

    text = format_text_report(report)

    assert "Alembic migration tooling" in text
    assert "PostgreSQL server" in text
    assert "artifact parsing tests" in text