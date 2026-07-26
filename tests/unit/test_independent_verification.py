from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "check_independent_verification.py"
COMPACT_FIXTURE = ROOT / "tests" / "fixtures" / "pr_evidence_policy" / "compact-cases-v1.json"
SHA_A = "a" * 40
SHA_B = "b" * 40
TREE_A = "c" * 40
HASH_A = "d" * 64
HASH_B = "e" * 64


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
- Reviewer UI regression contracts: Added `RT-RC-001`; other contracts are not
  applicable to this policy-only change.

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


VALIDATOR = _load_module()


def _compact_input(paths: list[str], **overrides: object) -> dict[str, object]:
    scope_hash = hashlib.sha256("\n".join(paths).encode("utf-8")).hexdigest()
    identity: dict[str, object] = {
        "repository": "nicho1ab/RecordsTracker",
        "base_sha": SHA_A,
        "head_sha": SHA_A,
        "tree_sha": TREE_A,
        "changed_file_inventory_hash": scope_hash,
        "pr_body_hash": HASH_A,
        "policy_version": "1.0.0",
        "schema_version": "recordstracker.evidence-reuse-validation-impact.v1",
        "validator_version": "evaluator-v1",
        "governed_boundary_classification": ["Repository governance"],
        "dependency_state_digest": HASH_A,
    }
    checks = [
        {
            "check_name": check,
            "run_id": number,
            "job_id": number + 100,
            "status": "success",
            "head_sha": SHA_A,
            "tree_sha": TREE_A,
            "changed_file_inventory_hash": scope_hash,
            "pr_body_hash": HASH_A,
        }
        for number, check in enumerate(("validate", "docs-check", "fixtures", "security"), 1)
    ]
    value: dict[str, object] = {
        "kind": "input",
        "schema_version": "recordstracker.evidence-reuse-validation-impact.v1",
        "repository_state": identity,
        "changed_file_inventory": {"complete": True, "paths": paths},
        "dependency_state": {"status": "known", "digest": HASH_A},
        "evidence": [],
        "required_check_runs": checks,
    }
    value.update(overrides)
    return value


def _compact_body(paths: list[str], **overrides: object) -> str:
    verification = _load_module()
    return (
        _valid_body()
        + "\n"
        + verification.compact_policy_section(
            _compact_input(paths, **overrides),
            delta="Policy evidence added for the changed scope.",
            validation_newly_performed=["focused"],
            live_evidence_recollected=["required checks"],
        )
    )


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

    assert (
        verification.find_pr_evidence_violations(_valid_body(), [".github/workflows/ci.yml"]) == []
    )


@pytest.mark.parametrize("case", json.loads(COMPACT_FIXTURE.read_text(encoding="utf-8"))["cases"])
def test_compact_fixture_contract_names_remain_complete(case: str) -> None:
    assert case


def test_valid_compact_evidence_reconstructs_requirements() -> None:
    verification = _load_module()
    for path in (
        "docs/developer/codex-workflow.md",
        "tests/unit/test_independent_verification.py",
        "scripts/delivery_automation_registry.py",
    ):
        assert verification.find_pr_evidence_violations(_compact_body([path]), [path]) == []


def test_body_only_retains_source_evidence_and_invalidates_body_dependent_evidence() -> None:
    verification = _load_module()
    paths = [".github/delivery-automation-registry.json"]
    policy_input = _compact_input(paths)
    current = policy_input["repository_state"]
    source = {
        "id": "source-test",
        "state": "fresh",
        "purpose": "source test",
        "identity": {**current, "pr_body_hash": HASH_B},
        "body_dependent": False,
        "immutable_references": ["commit:" + SHA_A],
    }
    body = {**source, "id": "body-validator", "body_dependent": True}
    policy_input["evidence"] = [source, body]
    rendered = verification.compact_policy_section(
        policy_input,
        delta="Body-only evidence change.",
        validation_newly_performed=[],
        live_evidence_recollected=["required checks"],
    )
    assert verification.find_pr_evidence_violations(_valid_body() + "\n" + rendered, paths) == []
    assert '"id":"source-test"' in rendered
    assert '"id":"body-validator"' in rendered


def test_compact_policy_rejects_scope_result_and_live_obligation_mismatches() -> None:
    verification = _load_module()
    body = _compact_body(["docs/developer/codex-workflow.md"])
    assert "compact policy" not in "\n".join(
        verification.find_pr_evidence_violations(body, ["docs/developer/codex-workflow.md"])
    )
    scope_violations = verification.find_pr_evidence_violations(
        body, ["tests/unit/test_independent_verification.py"]
    )
    assert (
        "compact policy changed-file inventory differs from independently supplied scope"
        in scope_violations
    )
    missing_live = body.replace(
        '"live_obligations":["observe_terminal_required_checks","recollect_mutable_issue_state"]',
        '"live_obligations":[]',
    )
    live_violations = verification.find_pr_evidence_violations(
        missing_live, ["docs/developer/codex-workflow.md"]
    )
    assert (
        "compact policy result differs from independently reconstructed result" in live_violations
    )


def test_compact_policy_rejects_tampered_visible_claims_and_schema_version() -> None:
    verification = _load_module()
    paths = ["docs/developer/codex-workflow.md"]
    body = _compact_body(paths)
    decision_violations = verification.find_pr_evidence_violations(
        body.replace("- Decision: ready", "- Decision: blocked"), paths
    )
    assert "compact policy visible decision differs from envelope" in decision_violations
    source_version = '"schema_version":"recordstracker.evidence-reuse-validation-impact.v1"'
    tampered_schema = '"schema_version":"recordstracker.evidence-reuse-validation-impact.v0"'
    before_envelope_version, _, after_envelope_version = body.rpartition(source_version)
    schema_violations = verification.find_pr_evidence_violations(
        before_envelope_version + tampered_schema + after_envelope_version,
        paths,
    )
    assert "compact policy envelope schema version is invalid" in schema_violations


def test_compact_policy_rejects_unsafe_runs_unknowns_and_legacy_mixing() -> None:
    verification = _load_module()
    paths = ["docs/developer/codex-workflow.md"]
    pending = _compact_input(paths)
    pending["required_check_runs"][-1]["status"] = "pending"
    pending_body = (
        _valid_body()
        + "\n"
        + verification.compact_policy_section(
            pending,
            delta="Pending check retained.",
            validation_newly_performed=[],
            live_evidence_recollected=["required checks"],
        )
    )
    assert verification.find_pr_evidence_violations(pending_body, paths) == []
    assert "REQUIRED_CHECK_PENDING:security" in pending_body
    mixed = (
        _governed_summary_body()
        + "\n"
        + verification.compact_policy_section(
            pending,
            delta="Pending check retained.",
            validation_newly_performed=[],
            live_evidence_recollected=["required checks"],
        )
    )
    assert (
        "compact policy evidence cannot be mixed with legacy governed summary"
        in verification.find_pr_evidence_violations(mixed, paths)
    )


def test_missing_governing_issue_fails_closed() -> None:
    verification = _load_module()

    violations = verification.find_pr_evidence_violations(
        _valid_body().replace("Closes #531", ""), []
    )

    assert "missing governing issue reference" in violations


@pytest.mark.parametrize("heading", VALIDATOR.REQUIRED_TEMPLATE_SECTIONS)
def test_each_missing_required_template_heading_fails_closed(heading: str) -> None:
    verification = _load_module()
    body = _valid_body().replace(f"## {heading}\n", "", 1)

    violations = verification.find_pr_evidence_violations(body, [])

    assert f"missing PR evidence section: {heading}" in violations


def test_duplicate_required_template_heading_fails_closed() -> None:
    verification = _load_module()
    body = _valid_body() + "\n## Required GitHub checks\n\n- duplicate\n"

    violations = verification.find_pr_evidence_violations(body, [])

    assert "duplicate PR evidence section: Required GitHub checks" in violations


@pytest.mark.parametrize(
    "value",
    (
        "",
        "<!-- List affected contracts. -->",
        "TBD",
        "N/A",
        "none",
    ),
)
def test_reviewer_contract_placeholder_or_evasive_value_fails_closed(value: str) -> None:
    verification = _load_module()
    body = _valid_body().replace(
        "Added `RT-RC-001`; other contracts are not\n  applicable to this policy-only change.",
        value,
    )

    violations = verification.find_pr_evidence_violations(body, [])

    assert any("reviewer-contract" in violation for violation in violations) or (
        "missing PR evidence field: Reviewer UI regression contracts" in violations
    )


def test_reviewer_contract_not_applicable_requires_non_reviewer_scope() -> None:
    verification = _load_module()
    body = _valid_body().replace(
        "Added `RT-RC-001`; other contracts are not\n  applicable to this policy-only change.",
        "Not applicable - this script-only change has no reviewer-facing behavior.",
    )

    assert verification.find_pr_evidence_violations(body, ["scripts/prepare_pr_body.py"]) == []
    assert (
        "reviewer-contract disposition cannot be not applicable for reviewer scope"
        in verification.find_pr_evidence_violations(body, ["tests/unit/test_hosted_reviewer_ui.py"])
    )


def test_governed_summary_passes_for_required_workflow_change() -> None:
    verification = _load_module()

    assert (
        verification.find_pr_evidence_violations(
            _governed_summary_body(), [".github/workflows/ci.yml"]
        )
        == []
    )


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

    assert (
        verification.main(
            [
                "--repo-root",
                str(ROOT),
                "--event-path",
                str(event_path),
                "--changed-files",
                str(changed_files),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Independent verification summary" in output
    assert "- Governing issue: #531" in output


def test_cli_reads_current_pr_body_instead_of_stale_event(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = _load_module()
    body_path = tmp_path / "current-pr-body.md"
    changed_files = tmp_path / "changed-files.txt"
    body_path.write_text(_valid_body(), encoding="utf-8")
    changed_files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert (
        verification.main(
            [
                "--repo-root",
                str(ROOT),
                "--pr-body",
                str(body_path),
                "--changed-files",
                str(changed_files),
            ]
        )
        == 0
    )

    assert "Independent verification summary" in capsys.readouterr().out


def test_cli_reports_live_body_read_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = _load_module()
    changed_files = tmp_path / "changed-files.txt"
    changed_files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert (
        verification.main(
            [
                "--repo-root",
                str(ROOT),
                "--pr-body",
                str(tmp_path / "missing-body.md"),
                "--changed-files",
                str(changed_files),
            ]
        )
        == 1
    )

    assert "cannot read pull-request body:" in capsys.readouterr().out


def test_cli_preserves_multiline_special_character_live_body(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = _load_module()
    body_path = tmp_path / "current-pr-body.md"
    changed_files = tmp_path / "changed-files.txt"
    body_path.write_text(
        _valid_body().replace(
            "Developer workflow policy updated.",
            "Developer workflow policy updated for review & audit.\n\nAdditional context: <safe>. ",
        ),
        encoding="utf-8",
    )
    changed_files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert (
        verification.main(
            [
                "--repo-root",
                str(ROOT),
                "--pr-body",
                str(body_path),
                "--changed-files",
                str(changed_files),
            ]
        )
        == 0
    )
    assert "Independent verification summary" in capsys.readouterr().out


def test_template_headings_match_the_validator_contract() -> None:
    verification = _load_module()
    template = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")

    expected = list(verification.REQUIRED_TEMPLATE_SECTIONS)
    expected.insert(4, verification.COMPACT_POLICY_HEADING)
    assert [line[3:] for line in template.splitlines() if line.startswith("## ")] == expected


def test_ci_fetches_live_pr_body_before_validation() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "--jq '.body' > .verification-pr-body.md" in workflow
    assert "--pr-body .verification-pr-body.md" in workflow
    assert '--event-path "$GITHUB_EVENT_PATH"' not in workflow
    assert "contents: read" in workflow
    assert "pull-requests: read" in workflow
    assert "set -euo pipefail" in workflow
    assert "write" not in workflow.partition("jobs:")[0]


def test_ci_runs_validation_for_pull_request_edits_without_write_permissions() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "types: [opened, reopened, synchronize, edited]" in workflow
    assert "contents: read" in workflow
    assert "pull-requests: read" in workflow
    assert "pull-requests: write" not in workflow
    assert "validate:" in workflow


def test_changed_governed_boundary_normalizes_windows_paths() -> None:
    verification = _load_module()

    assert verification.changed_governed_boundaries([".github\\workflows\\ci.yml"]) == {
        "Required GitHub workflows and checks": [".github/workflows/ci.yml"]
    }
