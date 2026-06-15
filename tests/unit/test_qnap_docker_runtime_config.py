from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "verify-qnap-pilot-workflow.ps1"
EVIDENCE_SCRIPT = ROOT / "scripts" / "summarize-qnap-pilot-seeded-import-evidence.ps1"


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


def run_evidence_summary(*args: str) -> subprocess.CompletedProcess[str]:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise AssertionError("PowerShell is required for evidence summary tests.")
    return subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(EVIDENCE_SCRIPT), *args],
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
    output = result.stderr + result.stdout
    assert "CCLD_RETRIEVAL_DEMO_MODE=mock-success" in output
    assert "AllowLocalDevDemo" in output
    assert "production validation" in output


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
    output = result.stderr + result.stdout
    assert "CCLD_RETRIEVAL_ENABLED=enabled" in output
    assert "CCLD_RETRIEVAL_RAW_DIR" in output
    assert "raw artifacts" in output


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


def test_qnap_seeded_import_evidence_script_checks_safe_read_only_summary() -> None:
    script = read_repo_text("scripts/summarize-qnap-pilot-seeded-import-evidence.ps1")
    normalized_script = " ".join(script.split())

    for required_text in (
        "param(",
        "$EnvFile = \".env\"",
        "$ComposeFile = \"docker-compose.qnap.yml\"",
        "$DatabaseService = \"postgres\"",
        "SkipDatabaseCheck",
        "Read-EnvValues",
        "Invoke-PostgresScalar",
        "hosted_import_batches",
        "hosted_source_derived_records",
        "CCLD_HOSTED_PAGE_DATA_MODE",
        "CCLD_RETRIEVAL_DEMO_MODE=mock-success",
        "GitHub feedback decision: half-configured readiness error",
        "Retrieval configuration decision: enabled without raw storage readiness error",
        "Source-derived row counts by entity type",
        "Rows with source URL",
        "Rows with raw SHA-256 linkage",
        "Rows with connector name",
        "Rows with source artifact identity",
        "Most recent import batch timestamp",
        "Raw artifact contents printed: no",
        "Raw server-specific paths printed: no",
        "Secrets printed: no",
    ):
        assert required_text in script

    for required_text in (
        "does not mutate data, run imports, run retrieval, call live CCLD, or call GitHub",
        "no public-source completeness, legal, facility-wide, harm, abuse, neglect, "
        "or liability conclusion",
    ):
        assert required_text in normalized_script

    forbidden_text = (
        "Invoke-WebRequest",
        "raw_path FROM",
        "SELECT raw_path",
        "raw artifact viewer",
        "ghp_",
        "github_pat_",
        "https://github.com/",
        "C:\\",
        "OneDrive",
        "/share/",
    )
    for text in forbidden_text:
        assert text not in script


def test_qnap_seeded_import_evidence_script_handles_env_example_without_database() -> None:
    result = run_evidence_summary("-EnvFile", ".env.example", "-SkipDatabaseCheck")

    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "QNAP pilot seeded import evidence summary" in output
    assert "Expected page-data mode is PostgreSQL-backed" in output
    assert "GitHub feedback decision: disabled intentionally" in output
    assert "Retrieval configuration decision: disabled intentionally" in output
    assert "Local-dev mock-success retrieval mode is not enabled" in output
    assert "Skipping PostgreSQL evidence queries" in output
    assert "placeholder" in output
    assert "Raw artifact contents printed: no" in output
    assert "Raw server-specific paths printed: no" in output
    assert "Secrets printed: no" in output


def test_qnap_seeded_import_evidence_script_handles_missing_env_safely(
    tmp_path: Path,
) -> None:
    missing_env = tmp_path / "missing.env"

    result = run_evidence_summary("-EnvFile", str(missing_env), "-SkipDatabaseCheck")

    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "was not found" in output
    assert "Skipping PostgreSQL evidence queries" in output
    assert "no readiness failures" in output


def test_qnap_seeded_import_evidence_script_detects_readiness_failures(
    tmp_path: Path,
) -> None:
    half_feedback_env = write_env_file(
        tmp_path / "half-feedback.env",
        {"GITHUB_FEEDBACK_REPO": "example/repo", "GITHUB_FEEDBACK_TOKEN": ""},
    )
    retrieval_without_raw_env = write_env_file(
        tmp_path / "retrieval-without-raw.env",
        {"CCLD_RETRIEVAL_ENABLED": "enabled", "CCLD_RETRIEVAL_RAW_DIR": ""},
    )
    mock_success_env = write_env_file(
        tmp_path / "mock-success.env",
        {"CCLD_RETRIEVAL_DEMO_MODE": "mock-success"},
    )

    half_feedback = run_evidence_summary(
        "-EnvFile", str(half_feedback_env), "-SkipDatabaseCheck"
    )
    retrieval_without_raw = run_evidence_summary(
        "-EnvFile", str(retrieval_without_raw_env), "-SkipDatabaseCheck"
    )
    mock_success = run_evidence_summary(
        "-EnvFile", str(mock_success_env), "-SkipDatabaseCheck"
    )

    assert half_feedback.returncode != 0
    assert "half-configured readiness error" in (
        half_feedback.stdout + half_feedback.stderr
    )
    assert retrieval_without_raw.returncode != 0
    assert "enabled without raw storage readiness error" in (
        retrieval_without_raw.stdout + retrieval_without_raw.stderr
    )
    assert mock_success.returncode != 0
    assert "CCLD_RETRIEVAL_DEMO_MODE=mock-success" in (
        mock_success.stdout + mock_success.stderr
    )


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
    assert "qnap-pilot-operator-checklist.md" in guide
    assert "qnap-pilot-auth-readiness.md" in guide
    assert "C:\\" not in guide
    assert "/share/" not in guide


def test_qnap_pilot_operator_checklist_exists_and_covers_required_steps() -> None:
    checklist = read_repo_text("docs/developer/qnap-pilot-operator-checklist.md")
    normalized = " ".join(checklist.split())
    searchable_text = f"{checklist}\n{normalized}"

    for required_text in (
        "QNAP Docker is the first pilot runtime, not a permanent platform lock-in",
        "early external stakeholder organization tester validation",
        "does not prove public-source completeness",
        "legal, facility-wide, harm, abuse, neglect, liability",
        "Confirm the repository checkout is current",
        "Docker and Docker Compose",
        "PostgreSQL data volume backup",
        "raw artifact storage",
        "Copy `.env.example` to `.env`",
        "Keep `CCLD_HOSTED_PAGE_DATA_MODE=postgres`",
        "Keep `CCLD_HOSTED_TESTER_AUTH_MODE=production`",
        "Keep `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled`",
        "Keep `CCLD_RETRIEVAL_DEMO_MODE=` blank",
        "Do not half-configure GitHub feedback",
        ".\\scripts\\verify-qnap-pilot-workflow.ps1 -EnvFile .env",
        "docker compose -f docker-compose.qnap.yml --env-file .env config",
        "docker compose -f docker-compose.qnap.yml --env-file .env up --build -d",
        "alembic upgrade head",
        "app container can write",
        "/ccld/retrieval/jobs/detail?job_id=missing-job",
        "Optional Local-Dev-Only Mock-Success Verification",
        "verifier output summary",
        "GitHub feedback decision",
        "controlled retrieval decision",
        "PostgreSQL backup location",
        "raw artifact backup location",
        "Do not commit `.env`",
        "Do not expose raw artifacts to testers",
    ):
        assert required_text in searchable_text

    assert "raw artifact viewer" not in normalized.casefold()
    assert "ghp_" not in checklist
    assert "github_pat_" not in checklist
    assert "C:\\" not in checklist
    assert "OneDrive" not in checklist


def test_qnap_pilot_operator_checklist_is_linked_from_guides() -> None:
    required_links = {
        "README.md": "docs/developer/qnap-pilot-operator-checklist.md",
        "RUNBOOK.md": "docs/developer/qnap-pilot-operator-checklist.md",
        "docs/developer/qnap-docker-runtime.md": "qnap-pilot-operator-checklist.md",
        "docs/developer/hosted-scaffold.md": "qnap-pilot-operator-checklist.md",
        "docs/user/getting-started.md": "../developer/qnap-pilot-operator-checklist.md",
    }

    for path, link in required_links.items():
        assert link in read_repo_text(path)


def test_qnap_pilot_auth_readiness_doc_exists_and_covers_required_steps() -> None:
    guide = read_repo_text("docs/developer/qnap-pilot-auth-readiness.md")
    normalized = " ".join(guide.split())
    searchable_text = f"{guide}\n{normalized}"

    for required_text in (
        "QNAP Pilot Auth Readiness",
        "CCLD_HOSTED_TESTER_AUTH_MODE=production",
        "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled",
        "Production mode blocks anonymous workflow routes",
        "Local-dev fixture auth exists only for local scaffold validation",
        "it is not production authentication",
        "`/auth/status` is a safe status/debug route",
        "must not expose provider subjects, issuers, raw claims, tokens, cookies",
        "No real login flow",
        "No real OIDC/OAuth2 callback handling",
        "No session cookies",
        "No user table",
        "No self-service account creation",
        "No production password login",
        "No managed identity or provider token exchange",
        "No tester invitation workflow",
        "Do not invite real testers until there is a deliberate access-control decision",
        "client secrets, callback URLs, issuer URLs",
        "Do not commit provider secrets, callback URLs",
        "`.env.example` should contain blanks or neutral placeholders only",
        "QNAP verifier remains the main local readiness check",
        "QNAP verifier output showing production auth mode and local-dev auth disabled",
        "Route behavior showing protected workflow routes are blocked",
        "Decision record that real OIDC/login remains deferred or planned",
        "Known limitation acknowledgement",
        "Do not enable local-dev auth for QNAP pilot mode",
        "Do not set `CCLD_RETRIEVAL_DEMO_MODE=mock-success` in QNAP pilot mode",
        "Do not paste tokens, callback secrets",
        "Do not treat local-dev fixture auth as production authentication",
        "Do not build custom password storage",
        "Do not use shared tester accounts",
    ):
        assert required_text in searchable_text

    assert "ghp_" not in guide
    assert "github_pat_" not in guide
    assert "https://github.com/" not in guide
    assert "C:\\" not in guide
    assert "OneDrive" not in guide
    assert "client_" + "secret" + "=" not in guide.casefold()


def test_qnap_pilot_auth_readiness_doc_is_linked_from_operator_guides() -> None:
    required_links = {
        "README.md": "docs/developer/qnap-pilot-auth-readiness.md",
        "RUNBOOK.md": "docs/developer/qnap-pilot-auth-readiness.md",
        "docs/developer/qnap-docker-runtime.md": "qnap-pilot-auth-readiness.md",
        "docs/developer/qnap-pilot-operator-checklist.md": "qnap-pilot-auth-readiness.md",
        "docs/developer/testing.md": "QNAP auth readiness documentation tests",
    }

    for path, link in required_links.items():
        assert link in read_repo_text(path)


def test_qnap_pilot_seeded_import_evidence_doc_exists_and_covers_required_steps() -> None:
    evidence = read_repo_text("docs/developer/qnap-pilot-seeded-import-evidence.md")
    normalized = " ".join(evidence.split())
    searchable_text = f"{evidence}\n{normalized}"

    for required_text in (
        "early QNAP hosted tester readiness evidence",
        "PostgreSQL-backed CCLD source-derived records",
        "does not prove public-source completeness",
        "legal findings, facility-wide conclusions",
        "`.env` exists on the deployment host and remains untracked",
        "Alembic migrations are current",
        "`CCLD_HOSTED_PAGE_DATA_MODE=postgres`",
        "QNAP verifier passes",
        "raw artifact path",
        "backup planning",
        "`CCLD_RETRIEVAL_DEMO_MODE=` remains blank",
        ".\\scripts\\verify-qnap-pilot-workflow.ps1 -EnvFile .env",
        "docker compose -f docker-compose.qnap.yml --env-file .env run --rm app alembic current",
        "hosted_import_batches",
        "hosted_source_derived_records",
        "source_derived_rows",
        "rows_with_raw_sha256",
        "source_document_id",
        "No raw artifact file contents displayed",
        "/ccld/records/request",
        "setup-required guidance",
        "loaded queue state",
        "A no-match result is not proof",
        "/ccld/retrieval/jobs",
        "/ccld/retrieval/jobs/detail?job_id=missing-job",
        "/feedback",
        "GitHub feedback decision",
        "Controlled retrieval decision",
        "Known limitations acknowledged",
        "PostgreSQL volume",
        "Back up raw artifact storage",
        "Do not commit `.env`",
        "Do not paste secrets into issue comments",
        "Do not expose raw artifacts to testers",
        "Do not enable `CCLD_RETRIEVAL_DEMO_MODE=mock-success` for QNAP pilot mode",
        "Do not use fixture-demo mode as QNAP pilot seeded import evidence",
        "scripts/summarize-qnap-pilot-seeded-import-evidence.ps1",
        "-SkipDatabaseCheck",
        "does not run imports, run retrieval, call live CCLD, call GitHub",
    ):
        assert required_text in searchable_text

    assert "raw artifact viewer" not in normalized.casefold()
    assert "public-source completeness proof" not in normalized.casefold()
    assert "ghp_" not in evidence
    assert "github_pat_" not in evidence
    assert "https://github.com/" not in evidence
    assert "C:\\" not in evidence
    assert "OneDrive" not in evidence


def test_qnap_pilot_seeded_import_evidence_doc_is_linked_from_operator_guides() -> None:
    required_links = {
        "README.md": "docs/developer/qnap-pilot-seeded-import-evidence.md",
        "RUNBOOK.md": "docs/developer/qnap-pilot-seeded-import-evidence.md",
        "docs/developer/qnap-docker-runtime.md": "qnap-pilot-seeded-import-evidence.md",
        "docs/developer/qnap-pilot-operator-checklist.md": "qnap-pilot-seeded-import-evidence.md",
        "docs/developer/testing.md": "QNAP seeded import evidence documentation tests",
        "docs/developer/qnap-pilot-seeded-import-evidence.md": (
            "scripts/summarize-qnap-pilot-seeded-import-evidence.ps1"
        ),
    }

    for path, link in required_links.items():
        assert link in read_repo_text(path)


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
    assert "client_" + "secret" + "=" not in guide.casefold()