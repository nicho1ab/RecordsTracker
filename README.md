# CCLD Complaints Data POC Governance Pack

This governance pack is designed for a VS Code + GitHub Copilot assisted build of a public-record complaint ingestion, extraction, validation, and presentation project.

The initial source is the California Community Care Licensing Division public facility/report portal. The initial proof of concept focuses on extracting structured complaint data from one facility, then expanding through a connector contract that supports additional facilities and future public data sources.

## Core principle

The project must preserve source traceability, avoid project dependencies on optional paid platform features, meet digital accessibility requirements, and prevent regression through fixture-based testing.

## Recommended initial architecture

```text
Public source portal/API
   -> Python connector
   -> Raw source file storage
   -> SQLite database
   -> Datasette read-only browse/search/API layer
   -> Optional later: PostgreSQL, Baserow, Metabase
```

## Included files

- Governance documents
- Architecture and roadmap
- Data and connector contracts
- Testing and documentation requirements
- ADA/digital accessibility requirements
- GitHub Copilot instructions and reusable prompts
- GitHub issue and pull request templates
- GitHub Actions workflows using lightweight standard capabilities
- PowerShell scaffolding/setup script
- Python project skeleton with tests, schemas, and fixtures

## Quick start

1. Extract this zip file.
2. Open PowerShell in the extracted folder.
3. Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup-project.ps1 -ProjectPath "<local-project-path>" -InitializeGit
```

4. Open the project in VS Code:

```powershell
code "<local-project-path>"
```

5. Read `docs/developer/setup.md` and `docs/developer/copilot-workflow.md` before asking Copilot to make changes.
