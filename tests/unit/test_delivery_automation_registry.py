"""Focused production-validator coverage for the DA registry foundation."""

from __future__ import annotations

import copy
import importlib.util
import json
import socket
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / ".github" / "delivery-automation-registry.json"
SCHEMA_PATH = ROOT / "schemas" / "delivery-automation-registry-v1.schema.json"
EXCEPTION_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "delivery_automation_registry"
    / "temporary-exception-review-trigger-v1.json"
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REGISTRY_VALIDATOR = _load_module(
    "delivery_automation_registry", ROOT / "scripts" / "delivery_automation_registry.py"
)


def _registry() -> dict[str, object]:
    return copy.deepcopy(json.loads(REGISTRY_PATH.read_text(encoding="utf-8")))


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _errors(registry: dict[str, object], *, today: date | None = None) -> list[str]:
    return REGISTRY_VALIDATOR.validate_registry(registry, _schema(), root=ROOT, today=today)


def _record(registry: dict[str, object], identifier: str) -> dict[str, object]:
    return next(item for item in registry["records"] if item["id"] == identifier)  # type: ignore[index, return-value]


def test_canonical_registry_passes_production_validation() -> None:
    assert REGISTRY_VALIDATOR.validate_canonical_registry() == []


def test_identifiers_are_numerically_ascending() -> None:
    registry = _registry()
    registry["records"] = list(reversed(registry["records"]))  # type: ignore[index]
    assert "records: DA identifiers must be numerically ascending" in _errors(registry)


def test_duplicate_and_invalid_identifiers_fail() -> None:
    registry = _registry()
    registry["records"][1]["id"] = "DA-029"  # type: ignore[index]
    assert "records: duplicate DA identifier" in _errors(registry)
    registry = _registry()
    registry["records"][0]["id"] = "da-29"  # type: ignore[index]
    assert any("schema:records/0/id" in error for error in _errors(registry))


def test_highest_identifier_and_declared_gaps_are_enforced() -> None:
    registry = _registry()
    registry["highest_assigned_id"] = 30
    assert "highest_assigned_id: must equal the highest record identifier" in _errors(registry)
    registry = _registry()
    registry["historical_gaps"] = []
    assert "historical_gaps: DA-001 through DA-028 must be explicitly unavailable" in _errors(
        registry
    )


def test_fabricated_historical_record_and_undeclared_later_gap_fail() -> None:
    registry = _registry()
    registry["records"][0]["id"] = "DA-001"  # type: ignore[index]
    assert any("DA-001 through DA-028" in error for error in _errors(registry))
    registry = _registry()
    registry["records"].pop(1)  # type: ignore[index]
    assert "records: undeclared identifier gaps: DA-030" in _errors(registry)


def test_owner_and_reference_formats_fail_closed() -> None:
    registry = _registry()
    _record(registry, "DA-029")["owner_issue"] = ""
    assert any("schema:records/0/owner_issue" in error for error in _errors(registry))
    registry = _registry()
    _record(registry, "DA-029")["evidence_references"][0]["reference"] = "616"  # type: ignore[index]
    assert "DA-029: evidence_references[0]: invalid issue reference" in _errors(registry)


def test_repository_paths_cannot_escape_the_repository_root() -> None:
    registry = _registry()
    _record(registry, "DA-029")["regression_coverage"] = ["../outside.py"]
    assert "DA-029: regression_coverage: invalid repository path" in _errors(registry)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("governance_change_classifications", ["unsupported"]),
        ("enforcement_levels", ["autonomous_execution"]),
    ],
)
def test_schema_bound_vocabularies_reject_unsupported_values(field: str, value: list[str]) -> None:
    registry = _registry()
    _record(registry, "DA-029")[field] = value
    assert any(f"schema:records/0/{field}/0" in error for error in _errors(registry))


def test_prevention_complete_requires_coverage_and_documentation() -> None:
    registry = _registry()
    record = _record(registry, "DA-029")
    record["regression_coverage"] = []
    record["documentation_impact"] = []
    errors = _errors(registry)
    assert any("regression_coverage" in error for error in errors)
    assert any("documentation_impact" in error for error in errors)


def test_known_prevention_prs_and_da_031_state_are_immutable_contracts() -> None:
    registry = _registry()
    _record(registry, "DA-029")["merged_prevention_prs"] = ["#619"]
    assert "DA-029: expected merged prevention PR #618" in _errors(registry)
    registry = _registry()
    _record(registry, "DA-030")["merged_prevention_prs"] = ["#618"]
    assert "DA-030: expected merged prevention PR #619" in _errors(registry)
    registry = _registry()
    record = _record(registry, "DA-031")
    record["lifecycle_status"] = "prevented"
    record["prevention_state"] = "prevention_complete"
    assert "DA-031: prevention cannot be complete without concrete prevention evidence" in _errors(
        registry
    )


def test_active_temporary_exception_requirements_and_expiration() -> None:
    registry = _registry()
    record = _record(registry, "DA-031")
    record["temporary_exception"] = {
        "owner": "",
        "reason": "temporary",
        "scope": "registry",
        "creation_reference": "#617",
        "status": "active",
        "replacement_or_exit_criteria": "review",
        "relaxes_required_check": False,
        "relaxes_authorization_boundary": False,
    }
    errors = _errors(registry)
    assert "DA-031: active temporary exception requires an owner" in errors
    assert (
        "DA-031: active temporary exception requires an expiration date or review trigger" in errors
    )
    registry = _registry()
    record = _record(registry, "DA-031")
    exception = json.loads(EXCEPTION_FIXTURE.read_text(encoding="utf-8"))
    exception["expiration_date"] = "2026-01-01"
    record["temporary_exception"] = exception
    assert "DA-031: active temporary exception is expired" in _errors(
        registry, today=date(2026, 7, 25)
    )


def test_valid_temporary_exception_review_trigger_passes() -> None:
    registry = _registry()
    _record(registry, "DA-031")["temporary_exception"] = json.loads(
        EXCEPTION_FIXTURE.read_text(encoding="utf-8")
    )
    assert _errors(registry, today=date(2026, 7, 25)) == []


def test_temporary_exception_cannot_relax_a_required_boundary() -> None:
    registry = _registry()
    exception = json.loads(EXCEPTION_FIXTURE.read_text(encoding="utf-8"))
    exception["relaxes_required_check"] = True
    _record(registry, "DA-031")["temporary_exception"] = exception
    assert (
        "DA-031: temporary exception cannot relax a required check or authorization boundary"
        in _errors(registry)
    )


def test_supersession_and_retirement_constraints_fail_closed() -> None:
    registry = _registry()
    _record(registry, "DA-029")["supersession"]["supersedes"] = ["DA-029"]  # type: ignore[index]
    assert "DA-029: direct self-supersession is not allowed" in _errors(registry)
    registry = _registry()
    _record(registry, "DA-029")["supersession"]["superseded_by"] = ["DA-099"]  # type: ignore[index]
    assert "DA-029: supersession references unknown record DA-099" in _errors(registry)
    registry = _registry()
    record = _record(registry, "DA-031")
    record["lifecycle_status"] = "retired"
    assert "DA-031: retired record requires a retirement rationale" in _errors(registry)
    registry = _registry()
    _record(registry, "DA-031")["retirement"] = {"status": "retired", "rationale": "obsolete"}
    assert "DA-031: active and retired state is contradictory" in _errors(registry)


def test_diagnostics_are_deterministic_and_validator_never_uses_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _registry()
    registry["highest_assigned_id"] = 1
    _record(registry, "DA-029")["merged_prevention_prs"] = []
    monkeypatch.setattr(
        socket, "create_connection", lambda *args, **kwargs: pytest.fail("network used")
    )
    first = _errors(registry)
    assert first == sorted(first)
    assert first == _errors(registry)


def test_registry_has_no_secrets_or_private_host_details() -> None:
    registry = _registry()
    registry["purpose"] = "Authorization: bearer secret"
    assert "registry: contains a credential, absolute path, URL, or private-host marker" in _errors(
        registry
    )


def test_existing_prevention_tests_and_documentation_are_referenced() -> None:
    registry = _registry()
    assert (
        "tests/unit/test_pr_body_validation_parity.py"
        in _record(registry, "DA-029")["regression_coverage"]
    )
    assert (
        "tests/unit/test_pr_body_persistence_integrity.py"
        in _record(registry, "DA-030")["regression_coverage"]
    )
    assert all(
        _record(registry, identifier)["documentation_impact"]
        for identifier in ("DA-029", "DA-030", "DA-031", "DA-032")
    )


def test_documentation_vocabulary_and_validation_integration_remain_aligned() -> None:
    workflow = (ROOT / "docs" / "developer" / "codex-workflow.md").read_text(encoding="utf-8")
    for phrase in (
        "Delivery-automation failure and prevention registry",
        "clarification, inconsistency correction, stronger enforcement, relaxed",
        "temporary exception",
        "workflow gate, and human decision",
        "DA-001 through",
        "DA-028 are explicitly unavailable",
    ):
        assert phrase in workflow
    check_docs = _load_module("check_docs_delivery_automation", ROOT / "scripts" / "check_docs.py")
    assert check_docs.find_delivery_automation_registry_violations(ROOT) == []
