# Setup Instructions

## Recommended platform approach

Use local VS Code, local Python, Git, SQLite, Datasette, and repository files.
Avoid project dependencies on optional paid platform features unless the project
explicitly approves and documents them.

## Local setup

From the repository root, create or refresh the local environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup-project.ps1 -ProjectPath "<local-project-path>"
```

Open the repository in VS Code and confirm the Python interpreter points to the
local virtual environment, when present:

```text
.venv\Scripts\python.exe
```

## Validate the repository

Run the standard checks before completing a task:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```

## Optional Docker runtime check

The local Python workflow above remains the default developer setup and does not
require Docker. For the production-like QNAP-first runtime, copy `.env.example`
to an untracked `.env` file on the Docker host, replace placeholder values, and
run:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env up --build -d
```

The Compose runtime starts the hosted scaffold app plus PostgreSQL in Docker,
runs Alembic migrations before app startup, and exposes the scaffold on
`CCLD_HOSTED_PORT`. Keep real database passwords and host-specific QNAP paths out
of Git. See [docs/developer/qnap-docker-runtime.md](docs/developer/qnap-docker-runtime.md).
For cloud portability planning, see
[docs/developer/cloud-portability-deployment.md](docs/developer/cloud-portability-deployment.md).

## Run the fixture-backed sample workflow

Populate the local sample database from committed fixtures:

```powershell
.\scripts\run-ccld-sample.ps1
```

The script prints the SQLite database path, generated Datasette metadata path,
the Datasette command to open, and grouped next steps for what to open first,
delay triage, source verification, and CSV export.

## Run controlled live fetch

Live fetch must be explicitly invoked and scoped to provided facility numbers.
Use request limits while testing:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098 -Limit 5 -MaxRequests 10
```

For multiple explicitly provided facilities:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098,157806097 -Limit 5 -MaxRequests 20
```

The command prints facility identifier intake feedback before discovery,
including accepted identifiers, duplicate identifiers ignored, and ignored
blank, comment, or header values.

Downloaded raw public report files are saved under the ignored local `data/raw`
path by default. Treat public complaint narratives carefully because they may
contain sensitive details even when publicly available.

## Browse with Datasette

Use the Datasette command printed by the sample or live fetch script when
available. It includes generated metadata with labels, descriptions, and saved
queries.

If you need to run Datasette manually, include the generated metadata file:

```powershell
.\.venv\Scripts\datasette.exe data\processed\ccld.sqlite --metadata data\processed\ccld.datasette-metadata.json
```

Start with the grouped next steps printed by the sample or live fetch script:

1. Open `review_home`, `complaint_review_start_here`, or `complaint_first_pass_review` first.
2. Use `delay_review_flags` for delay triage; review flags are screening aids only.
3. Use `source_traceability_review` to verify source URLs, raw hashes, connector details, and report index.
4. Use `complaint_review_export_with_traceability` or `export-review-bundle.ps1` for source-traceable CSV export.

## GitHub repository setup

For a new remote repository, use placeholders in documentation and examples:

```powershell
git remote add origin https://github.com/<your-github-org-or-user>/<repository-name>.git
git branch -M main
git push -u origin main
```

Do not enable optional paid add-ons unless explicitly approved. If branch
protection or rulesets are available, configure `main` to require pull requests,
passing checks, no force pushes, no branch deletion, and review for governance
files.

## Copilot handoff expectation

Future Copilot tasks should end with a self-contained handoff: summary of
changes, validation results, exact commit and push commands, PR title, PR body,
checks to wait for, post-merge cleanup commands, recommended next branch name,
and the next Copilot prompt.
