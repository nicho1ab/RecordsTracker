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
        check_python_package_or_command("pytest", "pytest", "pytest for scaffold tests"),
        check_python_package_or_command("ruff", "ruff", "ruff for lint checks"),
        check_python_package_or_command("mypy", "mypy", "mypy for type checks"),
        check_importable("alembic", "Alembic migration tooling"),
        check_importable("sqlalchemy", "SQLAlchemy migration runtime"),
        check_importable("psycopg", "PostgreSQL driver for future hosted tester wiring"),
        informational_boundary("Node/npm", "Not required for the Python stdlib hosted scaffold."),
        informational_boundary(
            "Docker",
            "Not required for local hosted scaffold setup or validation.",
        ),
        informational_boundary(
            "PostgreSQL server",
            "Not required for scaffold import, smoke, or boundary tests; "
            "required later to run migrations.",
        ),
        informational_boundary(
            "QNAP/cloud/public URL",
            "Deferred and not required for local scaffold work.",
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
            "Smoke command: .\\scripts\\smoke-hosted-scaffold.ps1",
            "Focused tests: pytest tests/unit/test_hosted_app_scaffold.py",
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