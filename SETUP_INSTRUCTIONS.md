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

## Run the fixture-backed sample workflow

Populate the local sample database from committed fixtures:

```powershell
.\scripts\run-ccld-sample.ps1
```

The script prints the SQLite database path, generated Datasette metadata path,
and the Datasette command to open the local review workflow.

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

Start with these review views:

1. `complaint_review_summary`
2. `facility_complaint_summary`
3. `delay_review_flags`
4. `source_traceability_review`

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
