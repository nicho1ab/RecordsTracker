# Development-Loop Label Taxonomy

This taxonomy provides routing metadata for the human-supervised development
loop governed by Issue #527. It does not start work, grant capabilities, select
an agent, approve a pull request, authorize deployment, or replace review of the
complete issue and current repository governance. The machine-readable source
of truth is [`.github/development-loop-labels.json`](../../.github/development-loop-labels.json).

## Labels

| Label | Color | GitHub description | Purpose | Apply when | Remove when |
| --- | --- | --- | --- | --- | --- |
| `codex-loop-ready` | `1A7F37` | Eligible for the governed human-supervised development loop | Marks an issue as eligible for bounded implementation selection. | Andrew has reviewed the complete issue and every eligibility rule is satisfied. | Andrew determines that scope, evidence, risk, dependencies, decisions, or governance no longer satisfy eligibility. |
| `risk-low` | `2DA44E` | Bounded, reversible work with strong independent validation | Records low implementation and verification risk. | Impact is bounded, reversibility is safe, and independent validation is strong. | The classification changes or the issue closes. |
| `risk-medium` | `BF8700` | Broader impact or verification needs; supervised execution allowed | Records medium risk suitable for supervised execution. | Impact or evidence needs are broader, but the issue remains independently testable and reversible. | The classification changes or the issue closes. |
| `risk-high` | `CF222E` | Material governed-boundary risk; no automatic selection | Routes material governed-boundary or operational risk to humans. | Product, data, security, privacy, schema, ingestion, deployment, or operational risk requires human-controlled handling. | Andrew approves a documented reclassification or the issue closes. |
| `requires-product-decision` | `8250DF` | Unresolved product or UX authority is required before execution | Makes an unresolved product or UX decision visible. | Implementation depends on unresolved product or UX authority. | The authorized human decision is recorded in the issue. |
| `requires-data-decision` | `0969DA` | Unresolved data, mapping, provenance, or contract decision | Makes an unresolved data-governance decision visible. | Data semantics, mapping, correction, provenance, or contract authority is unresolved. | The authorized decision and supporting evidence are recorded. |
| `requires-security-review` | `B62324` | Security or privacy review is required before implementation or merge | Routes unresolved security or privacy review to human authority. | Security or privacy review remains required before implementation or merge. | The authorized review is recorded and resulting blockers are resolved. |
| `requires-manual-ui-review` | `1B7C83` | Human visual or interaction review is required before completion | Records a mandatory human UI evidence gate. | Automated implementation may proceed, but visual or interaction review is required before merge or completion. | The human UI review and its disposition are recorded. |
| `blocked` | `57606A` | Execution cannot proceed while a dependency or decision remains | Stops execution while a dependency, decision, evidence gap, or governed boundary is unresolved. | Safe implementation cannot proceed. | The blocker and its resolution are recorded. |

## Loop-ready eligibility

`codex-loop-ready` requires all of the following:

- the issue states its goal, scope, exclusions, acceptance criteria, validation,
  and risks explicitly;
- required product, UX, privacy, security, legal, data, schema, ingestion, and
  deployment decisions are resolved;
- the work is independently testable and safely reversible;
- exactly one of `risk-low` or `risk-medium` is present;
- no unresolved decision, intake, or execution blocker is present; and
- autonomous production deployment is excluded.

The label is prohibited with:

- `risk-high` or more than one `risk-*` label;
- `blocked`;
- `requires-product-decision`;
- `requires-data-decision`;
- unresolved `requires-security-review`;
- `needs-triage` or `question`; and
- `invalid`, `duplicate`, or `wontfix`.

`requires-manual-ui-review` may coexist with `codex-loop-ready` only when the
implementation is already authorized to proceed and the documented human UI
review is a merge or completion gate. `needs:stakeholder-validation` follows
the same conditional rule: it may coexist only when stakeholder validation is
a later completion gate, not when stakeholder input is needed to decide the
implementation. In the latter case, apply the appropriate decision or blocker
label and remove `codex-loop-ready`.

Type, priority, intake-source, and ordinary work-category labels may coexist
with a loop-ready label after triage because they do not determine risk or
eligibility. Labels remain metadata; the implementing agent must still read the
complete issue, its dependencies, and repository governance.

## Human authority and automation

Andrew is the final human authority for loop eligibility and cross-boundary
decisions. Only Andrew may apply or remove `codex-loop-ready`. Issue authors,
contributors, and automated checks may recommend or validate a classification,
but they do not grant eligibility. Repository maintainers may keep risk,
decision, review, and blocker labels aligned with recorded issue state; Andrew
resolves classification disputes and cross-boundary decisions.

Automation may fail closed by refusing to select an ineligible issue. It may not
apply or remove `codex-loop-ready`, restore it after human removal, clear a
blocker or review label, override repository governance, or select an issue with
`risk-high`, `blocked`, an unresolved decision label, or another prohibited
combination. Issue #530 adds no automatic issue selector and applies no labels
to Issues #531 through #533.

## Supported synchronization

The label definitions can be previewed, applied idempotently, and verified with
the governed script:

```powershell
.\scripts\Manage-DevelopmentLoopLabels.ps1 -Mode DryRun
.\scripts\Manage-DevelopmentLoopLabels.ps1 -Mode Apply
.\scripts\Manage-DevelopmentLoopLabels.ps1 -Mode Verify
```

`Apply` and `Verify` require an authenticated GitHub CLI with access to
`nicho1ab/RecordsTracker`. The script rejects another repository, uses
`gh label create --force` for the nine governed definitions, verifies names,
colors, and descriptions, and never deletes unrelated labels.
