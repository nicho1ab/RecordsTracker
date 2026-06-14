# Hosted Scaffold

## Purpose

This document explains how to run the first local hosted tester MVP scaffold.
The scaffold is a runnable placeholder app shell and smoke route only. It is not
a functioning reviewer workflow.

The scaffold is local-first and must run on a Windows development workstation
before any QNAP, Azure, AWS, public hosting, or public URL work is attempted.
It uses Python standard-library HTTP tooling to avoid creating a final
production frontend, API, database, authentication, hosting, or deployment
commitment.

## Required local tools

- Windows PowerShell.
- Python 3.11 or newer.
- The repository development dependencies from `requirements-dev.txt` for
  tests, lint, and type checks.

Node.js is not required. Docker is not required. QNAP Container Station is not required.
No cloud resources, public URLs, app registrations, cloud databases, DNS records,
deployment credentials, secrets, or tokens are required.

## Verify local prerequisites

Run the local setup check from the repository root after installing project
dependencies:

```powershell
.\scripts\check-hosted-scaffold-local.ps1
```

The check verifies the Python version, hosted scaffold package import, and local
development tools used for focused tests, lint, and type checks. It also reports
that Node/npm, Docker, QNAP, cloud resources, and a public URL are not required
for the Python standard-library scaffold.

The local setup check does not install software, does not require admin rights,
does not create secrets, and does not contact cloud services.

## Install dependencies

From the repository root, create and activate a local virtual environment if one
does not already exist:

```powershell
py -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

Install runtime and development dependencies:

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Start the scaffold locally

Run the scaffold from the repository root:

```powershell
.\scripts\run-hosted-scaffold.ps1 -Port 8000
```

Open `http://127.0.0.1:8000/` on the same workstation. The page must identify
itself as a scaffold and not a functioning reviewer workflow. It must not imply
that authentication, records, workflows, cloud hosting, QNAP, Azure, or AWS are
available.

## Run the smoke check

The smoke check starts an in-process local scaffold server, checks the health
route and placeholder app shell, then stops the server:

```powershell
.\scripts\smoke-hosted-scaffold.ps1
```

The health route is also available on a running scaffold at:

```text
http://127.0.0.1:8000/health
```

## Run scaffold tests

Run the focused scaffold tests:

```powershell
pytest tests/unit/test_hosted_app_scaffold.py
```

Run the standard project validation before opening a PR:

```powershell
.\scripts\check-hosted-scaffold-local.ps1
```

```powershell
.\scripts\lint.ps1
```

```powershell
.\scripts\test.ps1
```

```powershell
.\scripts\docs.ps1
```

```powershell
git diff --check
```

## Intentionally not implemented

The scaffold intentionally does not implement:

- Real authentication.
- Authorization.
- Production schema.
- Migrations with domain tables.
- Import/sync.
- Queues.
- Annotations.
- Corrections.
- Exports.
- Tester feedback.
- Audit trail.
- Reset/reload.
- Hosted live crawling.
- Hosted connector execution.
- Reviewer-created state persistence.
- Source-derived canonical field changes.
- Extraction behavior changes.
- QNAP, Azure, AWS, public hosting, public URLs, or production deployment.

Those layers remain deferred to later ADRs or implementation PRs with focused
validation for the affected boundary.

## Tooling impact

The scaffold uses Python standard-library HTTP server primitives only. This is a
scaffold choice for local validation, not a final production frontend framework,
API framework, database product, authentication provider, hosting platform, or
deployment pipeline decision.