from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL_SCRIPT = (
    ROOT / "scripts" / "capture-hosted-operator-coverage-acceptance.ps1"
)
PYTHON_RUNNER = ROOT / "scripts" / "capture_hosted_operator_coverage_acceptance.py"


def test_acceptance_script_has_exact_modes_and_safe_hosted_auth_boundary() -> None:
    script = POWERSHELL_SCRIPT.read_text(encoding="utf-8")

    assert '[ValidateSet("LocalProductionAuth", "Hosted")]' in script
    assert "CCLD_OPERATOR_COVERAGE_ACCEPTANCE_HEADER_PROVIDER_COMMAND" in script
    assert "browser cookies and stored assertions are forbidden" in script
    assert "OutputRoot must remain under the ignored data/processed directory" in script
    assert 'featureBranch = "issues-453-477-hosted-coverage-runtime"' in script
    assert "LocalProductionAuth must run from branch $featureBranch" in script
    assert "Hosted mode requires -ExpectedCommitSha" in script
    assert 'if ($branch -ne "main")' in script
    assert "status --porcelain --untracked-files=all" in script
    assert "Hosted mode requires a clean worktree" in script
    assert "rev-parse refs/remotes/origin/main" in script
    assert "$commitSha -cne $ExpectedCommitSha" in script
    assert "$originMain -cne $ExpectedCommitSha" in script
    assert '"--commit-sha", $evidenceCommitSha' in script
    assert "EVIDENCE_PACKET_PATH=" not in script


def test_hosted_acceptance_documentation_preserves_direct_origin_boundary() -> None:
    guide = (
        ROOT / "docs/developer/operator-source-coverage-dashboard.md"
    ).read_text(encoding="utf-8")
    normalized_guide = " ".join(guide.split())

    for required in (
        "-ExpectedCommitSha <deployed-merge-sha>",
        "operator-approved direct origin or endpoint",
        "public Cloudflare edge URL",
        "client-supplied origin assertion",
        "operator-controlled network",
        "CCLD_OPERATOR_COVERAGE_ACCEPTANCE_HEADER_PROVIDER_COMMAND",
        "Cookies, browser profiles, stored assertions, service-token secrets",
        "not permission to bypass Access",
        "HEAD and local `origin/main` both equal",
        "evidence manifest records the validated deployed merge SHA",
    ):
        assert required in normalized_guide


def test_acceptance_runner_covers_routes_states_exports_and_automated_evidence() -> None:
    runner = PYTHON_RUNNER.read_text(encoding="utf-8")

    for route in (
        '"/operator/source-coverage"',
        '"/operator/source-coverage/facilities"',
        '"/operator/source-coverage/jobs"',
        '"/operator/source-coverage/export.csv"',
        '"/operator/source-coverage/facility-ids.csv?group={group}"',
    ):
        assert route in runner
    for group in (
        "changed",
        "unchanged",
        "warning",
        "failed",
        "missing_artifact",
        "retry_eligible",
    ):
        assert f'"{group}"' in runner
    for marker in (
        "summary-desktop",
        "summary-narrow",
        "summary-mobile",
        "200-percent-reflow",
        "keyboard-focus",
        "print-summary",
        "authorization-denial",
        "reviewer-tier-denial",
        "unavailable-package",
        "adjacent-first",
        "adjacent-second",
        "page.screenshot",
        "page.pdf",
        "route-assertions.csv",
        "route-status.csv",
        "manifest.json",
        "zipfile.ZipFile",
        "EVIDENCE_ZIP_SHA256=",
        "runtime-reconciliation.json",
        "runtime_sql_select_only",
    ):
        assert marker in runner


def test_acceptance_runner_never_reads_browser_auth_or_persists_headers() -> None:
    runner = PYTHON_RUNNER.read_text(encoding="utf-8").casefold()

    for forbidden in (
        "browser profile",
        "cf_authorization",
        "storage_state=",
        "cookies()",
        "document.cookie",
        "-method post",
    ):
        assert forbidden not in runner
    assert '"authentication_material_persisted": false' in runner
    assert '"browser_cookie_or_profile_accessed": false' in runner
    assert "completed.stdout" in runner
    assert "output was suppressed" in runner


def test_runtime_verifier_is_container_safe_and_read_only() -> None:
    verifier = (
        ROOT / "src/ccld_complaints/operator_coverage_runtime_verify.py"
    ).read_text(encoding="utf-8")

    assert "load_validated_coverage_package" in verifier
    assert "select(func.count())" in verifier
    assert "database_mutations_performed" in verifier
    assert "DEFAULT_PACKAGE_DIR" in verifier
    for forbidden in (".insert(", ".update(", ".delete(", "commit()", "rollback()"):
        assert forbidden not in verifier


def test_qnap_compose_and_example_publish_runtime_configuration() -> None:
    compose = (ROOT / "docker-compose.qnap.yml").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for variable in (
        "CCLD_OPERATOR_COVERAGE_ALLOWED_EMAILS",
        "CCLD_OPERATOR_COVERAGE_PACKAGE_DIR",
    ):
        assert variable in compose
        assert variable in example
    assert "/app/data/processed/source-to-screen-audit/runtime-current" in compose
    assert "/app/data/processed/source-to-screen-audit/runtime-current" in example


def test_acceptance_powershell_parses() -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell parsing is unavailable on this runner.")
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{POWERSHELL_SCRIPT.as_posix()}',[ref]$tokens,[ref]$errors) > $null; "
        "if($errors.Count){ $errors | Format-List; exit 1 }"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-Command", command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
