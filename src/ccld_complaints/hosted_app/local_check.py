from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from typing import Literal

MINIMUM_PYTHON = (3, 11)
CheckStatus = Literal["pass", "fail", "info"]


@dataclass(frozen=True)
class LocalCheck:
    name: str
    status: CheckStatus
    detail: str
    required: bool


def check_python_version(major: int, minor: int, micro: int) -> LocalCheck:
    version = f"{major}.{minor}.{micro}"
    minimum = f"{MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}"
    if (major, minor) >= MINIMUM_PYTHON:
        return LocalCheck("Python version", "pass", f"Python {version} meets >= {minimum}.", True)
    return LocalCheck("Python version", "fail", f"Python {version} is older than {minimum}.", True)


def check_importable(module_name: str, label: str) -> LocalCheck:
    if importlib.util.find_spec(module_name) is not None:
        return LocalCheck(label, "pass", f"{module_name} is importable.", True)
    return LocalCheck(label, "fail", f"{module_name} is not importable.", True)


def check_python_package_or_command(package_name: str, command_name: str, label: str) -> LocalCheck:
    if importlib.util.find_spec(package_name) is not None:
        return LocalCheck(label, "pass", f"Python package {package_name} is available.", True)
    if shutil.which(command_name) is not None:
        return LocalCheck(label, "pass", f"Command {command_name} is available.", True)
    return LocalCheck(
        label,
        "fail",
        f"Install development dependencies so {package_name} or {command_name} is available.",
        True,
    )


def informational_boundary(name: str, detail: str) -> LocalCheck:
    return LocalCheck(name, "info", detail, False)


def build_local_check_report() -> list[LocalCheck]:
    return [
        check_python_version(
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
        ),
        check_importable("ccld_complaints.hosted_app", "Hosted scaffold package"),
        check_importable("ccld_complaints.hosted_app.auth", "Hosted auth boundary package"),
        check_importable(
            "ccld_complaints.hosted_app.auth_provider_integration_plan",
            "Hosted auth provider integration planning package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.source_derived_routes",
            "Hosted source-derived API route package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.reviewer_workflow_shell",
            "Hosted reviewer workflow shell package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.reviewer_ui",
            "Hosted reviewer UI shell package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.ccld_record_request_ui",
            "Hosted CCLD record request UI package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.ccld_facility_lookup",
            "Hosted CCLD facility lookup package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.ccld_import_reload",
            "Hosted CCLD validated import/reload package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.ccld_retrieval_jobs",
            "Hosted controlled CCLD retrieval job package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.reviewer_created_state",
            "Hosted reviewer-created state scaffold package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.reviewer_created_state_routes",
            "Hosted reviewer-created state API route package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.audit_events",
            "Hosted audit event scaffold package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.audit_coverage_plan",
            "Hosted audit coverage planning package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.audit_event_routes",
            "Hosted audit event API route package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.reset_reload_dry_run",
            "Hosted reset/reload dry-run package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.reset_reload_execution_plan",
            "Hosted reset/reload execution-plan package",
        ),
        check_importable(
            "ccld_complaints.hosted_app.reset_reload_planning_routes",
            "Hosted reset/reload planning metadata API route package",
        ),
        check_python_package_or_command("pytest", "pytest", "pytest for scaffold tests"),
        check_python_package_or_command("ruff", "ruff", "ruff for lint checks"),
        check_python_package_or_command("mypy", "mypy", "mypy for type checks"),
        check_importable("alembic", "Alembic migration tooling"),
        check_importable("sqlalchemy", "SQLAlchemy migration runtime"),
        check_importable("psycopg", "PostgreSQL driver for future hosted tester wiring"),
        informational_boundary("Node/npm", "Not required for the Python stdlib hosted scaffold."),
        informational_boundary(
            "Docker",
            "Not required for local non-Docker scaffold setup or validation; "
            "used only for the optional QNAP-first runtime.",
        ),
        informational_boundary(
            "PostgreSQL server",
            "Not required for local smoke, boundary tests, or seeded artifact parsing tests; "
            "required to run migrations or load a hosted seeded corpus.",
        ),
        informational_boundary(
            "QNAP/cloud/public URL",
            "Not required for local scaffold work; public URLs and cloud deployment "
            "remain deferred.",
        ),
    ]


def has_failed_required_check(report: list[LocalCheck]) -> bool:
    return any(check.required and check.status == "fail" for check in report)


def format_text_report(report: list[LocalCheck]) -> str:
    lines = ["Hosted scaffold local setup check"]
    for check in report:
        lines.append(f"[{check.status.upper()}] {check.name}: {check.detail}")
    lines.extend(
        [
            "",
            "This check does not install software and does not require admin rights.",
            "Start command: .\\scripts\\run-hosted-scaffold.ps1 -Port 8000",
            "Complaint retrieval demo command: "
            ".\\scripts\\run-hosted-complaint-retrieval-demo.ps1 -Port 8000",
            "Smoke command: .\\scripts\\smoke-hosted-scaffold.ps1",
            "Focused tests: pytest tests/unit/test_hosted_app_scaffold.py "
            "tests/unit/test_hosted_seeded_corpus_import.py "
            "tests/unit/test_hosted_source_derived_reads.py "
            "tests/unit/test_hosted_auth_boundary.py "
            "tests/unit/test_hosted_auth_provider_integration_plan.py "
            "tests/unit/test_hosted_source_derived_routes.py "
            "tests/unit/test_hosted_reviewer_workflow_shell.py "
            "tests/unit/test_hosted_reviewer_ui.py "
            "tests/unit/test_hosted_ccld_facility_lookup.py "
            "tests/unit/test_hosted_ccld_record_request_ui.py "
            "tests/unit/test_hosted_ccld_retrieval_jobs.py "
            "tests/unit/test_hosted_app_scaffold.py "
            "tests/unit/test_hosted_ccld_import_reload.py "
            "tests/unit/test_hosted_ccld_artifact_builder.py "
            "tests/unit/test_hosted_reviewer_created_state.py "
            "tests/unit/test_hosted_reviewer_created_state_routes.py "
            "tests/unit/test_hosted_audit_coverage_plan.py "
            "tests/unit/test_hosted_audit_events.py "
            "tests/unit/test_hosted_audit_event_routes.py "
            "tests/unit/test_hosted_reset_reload_dry_run.py "
            "tests/unit/test_hosted_reset_reload_execution_plan.py "
            "tests/unit/test_hosted_reset_reload_operational_metadata.py "
            "tests/unit/test_hosted_reset_reload_planning_routes.py",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local hosted scaffold prerequisites.")
    parser.add_argument("--json", action="store_true", help="Print the check report as JSON.")
    args = parser.parse_args(argv)

    report = build_local_check_report()
    if args.json:
        print(json.dumps([asdict(check) for check in report], indent=2, sort_keys=True))
    else:
        print(format_text_report(report))
    return 1 if has_failed_required_check(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
