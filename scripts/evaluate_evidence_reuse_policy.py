"""Evaluate the fixed governed evidence-reuse and validation-impact policy.

This module is deliberately local, deterministic, read-only, and no-network.
It returns policy decisions, never commands or mutation instructions.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / ".github" / "evidence-reuse-validation-impact-policy.json"
SCHEMA_PATH = ROOT / "schemas" / "evidence-reuse-validation-impact-v1.schema.json"
SCHEMA_VERSION = "recordstracker.evidence-reuse-validation-impact.v1"
POLICY_VERSION = "1.0.3"
_PATH = re.compile(
    r"^(?!/)(?![A-Za-z]:)(?!.*//)(?!.*(?:^|/)\.(?:/|$))"
    r"(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"
)


class EvidencePolicyError(ValueError):
    """Raised when a policy input cannot produce a safe deterministic decision."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidencePolicyError(f"expected object in {path.name}")
    return value


def _schema_errors(value: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    return sorted(
        f"schema:{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in validator.iter_errors(value)
    )


def _inventory_hash(paths: list[str]) -> str:
    return hashlib.sha256("\n".join(paths).encode("utf-8")).hexdigest()


def _validate_paths(paths: object) -> list[str]:
    if not isinstance(paths, list):
        return ["INVALID_CHANGED_FILE_INVENTORY"]
    errors: list[str] = []
    for path in paths:
        if not isinstance(path, str) or not _PATH.fullmatch(path) or "\\" in path:
            errors.append("INVALID_CHANGED_FILE_PATH")
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        errors.append("NONDETERMINISTIC_CHANGED_FILE_INVENTORY")
    return sorted(set(errors))


def _classify_path(path: str, policy: dict[str, Any]) -> str:
    matches: list[tuple[int, str]] = []
    for rule in policy["path_rules"]:
        prefix = rule["path"]
        if path == prefix or prefix.endswith("/") and path.startswith(prefix):
            matches.append((len(prefix), rule["impact_class"]))
    return max(matches, default=(0, "unknown"))[1]


def _strict_requirements(classes: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    strict = set(classes)
    focused: set[str] = set()
    full_suite = bool(
        strict
        & {
            "schema_or_governance_validator",
            "application_implementation",
            "ingestion_or_source_contract",
            "database_or_migration",
            "security_or_privacy",
            "workflow_or_required_check_contract",
            "deployment_or_infrastructure",
        }
    )
    docs = "documentation_only" in strict or "schema_or_governance_validator" in strict
    workflow = (
        "workflow_or_required_check_contract" in strict
        or "schema_or_governance_validator" in strict
    )
    sensitive = bool(
        strict
        & {
            "security_or_privacy",
            "workflow_or_required_check_contract",
            "schema_or_governance_validator",
        }
    )
    independent = bool(strict - {"evidence_only_metadata", "documentation_only"})
    if "evidence_only_metadata" in strict:
        focused.add("evidence_metadata")
    if "documentation_only" in strict:
        focused.update({"documentation", "whitespace"})
    if "test_only" in strict:
        focused.update({"affected_regression", "owning_test_collection"})
    for name, category in (
        ("schema_or_governance_validator", "schema_or_governance_validator"),
        ("application_implementation", "affected_application"),
        ("ingestion_or_source_contract", "source_contract"),
        ("database_or_migration", "schema_or_migration"),
        ("security_or_privacy", "security_or_privacy"),
        ("workflow_or_required_check_contract", "workflow_contract"),
        ("deployment_or_infrastructure", "infrastructure"),
    ):
        if name in strict:
            focused.add(category)
    return {
        "required_focused_validation_categories": sorted(focused),
        "full_suite_required": full_suite,
        "docs_validation_required": docs,
        "workflow_contract_validation_required": workflow,
        "sensitive_content_validation_required": sensitive,
        "live_github_evidence_required": True,
        "pr_body_regeneration_required": "evidence_only_metadata" in strict,
        "independent_review_required": independent,
        "governed_boundary_disclosure_required": bool(
            strict - {"evidence_only_metadata", "documentation_only"}
        ),
        "terminal_required_checks_required": True,
        "reuse_permitted": "unknown" not in strict,
        "failure_classification": "none" if "unknown" not in strict else "unknown_scope",
    }


def _same_identity(evidence: dict[str, Any], current: dict[str, Any]) -> tuple[bool, list[str]]:
    prior = evidence["identity"]
    fields = (
        "repository",
        "pull_request_number",
        "base_ref",
        "base_sha",
        "head_ref",
        "head_sha",
        "tree_sha",
        "changed_file_inventory_hash",
        "policy_version",
        "schema_version",
        "validator_version",
        "governed_boundary_classification",
        "dependency_state_digest",
    )
    changed = [field for field in fields if prior.get(field) != current.get(field)]
    if evidence["body_dependent"] and prior.get("pr_body_hash") != current.get("pr_body_hash"):
        changed.append("pr_body_hash")
    return not changed, changed


def _run_obligations(
    runs: list[dict[str, Any]], policy: dict[str, Any], current: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    retained: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    blockers: list[str] = []
    reasons: list[str] = []
    for check in policy["required_check_names"]:
        observed_runs = [run for run in runs if run["check_name"] == check]
        by_identity: dict[tuple[object, object], dict[str, Any]] = {}
        for run in observed_runs:
            identity = (run["run_id"], run["job_id"])
            existing = by_identity.get(identity)
            if existing is not None and existing != run:
                blockers.append(f"AMBIGUOUS_REQUIRED_CHECK_RUN_TIE:{check}")
                continue
            by_identity[identity] = run
        if any(blocker == f"AMBIGUOUS_REQUIRED_CHECK_RUN_TIE:{check}" for blocker in blockers):
            continue
        check_runs = sorted(
            by_identity.values(),
            key=lambda run: (run["run_id"], run["job_id"]),
        )
        if not check_runs:
            blockers.append(f"REQUIRED_CHECK_UNOBSERVED:{check}")
            continue
        newest = check_runs[-1]
        input_fields = ("head_sha", "tree_sha", "changed_file_inventory_hash", "pr_body_hash")
        if any(newest[field] != current[field] for field in input_fields):
            blockers.append(f"REQUIRED_CHECK_INPUT_MISMATCH:{check}")
            reasons.append(f"REQUIRED_CHECK_INPUT_MISMATCH:{check}")
        elif newest["status"] == "success" and newest["conclusion"] != "success":
            blockers.append(f"REQUIRED_CHECK_CONCLUSION_MISMATCH:{check}")
            reasons.append(f"REQUIRED_CHECK_CONCLUSION_MISMATCH:{check}")
        elif newest["status"] == "pending" and newest["conclusion"] is not None:
            blockers.append(f"REQUIRED_CHECK_CONCLUSION_MISMATCH:{check}")
            reasons.append(f"REQUIRED_CHECK_CONCLUSION_MISMATCH:{check}")
        elif newest["status"] == "failure" and newest["conclusion"] in (None, "success"):
            blockers.append(f"REQUIRED_CHECK_CONCLUSION_MISMATCH:{check}")
            reasons.append(f"REQUIRED_CHECK_CONCLUSION_MISMATCH:{check}")
        elif newest["status"] == "pending":
            blockers.append(f"REQUIRED_CHECK_PENDING:{check}")
        elif newest["status"] == "failure":
            blockers.append(f"REQUIRED_CHECK_FAILED:{check}")
            reasons.append(f"NEWER_FAILED_RUN_SUPERSEDES_SUCCESS:{check}")
        else:
            retained.append(
                {"check_name": check, "run_id": newest["run_id"], "job_id": newest["job_id"]}
            )
        if len(check_runs) > 1:
            for prior in check_runs[:-1]:
                superseded.append(
                    {"check_name": check, "run_id": prior["run_id"], "job_id": prior["job_id"]}
                )
            if newest["status"] == "success" and all(
                run["status"] == "success" for run in check_runs
            ):
                reasons.append(f"DUPLICATE_SUCCESSFUL_RUNS_COMPRESSED:{check}")
    return retained, superseded, blockers, reasons


def evaluate(policy_input: dict[str, Any]) -> dict[str, Any]:
    """Return the stable compact policy result for one complete caller inventory."""

    policy = _load_json(POLICY_PATH)
    schema = _load_json(SCHEMA_PATH)
    if policy.get("policy_version") != POLICY_VERSION:
        raise EvidencePolicyError("unsupported policy version")
    for value, label in ((policy, "policy"), (policy_input, "input")):
        errors = _schema_errors(value, schema)
        if errors:
            raise EvidencePolicyError(f"invalid {label}: " + "; ".join(errors))

    inventory = policy_input["changed_file_inventory"]
    current = policy_input["repository_state"]
    path_errors = _validate_paths(inventory["paths"])
    classes = sorted({_classify_path(path, policy) for path in inventory["paths"]})
    blockers = list(path_errors)
    reasons = list(path_errors)
    calculated_inventory_hash = _inventory_hash(inventory["paths"])
    if current["changed_file_inventory_hash"] != calculated_inventory_hash:
        blockers.append("CHANGED_FILE_INVENTORY_HASH_MISMATCH")
        reasons.append("CHANGED_FILE_INVENTORY_HASH_MISMATCH")
    if not inventory["complete"]:
        blockers.append("INCOMPLETE_CHANGED_FILE_INVENTORY")
        reasons.append("INCOMPLETE_CHANGED_FILE_INVENTORY")
    if "unknown" in classes:
        blockers.append("UNKNOWN_CHANGE_CLASS")
        reasons.append("UNKNOWN_CHANGE_CLASS")
    if (
        policy_input["dependency_state"]["status"] != "known"
        or not policy_input["dependency_state"]["digest"]
    ):
        blockers.append("UNCERTAIN_DEPENDENCY_STATE")
        reasons.append("UNCERTAIN_DEPENDENCY_STATE")
    requirements = _strict_requirements(classes, policy)
    requirements["reuse_permitted"] = requirements["reuse_permitted"] and not blockers

    reused: list[dict[str, Any]] = []
    invalidated: list[dict[str, Any]] = []
    recollected: list[dict[str, Any]] = []
    for evidence in sorted(policy_input["evidence"], key=lambda item: item["id"]):
        same, changed = _same_identity(evidence, current)
        reference = {"id": evidence["id"], "immutable_references": evidence["immutable_references"]}
        if evidence["state"] == "fresh" and same and requirements["reuse_permitted"]:
            reused.append(reference)
        elif evidence["state"] == "live":
            recollected.append(reference)
        else:
            invalidated.append({**reference, "invalidated_by": changed or ["evidence_state"]})
            reasons.extend(
                f"EVIDENCE_INVALIDATED:{evidence['id']}:{field}"
                for field in changed or ["evidence_state"]
            )

    retained_runs, superseded_runs, run_blockers, run_reasons = _run_obligations(
        policy_input["required_check_runs"], policy, current
    )
    blockers.extend(run_blockers)
    reasons.extend(run_reasons)
    inventory_paths = inventory["paths"]
    result = {
        "kind": "result",
        "schema_version": SCHEMA_VERSION,
        "policy_version": policy["policy_version"],
        "decision": "blocked" if blockers else "ready",
        "repository_state": current,
        "change_inventory": {
            "complete": inventory["complete"],
            "count": len(inventory_paths),
            "hash": calculated_inventory_hash,
            "paths": inventory_paths,
        },
        "impact_classes": classes or ["unknown"],
        "validation_requirements": requirements,
        "evidence_reused": reused + retained_runs,
        "evidence_recollected": recollected,
        "evidence_superseded": superseded_runs,
        "evidence_invalidated": invalidated,
        "live_obligations": ["observe_terminal_required_checks", "recollect_mutable_issue_state"],
        "blockers": sorted(set(blockers)),
        "authorized_mutations": [],
        "unauthorized_mutations": [
            "automatic_rerun",
            "test_execution",
            "github_check_execution",
            "pr_publication",
            "comment",
            "merge",
            "issue_state_mutation",
            "cleanup",
            "deployment",
            "recovery",
        ],
        "governed_boundary_disclosures": policy["governed_boundary_disclosures"],
        "reasons": sorted(set(reasons)) or ["POLICY_DECISION_COMPLETE"],
    }
    errors = _schema_errors(result, schema)
    if errors:
        raise EvidencePolicyError("invalid result: " + "; ".join(errors))
    return result
