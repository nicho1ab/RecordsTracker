# Developer Setup

## Required tools

Install these locally on Windows:

- Git
- Python 3.11 or newer
- Visual Studio Code
- GitHub Copilot extension for VS Code, if available through your account

## Setup command

From the extracted governance pack folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup-project.ps1 -ProjectPath "C:\Users\andre\Desktop\ccld-complaints-poc" -InitializeGit
```

## What setup does

- Creates the project folder.
- Copies the governance pack into the project.
- Creates a Python virtual environment.
- Installs Python dependencies from `requirements-dev.txt`.
- Creates local data folders.
- Initializes Git if requested.
- Runs initial validation commands.

## Open in VS Code

```powershell
code "C:\Users\andre\Desktop\ccld-complaints-poc"
```

## Validate setup

```powershell
.\scripts\test.ps1
.\scripts\lint.ps1
.\scripts\docs.ps1
```
