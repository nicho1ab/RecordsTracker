from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "check_independent_verification.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("independent_verification", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_body() -> str:
    workflow_row = (
        "| Required GitHub workflows and checks | Concern - review required | "
        "The required validate workflow is extended. |"
    )
    return f"""# Pull Request Evidence

## Governing issue and intended outcome

- Governing issue: Closes #531
- Intended outcome: Verification evidence is checked on every pull request.

## Implementation scope

- Major files or components changed: verification policy
- Important behavior intentionally left unchanged or out of scope: human approval

## Acceptance-criteria evidence

| Acceptance criterion | Evidence and result |
| --- | --- |
| PR evidence is verified | Focused regression passes |

## Validation and failure classification

| Exact command | Result | Failure classification, if applicable |
| --- | --- | --- |
| `pytest tests/unit/test_independent_verification.py` | Pass | none |

- Implementation-caused failures: None
- Pre-existing failures: None
- Environmental failures: None
- Tests intentionally not run and why: Full suite not run for this focused check.

## UI and accessibility evidence (when applicable)

- Evidence: Not applicable - no UI or accessibility change

## Reviewer-facing redesign artifact classification (when applicable)

- Not applicable - no reviewer-facing redesign

## Documentation, assumptions, and remaining risks

- Documentation impact: Developer workflow policy updated.
- Assumptions and limitations: Human review remains controlling.
- Remaining risks or follow-up: Advisory fresh-context review remains manual.

## Governed-boundary review

| Governed boundary | Status | Specific explanation or evidence |
| --- | --- | --- |
| Schemas and migrations | No change | No affected paths. |
| Ingestion and source-connector contracts | No change | No affected paths. |
| Security and privacy | No change | No affected paths. |
| Production data and correction behavior | No change | No affected paths. |
| Deployment and infrastructure | No change | No affected paths. |
| Repository governance | Authorized change | Verification policy is documented. |
{workflow_row}
| Tests or checks weakened to obtain passage | Authorized change | Regression coverage is added. |

## Required GitHub checks

- [ ] `validate`
- [ ] `docs-check`
- [ ] `fixtures`
- [ ] `security`
"""


def _governed_summary_body() -> str:
    summary = (
        "- adds objective independent verification for governing issues, PR evidence, "
        "and governed-boundary disclosures"
    )
    return f"""## Summary
{summary}

## Required checks
- validate
- docs-check
- fixtures
- security

## Verification behavior
- identifies PRs without a governing issue
- requires disclosure when governed workflow boundaries change

## Boundaries
- no branch-protection or ruleset change
- no required-check rename or removal
- no autonomous approval or merge

## Validation
- focused tests passed

Refs #531
"""


def test_valid_evidence_passes_for_required_workflow_change() -> None:
    verification = _load_module()

    assert verification.find_pr_evidence_violations(
        _valid_body(), [".github/workflows/ci.yml"]
    ) == []


def test_missing_governing_issue_fails_closed() -> None:
    verification = _load_module()

    violations = verification.find_pr_evidence_violations(
        _valid_body().replace("Closes #531", ""), []
    )

    assert "missing governing issue reference" in violations


def test_governed_summary_passes_for_required_workflow_change() -> None:
    verification = _load_module()

    assert verification.find_pr_evidence_violations(
        _governed_summary_body(), [".github/workflows/ci.yml"]
    ) == []


def test_governed_summary_requires_workflow_disclosure_rule() -> None:
    verification = _load_module()
    body = _governed_summary_body().replace(
        "- requires disclosure when governed workflow boundaries change\n", ""
    )

    violations = verification.find_pr_evidence_violations(body, [".github/workflows/ci.yml"])

    assert "missing governed workflow-boundary disclosure rule" in violations


def test_changed_governed_boundary_cannot_claim_no_change() -> None:
    verification = _load_module()
    body = _valid_body().replace(
        "| Security and privacy | No change | No affected paths. |",
        "| Security and privacy | No change | No affected paths. |",
    )

    violations = verification.find_pr_evidence_violations(body, ["scripts/check_no_secrets.py"])

    assert "Security and privacy: changed files require explicit disclosure" in violations


def test_required_workflow_change_requires_human_review_status() -> None:
    verification = _load_module()
    body = _valid_body().replace(
        "| Required GitHub workflows and checks | Concern - review required |",
        "| Required GitHub workflows and checks | Authorized change |",
    )

    violations = verification.find_pr_evidence_violations(body, [".github/workflows/ci.yml"])

    assert (
        "Required GitHub workflows and checks: changes require Concern - review required"
        in violations
    )


def test_required_workflow_contract_rejects_test_skip_controls(tmp_path: Path) -> None:
    verification = _load_module()
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True)
    source = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    workflow.write_text(source + "\n      continue-on-error: true\n", encoding="utf-8")
    for relative_path in (
        ".github/workflows/docs-check.yml",
        ".github/workflows/regression.yml",
        ".github/workflows/security.yml",
    ):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((ROOT / relative_path).read_text(encoding="utf-8"), encoding="utf-8")

    violations = verification.find_workflow_contract_violations(tmp_path)

    assert ".github/workflows/ci.yml: continue-on-error: true is not permitted" in violations


def test_cli_reads_event_and_prints_verification_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = _load_module()
    event_path = tmp_path / "event.json"
    changed_files = tmp_path / "changed-files.txt"
    event_path.write_text(json.dumps({"pull_request": {"body": _valid_body()}}), encoding="utf-8")
    changed_files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert verification.main(
        [
            "--repo-root",
            str(ROOT),
            "--event-path",
            str(event_path),
            "--changed-files",
            str(changed_files),
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Independent verification summary" in output
    assert "- Governing issue: #531" in output
