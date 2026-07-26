"""Focused coverage for the governed evidence-reuse policy evaluator."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "evidence_reuse_validation_impact" / "cases-v1.json"
MODULE_PATH = ROOT / "scripts" / "evaluate_evidence_reuse_policy.py"
SHA_A = "a" * 40
SHA_B = "b" * 40
TREE_A = "c" * 40
HASH_A = "d" * 64
HASH_B = "e" * 64


def _load_module():
    spec = importlib.util.spec_from_file_location("evidence_reuse_policy", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POLICY = _load_module()


def _identity(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "repository": "nicho1ab/RecordsTracker",
        "pull_request_number": 617,
        "base_ref": "main",
        "base_sha": SHA_A,
        "head_ref": "codex/test",
        "head_sha": SHA_A,
        "tree_sha": TREE_A,
        "changed_file_inventory_hash": HASH_A,
        "pr_body_hash": HASH_A,
        "policy_version": "1.0.2",
        "schema_version": "recordstracker.evidence-reuse-validation-impact.v1",
        "validator_version": "evaluator-v1",
        "governed_boundary_classification": ["Repository governance"],
        "dependency_state_digest": HASH_A,
    }
    value.update(overrides)
    return value


def _digest(paths: list[str]) -> str:
    return hashlib.sha256("\n".join(paths).encode("utf-8")).hexdigest()


def _run(
    check: str, run_id: int, status: str = "success", *, scope_hash: str = HASH_A
) -> dict[str, object]:
    return {
        "check_name": check,
        "run_id": run_id,
        "job_id": run_id + 1000,
        "status": status,
        "conclusion": None if status == "pending" else status,
        "head_sha": SHA_A,
        "tree_sha": TREE_A,
        "changed_file_inventory_hash": scope_hash,
        "pr_body_hash": HASH_A,
    }


def _input(paths: list[str], **overrides: object) -> dict[str, object]:
    inventory = overrides.get("changed_file_inventory", {"complete": True, "paths": paths})
    scope_hash = _digest(inventory["paths"])
    value: dict[str, object] = {
        "kind": "input",
        "schema_version": "recordstracker.evidence-reuse-validation-impact.v1",
        "repository_state": _identity(changed_file_inventory_hash=scope_hash),
        "changed_file_inventory": inventory,
        "dependency_state": {"status": "known", "digest": HASH_A},
        "evidence": [],
        "required_check_runs": [
            _run(name, index + 1, scope_hash=scope_hash)
            for index, name in enumerate(("validate", "docs-check", "fixtures", "security"))
        ],
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "case", json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"], ids=lambda item: item["name"]
)
def test_sanitized_fixture_covers_every_required_case(case: dict[str, object]) -> None:
    paths = case["paths"]
    if case["name"] == "traversal_path":
        with pytest.raises(POLICY.EvidencePolicyError):
            POLICY.evaluate(_input(paths))
    else:
        result = POLICY.evaluate(
            _input(
                paths,
                changed_file_inventory={
                    "complete": case["name"] != "incomplete_inventory",
                    "paths": paths,
                },
            )
        )
        assert case["class"] in result["impact_classes"]


def test_strict_mixed_scope_union_and_requirements_are_explicit() -> None:
    result = POLICY.evaluate(
        _input(["scripts/check_no_secrets.py", "src/ccld_complaints/source_to_screen_audit.py"])
    )
    requirements = result["validation_requirements"]
    assert requirements["full_suite_required"] is True
    assert requirements["sensitive_content_validation_required"] is True
    assert {"affected_application", "security_or_privacy"} <= set(
        requirements["required_focused_validation_categories"]
    )


def test_unknown_and_incomplete_scopes_fail_closed() -> None:
    unknown = POLICY.evaluate(_input(["unclassified/file.txt"]))
    assert unknown["decision"] == "blocked"
    assert "UNKNOWN_CHANGE_CLASS" in unknown["blockers"]
    incomplete = POLICY.evaluate(
        _input(
            ["docs/developer/codex-workflow.md"],
            changed_file_inventory={
                "complete": False,
                "paths": ["docs/developer/codex-workflow.md"],
            },
        )
    )
    assert "INCOMPLETE_CHANGED_FILE_INVENTORY" in incomplete["blockers"]


def test_freshness_and_body_dependency_invalidation_are_distinct() -> None:
    current = _input([".github/delivery-automation-registry.json"])["repository_state"]
    fresh = {
        "id": "source-tests",
        "state": "fresh",
        "purpose": "source tests",
        "identity": {**current, "pr_body_hash": HASH_B},
        "body_dependent": False,
        "immutable_references": ["commit:" + SHA_A],
    }
    body = copy.deepcopy(fresh)
    body["id"] = "body-validator"
    body["body_dependent"] = True
    result = POLICY.evaluate(
        _input([".github/delivery-automation-registry.json"], evidence=[fresh, body])
    )
    assert [item["id"] for item in result["evidence_reused"] if "id" in item] == ["source-tests"]
    assert result["evidence_invalidated"][0]["id"] == "body-validator"
    assert result["evidence_invalidated"][0]["invalidated_by"] == ["pr_body_hash"]


def test_head_tree_scope_boundary_and_dependency_changes_invalidate_evidence() -> None:
    for field, changed in (
        ("head_sha", SHA_B),
        ("tree_sha", SHA_B),
        ("changed_file_inventory_hash", HASH_B),
        ("governed_boundary_classification", ["Security and privacy"]),
        ("dependency_state_digest", HASH_B),
    ):
        current = _input(["docs/developer/codex-workflow.md"])["repository_state"]
        evidence = {
            "id": field,
            "state": "fresh",
            "purpose": "prior",
            "identity": current,
            "body_dependent": False,
            "immutable_references": ["run:1"],
        }
        result = POLICY.evaluate(
            _input(
                ["docs/developer/codex-workflow.md"],
                repository_state={**current, field: changed},
                evidence=[evidence],
            )
        )
        assert result["evidence_invalidated"][0]["invalidated_by"] == [field]
    uncertain = POLICY.evaluate(
        _input(
            ["docs/developer/codex-workflow.md"],
            dependency_state={"status": "uncertain", "digest": None},
        )
    )
    assert "UNCERTAIN_DEPENDENCY_STATE" in uncertain["blockers"]


def test_duplicate_pending_and_failed_required_runs_have_stable_outcomes() -> None:
    runs = [
        _run(name, index + 1)
        for index, name in enumerate(("validate", "docs-check", "fixtures", "security"))
    ]
    scope_hash = _digest(["docs/developer/codex-workflow.md"])
    runs = [
        _run(name, index + 1, scope_hash=scope_hash)
        for index, name in enumerate(("validate", "docs-check", "fixtures", "security"))
    ]
    duplicate = POLICY.evaluate(
        _input(
            ["docs/developer/codex-workflow.md"],
            required_check_runs=runs + [_run("validate", 99, scope_hash=scope_hash)],
        )
    )
    assert "DUPLICATE_SUCCESSFUL_RUNS_COMPRESSED:validate" in duplicate["reasons"]
    assert duplicate["evidence_superseded"] == [
        {"check_name": "validate", "run_id": 1, "job_id": 1001}
    ]
    pending = POLICY.evaluate(
        _input(
            ["docs/developer/codex-workflow.md"],
            required_check_runs=runs + [_run("validate", 99, "pending", scope_hash=scope_hash)],
        )
    )
    assert "REQUIRED_CHECK_PENDING:validate" in pending["blockers"]
    failed = POLICY.evaluate(
        _input(
            ["docs/developer/codex-workflow.md"],
            required_check_runs=runs + [_run("validate", 99, "failure", scope_hash=scope_hash)],
        )
    )
    assert "REQUIRED_CHECK_FAILED:validate" in failed["blockers"]
    assert "NEWER_FAILED_RUN_SUPERSEDES_SUCCESS:validate" in failed["reasons"]


def test_exact_required_run_identity_ties_fail_closed_unless_equivalent() -> None:
    paths = ["docs/developer/codex-workflow.md"]
    scope_hash = _digest(paths)
    runs = [
        _run(name, index + 1, scope_hash=scope_hash)
        for index, name in enumerate(("validate", "docs-check", "fixtures", "security"))
    ]
    equivalent = POLICY.evaluate(_input(paths, required_check_runs=runs + [copy.deepcopy(runs[0])]))
    assert equivalent["decision"] == "ready"
    contradictory = copy.deepcopy(runs[0])
    contradictory["conclusion"] = "failure"
    result = POLICY.evaluate(_input(paths, required_check_runs=runs + [contradictory]))
    assert "AMBIGUOUS_REQUIRED_CHECK_RUN_TIE:validate" in result["blockers"]


def test_result_is_deterministic_complete_and_non_mutating() -> None:
    value = _input(["docs/developer/codex-workflow.md"])
    first = POLICY.evaluate(value)
    assert first == POLICY.evaluate(copy.deepcopy(value))
    assert first["authorized_mutations"] == []
    assert "automatic_rerun" in first["unauthorized_mutations"]
    assert "command" not in json.dumps(first, sort_keys=True).lower()
    assert {
        "schema_version",
        "policy_version",
        "decision",
        "repository_state",
        "change_inventory",
        "impact_classes",
        "validation_requirements",
        "evidence_reused",
        "evidence_recollected",
        "evidence_superseded",
        "evidence_invalidated",
        "live_obligations",
        "blockers",
        "authorized_mutations",
        "unauthorized_mutations",
        "governed_boundary_disclosures",
        "reasons",
    } <= set(first)


def test_schema_and_path_safety_fail_closed() -> None:
    malformed = _input(["docs/developer/codex-workflow.md"])
    malformed["unknown"] = True
    with pytest.raises(POLICY.EvidencePolicyError):
        POLICY.evaluate(malformed)
    with pytest.raises(POLICY.EvidencePolicyError):
        POLICY.evaluate(_input(["../outside.py"]))


@pytest.mark.parametrize(
    "path",
    [
        "docs/./developer/codex-workflow.md",
        "./README.md",
        "docs/../README.md",
        "docs//README.md",
        "docs\\README.md",
        "C:README.md",
        "//server/share/file.md",
    ],
)
def test_unnormalized_repository_paths_fail_closed(path: str) -> None:
    with pytest.raises(POLICY.EvidencePolicyError):
        POLICY.evaluate(_input([path]))


def test_normalized_paths_remain_valid_and_duplicate_paths_fail_closed() -> None:
    assert POLICY.evaluate(_input(["docs/developer/codex-workflow.md"]))["decision"] == "ready"
    duplicate = _input(["docs/developer/codex-workflow.md"])
    duplicate["changed_file_inventory"] = {
        "complete": True,
        "paths": ["docs/developer/codex-workflow.md", "docs/developer/codex-workflow.md"],
    }
    duplicate["repository_state"]["changed_file_inventory_hash"] = _digest(
        duplicate["changed_file_inventory"]["paths"]
    )
    result = POLICY.evaluate(duplicate)
    assert result["decision"] == "blocked"
    assert "NONDETERMINISTIC_CHANGED_FILE_INVENTORY" in result["blockers"]


def test_immutable_references_are_preserved_in_compact_result() -> None:
    current = _input(["docs/developer/codex-workflow.md"])["repository_state"]
    evidence = {
        "id": "exact",
        "state": "fresh",
        "purpose": "retained",
        "identity": current,
        "body_dependent": True,
        "immutable_references": ["commit:" + SHA_A, "run:42", "job:99"],
    }
    result = POLICY.evaluate(_input(["docs/developer/codex-workflow.md"], evidence=[evidence]))
    assert {"id": "exact", "immutable_references": evidence["immutable_references"]} in result[
        "evidence_reused"
    ]
