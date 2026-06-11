# Setup Instructions

## Recommended platform approach

Use local VS Code, local Python, Git, and repository features available to your project. Avoid project dependencies on optional paid platform features unless the project explicitly approves them.

## Create GitHub repository

1. Sign in to GitHub with the account that owns `<your-github-org-or-user>`.
2. Create a new repository in `<your-github-org-or-user>`.
3. Do not enable optional paid add-ons unless the project explicitly approves them.
4. Keep the repository private or internal unless public release is intentional.
5. After local setup, push the local repo to GitHub.

## Local setup

Run from the extracted governance pack folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup-project.ps1 -ProjectPath "<local-project-path>" -InitializeGit
```

## Connect local repo to GitHub

Replace the URL with your repository URL:

```powershell
cd "<local-project-path>"
git remote add origin https://github.com/<your-github-org-or-user>/<repository-name>.git
git branch -M main
git push -u origin main
```

## VS Code integration

1. Open VS Code.
2. Open the project folder.
3. Install recommended extensions when prompted.
4. Confirm VS Code is using `.venv\Scripts\python.exe`.
5. Open GitHub Copilot Chat.
6. Start with this prompt:

```text
Read .github/copilot-instructions.md, PROJECT_CHARTER.md, DATA_CONTRACT.md, SOURCE_CONNECTOR_CONTRACT.md, TESTING_STRATEGY.md, DOCUMENTATION_STRATEGY.md, ACCESSIBILITY_REQUIREMENTS.md, and DECISIONS.md. Summarize the project rules you must follow before making code changes.
```

## SQLite and Datasette setup

The setup script creates:

```text
data\processed\ccld.sqlite
```

To browse the SQLite database with Datasette:

```powershell
cd "<local-project-path>"
.\.venv\Scripts\datasette.exe data\processed\ccld.sqlite
```

Open the local URL shown by Datasette.

## GitHub Actions

The pack includes GitHub Actions workflows. They use standard hosted runners and lightweight validation. If project policy limits or disables Actions, keep using the same commands locally:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```

## Branch protection or rulesets

If available for the repository, configure `main` to require:

- Pull request before merge
- CI checks passing
- No force pushes
- No branch deletion
- Code owner review for governance files

If rulesets are not available to you, use the same policy manually.

## Avoid by default

- GitHub Codespaces unless explicitly approved for the project.
- GitHub Advanced Security or other optional paid platform features unless explicitly approved for the project.
- Long-running GitHub Actions jobs.
- Large workflow artifacts.
- Optional paid external SaaS services.

## First development task

Ask Copilot to implement only Phase 1 discovery/fetch/storage for one CCLD facility, then require tests before extraction logic is expanded.
