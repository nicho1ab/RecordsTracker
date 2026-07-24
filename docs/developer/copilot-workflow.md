# Copilot Workflow

## Primary rule

Use chat to ask Copilot for small, scoped, validated changes. Point Copilot to
the current complete GitHub issue, `AGENTS.md`, `.github/copilot-instructions.md`,
and only task-relevant governing files before requesting work. The issue is the
durable task specification; report governing files actually read and only
conflicts or material findings.

## Recommended first prompt in VS Code Chat

```text
Read the current complete GitHub issue, AGENTS.md, .github/copilot-instructions.md,
and the task-relevant governing documents. List the governing files actually
read and report only conflicts or material findings before making changes.
```

## Prompt types

### Analysis-only prompts

Use analysis-only prompts when you want Copilot to inspect code, docs, issues,
test failures, or architecture options without editing files.

```text
Read the governance files and analyze <question or risk>. Do not edit files, run
mutating commands, create branches, or open a PR. Summarize findings, open
questions, and recommended next steps.
```

Analysis-only work may challenge assumptions and identify stale governance, but
it must not weaken source traceability, raw source preservation, deterministic
extraction, fixture-backed regression expectations, accessibility, security,
privacy, or public-source caution language.

### Governance-change proposals

Use governance-change prompts when rules, decision logs, roadmap language,
testing policy, documentation policy, or workflow guidance may need to change.

```text
Using the governance files, propose and implement the smallest governance update
for <change>. Preserve non-negotiable safeguards, update related docs that would
otherwise become stale, run focused documentation validation, then rely on the
required GitHub checks for broader ordinary PR validation.
```

Governance may be challenged when project phase, reviewer needs, validation
evidence, CI failures, repeated review corrections, or architecture decisions
show that prior assumptions are stale. Source traceability, raw source
preservation, deterministic extraction where reliable, fixture-backed regression
coverage, accessibility, security/privacy, schema-change discipline, connector
contract discipline, and public-source caution language remain strict.

### Architecture decision reviews

Use architecture decision review prompts when comparing boundaries, tradeoffs, or
stack options. These prompts should produce or update ADRs and should not select
or implement a production stack unless the task explicitly asks for that decision
and the required context is available.

```text
Read the governance files and current ADRs. Review the architecture decision for
<topic>, compare options, preserve the non-negotiable safeguards, and draft the
smallest ADR or ADR update needed. Do not build the implementation.
```

### Implementation tasks

Use implementation prompts for code, schema, connector, extraction, export,
review-view, or script changes.

## Add a feature prompt

```text
Using the governance files, implement the smallest safe version of <feature>. Add or update tests, update developer docs and user docs if behavior changes, and do not change the data contract unless you explain why first.
```

## Fix a bug prompt

```text
Create a failing regression test or fixture for this bug first. Then fix the smallest amount of code needed. Identify the root cause and update governance rules if a missing or unclear rule allowed the bug. Run or describe the validation commands I should run.
```

Implementation work must keep schema, extraction, connector, traceability,
accessibility, privacy, and documentation impacts explicit. Focused local
validation does not replace the required GitHub checks.

### Phase-transition tasks

Use phase-transition prompts when the project moves from POC to local
attorney-review aid, production-discovery, production-build, or production
operations governance.

```text
Implement the smallest phase-transition governance update for <phase change>.
Preserve non-negotiable safeguards, mark prior decisions as historical or
superseded only where applicable, update roadmap/design/architecture/workflow
docs that would otherwise become misleading, and do not build application code.
```

Phase-transition work may supersede stale POC-era assumptions. It must not remove
source traceability, raw source preservation, deterministic extraction
expectations, fixture-backed regression expectations, accessibility,
security/privacy, public-source caution language, or schema/connector governance.

### Prototype and spike tasks

Use prototype or spike prompts to explore uncertain approaches before production
commitment. Spikes should be clearly labeled, small, reversible, and separated
from production decisions.

```text
Create a small prototype or spike for <question>. Keep it isolated, document what
it proves and does not prove, avoid new baseline dependencies unless explicitly
approved, preserve source traceability and accessibility constraints, and do not
present it as the production stack decision.
```

## Guardrails

- Do not accept broad rewrites.
- Do not accept schema changes without migration, docs, and tests.
- Do not accept extraction changes without fixture tests.
- Do not accept bug or CI-failure fixes that skip root-cause governance review.
- Use focused validation first to catch likely failures quickly, and explain why
	the focused tests matched the changed area.
- Do not skip the required GitHub checks for implementation work.
- When a bug or CI failure reveals a missing or unclear rule, update the relevant
	governance, testing, fixture, connector, or workflow documentation in the same
	change.
- Ask Copilot to show changed files and summarize validation results.

## Validation guidance

Use tiered validation for implementation work.

### Local implementation validation

For a focused bug fix or similarly narrow change, run the new regression
independently, then the smallest relevant tests for the changed area. Run
targeted Ruff and mypy appropriate to the changed files, documentation
validation when documentation or governed behavior changes, and
`git diff --check`. Examples:

- Extraction change: targeted extractor tests and related fixture regression tests.
- Connector change: targeted connector discovery, fetch, and raw storage tests using fixtures or mocks.
- Data contract or schema change: schema validation, init or migration SQL tests, persistence tests, and affected data dictionary checks.
- Datasette, view, or export change: affected SQL, view, export, metadata, and documentation checks.
- Documentation-only change: documentation validation and link or reference checks.
- Security or privacy change: security checks and any affected tests.
- Accessibility-facing change: documentation, export, view, or presentation accessibility checks.

Copilot should state which focused validation it selected and why it matched the
change. Focused tests must genuinely prove the changed behavior. Do not report
unrun validation as passed, and do not run the complete local suite by default
for an ordinary focused change.

### Required GitHub PR validation

For this repository, Standard PR validation means the required GitHub checks
below, not an automatic complete local test-suite run.

Before merge, verify the required GitHub checks pass:

- `validate`
- `docs-check`
- `fixtures`
- `security`

These checks provide broader pre-merge validation for ordinary focused changes
and must not be weakened or bypassed.

### Independent GitHub Actions verification

GitHub Actions independently reruns the authoritative checks from a clean
GitHub-hosted environment. Their purposes are: `validate` runs lint, type, test,
and documentation validation; `docs-check` reruns documentation validation;
`fixtures` reruns fixture regressions; and `security` checks committed secrets
and dependency advisories. The four status-check names remain the required
merge-gate contract.

The `validate` workflow also runs `scripts/check_independent_verification.py`.
For pull requests it verifies the governing-issue reference, completed
machine-testable evidence fields, and truthful governed-boundary declarations.
It fails when a changed governed boundary is marked `No change`, and workflow
changes require `Concern - review required`. It statically rejects removed or
renamed required jobs, missing authoritative commands, unconditional skip
conditions, broad `continue-on-error`, and path filters that could silently
weaken the required checks. The pull-request-only evidence step is intentionally
environment-gated; the workflow-contract check runs for both pull requests and
pushes.

This validation produces a concise summary for human review. It does not approve
the pull request or determine subjective product, UX, accessibility, privacy,
security, legal, or governance acceptance. During the pilot, fresh-context review remains advisory;
it is selected by a human and cannot approve or merge a pull
request. A failed or unavailable advisory review is never an approval.

### Full local or release validation

Run or verify the full test suite only when explicitly requested; for releases,
production-readiness milestones, schema changes, connector expansion,
export-contract changes, production architecture transitions, or broad
cross-cutting changes; when repository governance specifically requires it; or
when focused or CI failures require broader investigation.

## Required completion handoff

Implementation and RL-PREPARE handoffs contain only the outcome; root cause
where applicable; changed files; focused validation; documentation or governance
impact; PR number and state when applicable; blockers; and the exact stop point.
Include a manual command only when an authorized action remains for the human;
do not repeat unused commit, push, or PR commands after Codex completed them.

Copilot should not run an unattended loop through the entire roadmap. Do not
include personal paths, account details, private URLs, tokens, secrets, or
machine-specific configuration in a handoff.

## Next-prompt quality standard

Within an already-authorized task with unchanged authority and scope, the next
Copilot prompt is delta-only: state only the new output, failure, correction, or
evidence. Restate the task authorization when authority or scope changes; a
continuation never grants additional authority implicitly.

Prompt-mode guidance:

- `analysis-only`: use when the next task should inspect risks, failures,
	architecture options, or stale documentation without editing files, creating a
	branch, opening a PR, or running mutating commands.
- `governance-change`: use when the next task should update project rules,
	workflow guidance, testing policy, documentation strategy, roadmap language,
	decision logs, or other governance surfaces.
- `architecture decision`: use when the next task should create or update an ADR
	that decides boundaries, tradeoffs, or deferred production-discovery choices
	without building the implementation.
- `implementation`: use when the next task should change code, schemas,
	connectors, extraction, storage, exports, review views, or scripts, with tests
	and documentation updates scaled to the change.
- `prototype/spike`: use when the next task should explore an uncertain approach
	in an isolated, reversible way without creating an implicit production
	commitment or baseline dependency.
- `validation-hardening`: use when the next task should strengthen tests,
	fixtures, docs checks, security checks, accessibility checks, or CI coverage
	for an already identified risk.

Next prompts must preserve source traceability, raw source preservation,
deterministic extraction, fixture-backed regression expectations, accessibility,
security/privacy, and public-source caution language. Consult the governing
authorization and capability rules before asking for branch, PR, merge, browser,
network, deployment, or QNAP work.
