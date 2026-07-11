---
mode: agent
description: Implement one external stakeholder requirement issue with focused code, tests, documentation, and handoff.
---

Implement the GitHub issue currently in context.

Requirements:

1. Treat the issue body as the approved implementation prompt and acceptance contract.
2. Read `requirements/stakeholder-requirements.json`, `.github/copilot-instructions.md`, `AGENTS.md` when present, and directly affected governance files.
3. Inspect the current code before deciding which files to change.
4. Implement only the selected child requirement and unavoidable dependencies.
5. Preserve source traceability and source-derived versus reviewer-created state separation.
6. Never include the stakeholder's personal name, organization name, or organization domain.
7. Add focused automated tests and directly impacted documentation.
8. Run the narrowest relevant validation first, then the repository-required validation.
9. Do not create or merge a PR, deploy, or capture manual evidence unless explicitly instructed.
10. End with: summary, user-visible outcome, files changed, validation results, limitations, and exact remaining human evidence/stakeholder acceptance steps.