from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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


def test_env_example_uses_placeholders_only() -> None:
    values = parse_env_example()

    assert values["CCLD_POSTGRES_DB"] == "ccld_records"
    assert values["CCLD_POSTGRES_USER"] == "ccld_app"
    assert values["CCLD_POSTGRES_PASSWORD"] == "replace-with-strong-local-password"
    assert values["CCLD_HOSTED_PORT"] == "8000"
    assert values["CCLD_HOSTED_PAGE_DATA_MODE"] == "postgres"
    assert values["CCLD_FACILITY_REFERENCE_CSV"] == ""

    env_text = read_repo_text(".env.example")
    assert "ghp_" not in env_text
    assert "github_pat_" not in env_text
    assert "https://github.com/" not in env_text
    assert "C:\\" not in env_text
    assert "OneDrive" not in env_text


def test_compose_runtime_uses_postgres_named_volumes_and_healthchecks() -> None:
    compose = read_repo_text("docker-compose.qnap.yml")

    assert "postgres:16-alpine" in compose
    assert "CCLD_HOSTED_TESTER_DATABASE_URL" in compose
    assert "CCLD_HOSTED_PAGE_DATA_MODE" in compose
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