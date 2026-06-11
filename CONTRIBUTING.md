# Contributing

## Change process

1. Create a branch.
2. Make the smallest practical change.
3. Add or update tests.
4. Update documentation.
5. Run local validation.
6. Open a pull request.

## Local validation

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```

## Rules

- Do not change extraction behavior without fixture tests.
- Do not change schemas without updating `DATA_CONTRACT.md` and user data dictionary docs.
- Do not add connectors outside `SOURCE_CONNECTOR_CONTRACT.md`.
- Avoid project dependencies on optional paid platform features.
- Do not merge accessibility regressions.
