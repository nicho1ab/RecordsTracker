from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "verify-qnap-pilot-workflow.ps1"


def read_repo_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def parse_env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in read_repo_text(".env.example").splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        key, value = stripped_line.split("=", 1)
        values[key] = value
    return values


def run_verifier(*args: str) -> subprocess.CompletedProcess[str]:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise AssertionError("PowerShell is required for verifier behavior tests.")
    return subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(VERIFIER), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def write_env_file(path: Path, updates: dict[str, str]) -> Path:
    values = parse_env_example()
    values.update(updates)
    text = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def test_env_example_uses_placeholders_only() -> None:
    values = parse_env_example()

    assert values["CCLD_POSTGRES_DB"] == "ccld_records"
    assert values["CCLD_POSTGRES_USER"] == "ccld_app"
    assert values["CCLD_POSTGRES_PASSWORD"] == "replace-with-strong-local-password"
    assert values["CCLD_HOSTED_PORT"] == "8000"
    assert values["CCLD_HOSTED_PAGE_DATA_MODE"] == "postgres"
    assert values["GITHUB_FEEDBACK_REPO"] == ""
    assert values["GITHUB_FEEDBACK_TOKEN"] == ""
    assert values["GITHUB_FEEDBACK_DEFAULT_LABELS"] == ""
    assert values["CCLD_RETRIEVAL_ENABLED"] == "disabled"
    assert values["CCLD_RETRIEVAL_RAW_DIR"] == "/app/data/raw/ccld/retrieval"
    assert values["CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS"] == "366"
    assert values["CCLD_RETRIEVAL_PER_JOB_LIMIT"] == "5"
    assert values["CCLD_RETRIEVAL_RATE_LIMIT_PER_ACTOR"] == "3"
    assert values["CCLD_RETRIEVAL_TIMEOUT_SECONDS"] == "30"
    assert values["CCLD_RETRIEVAL_RETRY_LIMIT"] == "1"
    assert values["CCLD_RETRIEVAL_DEMO_MODE"] == ""
    assert values["CCLD_FACILITY_REFERENCE_CSV"] == ""

    env_text = read_repo_text(".env.example")
    for heading in (
        "QNAP pilot environment template",
        "Required: PostgreSQL container and app port",
        "Required for QNAP pilot: PostgreSQL-backed hosted pages",
        "Required for QNAP pilot: production auth boundary defaults",
        "Optional server-side GitHub Issues feedback intake",
        "Optional controlled server-side CCLD retrieval jobs",
        "Local-dev scaffold validation only",
        "Optional local/test CCLD facility reference CSV path",
    ):
        assert heading in env_text
    assert "ghp_" not in env_text
    assert "github_pat_" not in env_text
    assert "https://github.com/" not in env_text
    assert "C:\\" not in env_text
    assert "OneDrive" not in env_text


def test_qnap_verifier_passes_env_example_with_placeholder_warnings() -> None:
    result = run_verifier("-EnvFile", ".env.example")

    assert result.returncode == 0
    assert "[PASS] Required QNAP pilot env keys are present." in result.stdout
    assert "QNAP pilot mode keeps PostgreSQL page data" in result.stdout
    assert "Controlled retrieval is intentionally disabled" in result.stdout
    assert "placeholder" in (result.stdout + result.stderr)


def test_qnap_verifier_reports_missing_env_file(tmp_path: Path) -> None:
    missing_env = tmp_path / "missing.env"

    result = run_verifier("-EnvFile", str(missing_env), "-SkipComposeConfig")

    assert result.returncode != 0
    assert "not found" in (result.stderr + result.stdout)


def test_qnap_verifier_rejects_unsafe_local_dev_auth(tmp_path: Path) -> None:
    env_file = write_env_file(
        tmp_path / "local-dev.env",
        {
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        },
    )

    result = run_verifier("-EnvFile", str(env_file), "-SkipComposeConfig")

    assert result.returncode != 0
    output = result.stderr + result.stdout
    assert "production auth mode" in output
    assert "auth disabled" in output


def test_qnap_verifier_rejects_mock_success_without_override(tmp_path: Path) -> None:
    env_file = write_env_file(
        tmp_path / "mock-success.env",
        {"CCLD_RETRIEVAL_DEMO_MODE": "mock-success"},
    )

    result = run_verifier("-EnvFile", str(env_file), "-SkipComposeConfig")

    assert result.returncode != 0
    assert "requires -AllowLocalDevDemo" in (result.stderr + result.stdout)


def test_qnap_verifier_detects_retrieval_enabled_without_raw_storage(tmp_path: Path) -> None:
    env_file = write_env_file(
        tmp_path / "retrieval-no-raw.env",
        {
            "CCLD_RETRIEVAL_ENABLED": "enabled",
            "CCLD_RETRIEVAL_RAW_DIR": "",
        },
    )

    result = run_verifier("-EnvFile", str(env_file), "-SkipComposeConfig")

    assert result.returncode != 0
    assert "requires CCLD_RETRIEVAL_RAW_DIR" in (result.stderr + result.stdout)


def test_qnap_verifier_detects_partial_github_feedback(tmp_path: Path) -> None:
    env_file = write_env_file(
        tmp_path / "partial-feedback.env",
        {
            "GITHUB_FEEDBACK_REPO": "example/repo",
            "GITHUB_FEEDBACK_TOKEN": "",
        },
    )

    result = run_verifier("-EnvFile", str(env_file), "-SkipComposeConfig")

    assert result.returncode != 0
    assert "GitHub feedback must be either intentionally disabled" in (
        result.stderr + result.stdout
    )


def test_qnap_verifier_allows_github_feedback_disabled(tmp_path: Path) -> None:
    env_file = write_env_file(
        tmp_path / "feedback-disabled.env",
        {
            "GITHUB_FEEDBACK_REPO": "",
            "GITHUB_FEEDBACK_TOKEN": "",
        },
    )

    result = run_verifier("-EnvFile", str(env_file), "-SkipComposeConfig")

    assert result.returncode == 0
    assert "GitHub feedback intake is intentionally disabled" in result.stdout


def test_qnap_verifier_allows_retrieval_disabled_without_raw_storage(tmp_path: Path) -> None:
    env_file = write_env_file(
        tmp_path / "retrieval-disabled.env",
        {
            "CCLD_RETRIEVAL_ENABLED": "disabled",
            "CCLD_RETRIEVAL_RAW_DIR": "",
        },
    )

    result = run_verifier("-EnvFile", str(env_file), "-SkipComposeConfig")

    assert result.returncode == 0
    assert "Controlled retrieval is intentionally disabled" in result.stdout


def test_compose_runtime_uses_postgres_named_volumes_and_healthchecks() -> None:
    compose = read_repo_text("docker-compose.qnap.yml")

    assert "postgres:16-alpine" in compose
    assert "CCLD_HOSTED_TESTER_DATABASE_URL" in compose
    assert "CCLD_HOSTED_PAGE_DATA_MODE" in compose
    assert "GITHUB_FEEDBACK_REPO" in compose
    assert "GITHUB_FEEDBACK_TOKEN" in compose
    assert "CCLD_RETRIEVAL_ENABLED" in compose
    assert "CCLD_RETRIEVAL_RAW_DIR" in compose
    assert "CCLD_RETRIEVAL_PER_JOB_LIMIT" in compose
    assert "CCLD_RETRIEVAL_DEMO_MODE" in compose
    assert "postgresql+psycopg://${CCLD_POSTGRES_USER" in compose
    assert "alembic upgrade head" in compose
    assert "python -m ccld_complaints.hosted_app --host 0.0.0.0 --port 8000" in compose
    assert "pg_isready" in compose
    assert "http://127.0.0.1:8000/health" in compose
    assert "ccld_postgres_data:/var/lib/postgresql/data" in compose
    assert "ccld_processed_data:/app/data/processed" in compose
    assert "ccld_raw_data:/app/data/raw" in compose
    assert "ccld_logs:/app/data/logs" in compose
    assert "C:\\" not in compose
    assert "/share/" not in compose
    assert "qnap" not in compose.casefold()


def test_qnap_pilot_workflow_script_checks_env_compose_and_routes() -> None:
    script = read_repo_text("scripts/verify-qnap-pilot-workflow.ps1")

    for required_text in (
        "CCLD_POSTGRES_DB",
        "CCLD_POSTGRES_USER",
        "CCLD_POSTGRES_PASSWORD",
        "CCLD_HOSTED_PAGE_DATA_MODE",
        "CCLD_HOSTED_TESTER_AUTH_MODE",
        "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH",
        "CCLD_RETRIEVAL_ENABLED",
        "CCLD_RETRIEVAL_RAW_DIR",
        "CCLD_RETRIEVAL_DEMO_MODE",
        "mock-success",
        "AllowLocalDevDemo",
        "GitHub feedback must be either intentionally disabled",
        "CCLD_RETRIEVAL_ENABLED=enabled requires CCLD_RETRIEVAL_RAW_DIR",
        "Controlled retrieval is intentionally disabled",
        "docker compose -f",
        "pg_isready",
        "alembic current",
        "Invoke-WebRequest",
        "/ccld/retrieval/jobs",
        "/ccld/retrieval/jobs/detail?job_id=missing-job",
        "/reviewer",
    ):
        assert required_text in script

    normalized_script = " ".join(script.split())
    assert "QNAP pilot mode should use CCLD_HOSTED_PAGE_DATA_MODE=postgres" in (
        normalized_script
    )
    assert "mock-success demo mode requires local-dev auth" in normalized_script
    assert "does not make live CCLD retrieval" not in normalized_script
    assert "C:\\" not in script
    assert "function Test-PilotEnvValue" in script
    assert "function Test-NoHostSpecificPath" in script
    assert 'Stop-CheckFail "$Label must be a portable container path' in script
    assert "Test-SecretLikeExampleValue" in script
    assert "ghp_[A-Za-z0-9_]" in script
    assert "github_pat_[A-Za-z0-9_]" in script


def test_dockerfile_preserves_no_secret_portable_app_start() -> None:
    dockerfile = read_repo_text("Dockerfile")

    assert "FROM python:3.12-slim" in dockerfile
    assert "PYTHONPATH=/app/src" in dockerfile
    assert "COPY requirements.txt" in dockerfile
    assert "COPY migrations ./migrations" in dockerfile
    assert "COPY src ./src" in dockerfile
    assert "USER ccld" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--host" in dockerfile
    assert "0.0.0.0" in dockerfile
    assert ".env" not in dockerfile
    assert "CCLD_POSTGRES_PASSWORD" not in dockerfile


def test_qnap_runtime_doc_keeps_qnap_specifics_out_of_app_code() -> None:
    guide = read_repo_text("docs/developer/qnap-docker-runtime.md")
    normalized_guide = " ".join(guide.split())

    assert "QNAP Docker is the first practical deployment target" in normalized_guide
    assert "move later to AWS, Azure, DigitalOcean, Render, Fly.io" in normalized_guide
    assert "Do not commit a database connection string" in normalized_guide
    assert "CCLD_HOSTED_TESTER_DATABASE_URL" in guide
    assert "CCLD_POSTGRES_PASSWORD" in guide
    assert "docker compose -f docker-compose.qnap.yml --env-file .env up --build -d" in guide
    assert "alembic upgrade head" in guide
    assert "ccld_postgres_data" in guide
    assert "pg_dump" in guide
    assert "pg_restore" in guide
    assert "GitHub Projects are not required" in normalized_guide
    assert "C:\\" not in guide
    assert "/share/" not in guide


def test_cloud_portability_guide_compares_hosts_without_credentials() -> None:
    guide = read_repo_text("docs/developer/cloud-portability-deployment.md")
    normalized_guide = " ".join(guide.split())

    for required_text in (
        "QNAP Docker",
        "AWS low-cost path",
        "Azure",
        "DigitalOcean",
        "Render",
        "Fly.io",
        "Railway",
        "Supabase or Neon",
        "Python app",
        "PostgreSQL",
        "Persistent raw file storage",
        "Server-side retrieval jobs",
        "Secrets",
        "Scheduled backups",
        "Custom domain/HTTPS",
        "Production-Readiness Checklist",
        "CCLD_RETRIEVAL_DEMO_MODE=mock-success",
    ):
        assert required_text in guide

    assert "does not deploy the app" in normalized_guide
    assert "No real cloud credentials" not in guide
    assert "ghp_" not in guide
    assert "github_pat_" not in guide
    assert "C:\\" not in guide
    assert "OneDrive" not in guide
    assert "client_secret=" not in guide.casefold()