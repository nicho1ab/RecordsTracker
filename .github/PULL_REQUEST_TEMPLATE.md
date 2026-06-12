# Pull Request Checklist

## Summary

Describe the change.

## Documentation impact

Describe which public, user, developer, contract, limitation, design, or decision
docs were updated. If none were updated, state why no user-facing or
documentation-impacting behavior changed.

## Required checks

- [ ] Tests added or updated.
- [ ] Regression fixtures added or updated, if extraction behavior changed.
- [ ] Data contract unchanged or updated with schemas/docs/tests.
- [ ] Developer docs updated, if developer behavior changed.
- [ ] User docs updated, if user-visible behavior changed.
- [ ] README and other public docs reviewed for documentation impact.
- [ ] Accessibility requirements reviewed.
- [ ] Security/privacy impact reviewed.
- [ ] Known limitations updated, if needed.
- [ ] No project dependency on optional paid platform features added.
- [ ] No secrets committed.
- [ ] Raw source traceability preserved.

## Validation commands

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```
