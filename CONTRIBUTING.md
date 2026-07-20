# Contributing

## Change process

1. Create a branch.
2. Make the smallest practical change.
3. Add or update tests.
4. Update documentation.
5. Run local validation.
6. Open a pull request.

## Creating loop-compatible implementation issues

Use the **Loop-compatible implementation** issue form when proposed work is
intended for the governed, human-supervised issue-to-draft-PR development loop.
Use the existing specialized forms for initial bug reports, data-contract or
extraction proposals, connector requests, documentation requests, and external
stakeholder requirements that are not yet being authorized as bounded loop
work. Submitting the loop-compatible form does not start work, grant an agent a
capability, authorize a production deployment, or override repository
governance.

Complete the observable outcome, current problem, in-scope and out-of-scope
work, independently verifiable acceptance criteria, validation and evidence,
dependencies, blockers, risk, governed-boundary review, human decisions,
readiness confirmations, and readiness declaration. Keep optional
implementation suggestions separate from required outcomes. Suggestions are not
binding unless they are also stated in the scope or acceptance criteria.
Replace vague criteria such as "make it better" or "improve the UX" with an
observable result that another reviewer can verify.

The issue author records a readiness assessment, but the human with authority
to grant the implementation task makes the readiness determination after
reviewing the complete issue and current repository governance. An issue is:

- **ready for human readiness review** only when every readiness confirmation
  is supported, no required decision remains unresolved, and the work can be
  completed and independently verified without unauthorized deployment;
- **not ready** when required scope, criteria, validation, evidence, dependency,
  risk, boundary, or decision information is incomplete; or
- **blocked** when a dependency, blocker, governed-boundary question, required
  human decision, or unavailable evidence prevents safe execution.

Implementation must stop when repository governance conflicts with the issue,
an unresolved product, UX, privacy, security, legal, data, schema, ingestion, or
deployment decision is discovered, required evidence cannot be produced, the
work is materially broader than described, or the same root problem remains
after the task's allowed correction attempts. Human authority, the task's
explicit capability grant, required checks, review, and merge decision remain
controlling after the form is submitted.

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
