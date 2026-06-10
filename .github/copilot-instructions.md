# Repository Instructions for GitHub Copilot

You are assisting with a governed public-data ingestion and extraction project.

## Required context files

Before making changes, read and follow:

- `PROJECT_CHARTER.md`
- `DECISIONS.md`
- `DATA_CONTRACT.md`
- `SOURCE_CONNECTOR_CONTRACT.md`
- `TESTING_STRATEGY.md`
- `DOCUMENTATION_STRATEGY.md`
- `ACCESSIBILITY_REQUIREMENTS.md`
- `SECURITY_AND_PRIVACY.md`
- `KNOWN_LIMITATIONS.md`

## Hard rules

- Do not invent canonical fields outside `DATA_CONTRACT.md`.
- Do not change schema without updating schemas, docs, tests, and migration/init SQL.
- Do not add a source connector unless it follows `SOURCE_CONNECTOR_CONTRACT.md`.
- Do not modify extraction behavior without adding or updating fixture-based regression tests.
- Do not use LLM extraction for fields that can be deterministically parsed.
- Do not add paid GitHub feature dependencies.
- Do not introduce inaccessible user-facing output.
- Do not remove source traceability.
- Do not delete raw source preservation behavior.
- Do not store secrets in the repo.

## Required change behavior

For every code change:

1. Keep the change small.
2. Add or update tests.
3. Update developer docs if developer behavior changes.
4. Update user docs if user-visible behavior changes.
5. Update known limitations if limitations change.
6. Explain validation commands.

## Preferred stack

- Python
- SQLite
- Datasette
- pytest
- ruff
- mypy
- jsonschema

## Accessibility

All user-facing docs, exports, and presentation layers must meet `ACCESSIBILITY_REQUIREMENTS.md`.
