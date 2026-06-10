# Setup Instructions

## Recommended no-cost approach

Use local VS Code, local Python, Git, and GitHub repository features available to your University of Illinois GitHub Enterprise organization. Avoid Codespaces and any metered add-on features unless the organization confirms they are covered.

## Create GitHub repository

1. Sign in to GitHub with your University of Illinois account.
2. Create a new repository in the appropriate organization.
3. Do not enable paid add-ons unless your organization confirms they are included.
4. Keep the repository private or internal unless public release is intentional.
5. After local setup, push the local repo to GitHub.

## Local setup

Run from the extracted governance pack folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup-project.ps1 -ProjectPath "C:\Users\andre\Desktop\ccld-complaints-poc" -InitializeGit
```

## Connect local repo to GitHub

Replace the URL with your repository URL:

```powershell
cd "C:\Users\andre\Desktop\ccld-complaints-poc"
git remote add origin https://github.com/YOUR-ORG/ccld-complaints-poc.git
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
cd "C:\Users\andre\Desktop\ccld-complaints-poc"
.\.venv\Scripts\datasette.exe data\processed\ccld.sqlite
```

Open the local URL shown by Datasette.

## GitHub Actions

The pack includes GitHub Actions workflows. They use standard hosted runners and lightweight validation. If your organization limits or disables Actions, keep using the same commands locally:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```

## Branch protection or rulesets

If available in your GitHub organization, configure `main` to require:

- Pull request before merge
- CI checks passing
- No force pushes
- No branch deletion
- Code owner review for governance files

If rulesets are not available to you, use the same policy manually.

## Avoid by default

- GitHub Codespaces unless billing is confirmed.
- GitHub Advanced Security paid features unless included.
- Long-running GitHub Actions jobs.
- Large workflow artifacts.
- Paid external SaaS services.

## First development task

Ask Copilot to implement only Phase 1 discovery/fetch/storage for one CCLD facility, then require tests before extraction logic is expanded.
