"""Focused coverage for the fail-closed hosted UI acceptance contract."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "hosted-ui-acceptance-v1.schema.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "hosted_ui_acceptance"
ACCEPTED_FIXTURE = FIXTURE_DIR / "accepted-v1.json"
REJECTED_641_FIXTURE = FIXTURE_DIR / "issue-641-rejected-packet-v1.json"
VALIDATOR_PATH = ROOT / "scripts" / "validate_hosted_ui_acceptance.py"
REVIEW_GUIDE = ROOT / "docs" / "developer" / "ui-evidence-review.md"
ACCEPTANCE_GUIDE = ROOT / "docs" / "developer" / "hosted-reviewer-acceptance.md"
PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("hosted_ui_acceptance", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_module()

EXPECTED_ISSUE_SCOPE = {
    "governance_issue": "#648",
    "parent_issue": "#640",
    "stakeholder_issue": "#419",
}


def _record(path: Path = ACCEPTED_FIXTURE) -> dict[str, object]:
    return copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))


def _errors(record: dict[str, object]) -> tuple[str, ...]:
    return VALIDATOR.validate_acceptance(record).errors


def _issue_scope(record: dict[str, object]) -> dict[str, object]:
    scope = record["scope"]
    assert isinstance(scope, dict)
    return {key: scope[key] for key in EXPECTED_ISSUE_SCOPE}


def test_accepted_fixture_passes_all_four_gates() -> None:
    record = _record()
    result = VALIDATOR.validate_acceptance(record)

    assert _issue_scope(record) == EXPECTED_ISSUE_SCOPE
    assert result.gates == {
        "STRUCTURAL": "PASS",
        "FUNCTIONAL": "PASS",
        "VISUAL": "PASS",
        "OWNER_ACCEPTANCE": "PASS",
    }
    assert result.overall == "PASS"
    assert result.errors == ()


def test_historical_issue_641_packet_is_rejected_despite_claimed_pass() -> None:
    record = _record(REJECTED_641_FIXTURE)
    result = VALIDATOR.validate_acceptance(record)

    assert _issue_scope(record) == EXPECTED_ISSUE_SCOPE
    assert result.gates == {
        "STRUCTURAL": "FAIL",
        "FUNCTIONAL": "FAIL",
        "VISUAL": "FAIL",
        "OWNER_ACCEPTANCE": "FAIL",
    }
    assert result.overall == "NOT_ACCEPTED"
    assert (
        "structural: artifact counts do not reconcile "
        "(filesystem=71, zip=71, manifest=68, reported=76)"
        in result.errors
    )
    assert "functional: every console event must be explicitly classified" in result.errors
    assert "functional: every network failure must be explicitly classified" in result.errors
    assert any("33 pages exceeds maximum 4" in error for error in result.errors)
    assert any("DOM or text alone cannot prove" in error for error in result.errors)
    assert "visual/independent_review: a human PASS decision is required" in result.errors
    assert "owner_acceptance: an explicit human PASS decision is required" in result.errors
    assert "claims/overall: claimed PASS, computed NOT_ACCEPTED" in result.errors


def test_schema_rejects_swapped_parent_and_stakeholder_issues() -> None:
    record = _record()
    scope = record["scope"]
    assert isinstance(scope, dict)
    scope["parent_issue"] = "#419"
    scope["stakeholder_issue"] = "#640"

    errors = _errors(record)

    assert any(error.startswith("schema:scope/parent_issue") for error in errors)
    assert any(error.startswith("schema:scope/stakeholder_issue") for error in errors)


def test_artifact_counts_must_match_exactly() -> None:
    record = _record()
    record["source_packet"]["artifact_counts"]["manifest"] = 11  # type: ignore[index]

    assert any("artifact counts do not reconcile" in error for error in _errors(record))


def test_required_viewport_and_state_matrices_are_complete_and_unique() -> None:
    record = _record()
    record["visual"]["viewports"][-1]["id"] = "DESKTOP"  # type: ignore[index]
    record["visual"]["state_matrix"][1]["id"] = "DEFAULT"  # type: ignore[index]
    errors = _errors(record)

    assert "visual/viewports: missing required entries: ZOOM_200" in errors
    assert "visual/state_matrix: missing required entries: HOVER" in errors
    assert "visual/state_matrix: duplicate entries: DEFAULT" in errors


def test_design_regression_and_unapproved_variance_fail_visual_gate() -> None:
    record = _record()
    requirements = record["visual"]["design_requirements"]  # type: ignore[index]
    requirements[0]["classification"] = "REGRESSION"
    requirements[1]["classification"] = "VARIANCE"
    errors = _errors(record)

    assert "visual/design_requirements/RT-DS-004: regression" in errors
    assert (
        "visual/design_requirements/RT-STATE-001: variance requires human approval" in errors
    )


def test_dom_only_visual_assertion_and_excess_density_fail() -> None:
    record = _record()
    assertion = record["visual"]["visual_assertions"][0]  # type: ignore[index]
    assertion["evidence_types"] = ["DOM", "TEXT"]
    density = record["visual"]["density_checks"][0]  # type: ignore[index]
    density["measured"] = 13
    errors = _errors(record)

    assert any("DOM or text alone cannot prove" in error for error in errors)
    assert any("measured 13 exceeds maximum 12" in error for error in errors)


def test_density_and_print_ceilings_cannot_be_raised_in_a_record() -> None:
    record = _record()
    density = record["visual"]["density_checks"][0]  # type: ignore[index]
    density["maximum"] = 100
    print_check = record["visual"]["print_checks"][0]  # type: ignore[index]
    print_check["maximum_pages"] = 100
    errors = _errors(record)

    assert any("must remain 12 viewport-heights" in error for error in errors)
    assert any("maximum_pages must remain 4" in error for error in errors)


def test_runtime_event_inventory_must_reconcile_and_classify_exact_resources() -> None:
    record = _record()
    functional = record["functional"]  # type: ignore[index]
    functional["observed_network_failures"] = 2
    functional["network_failure_classifications"] = [
        {
            "id": "optional-telemetry",
            "occurrences": 1,
            "classification": "EXPECTED_OPTIONAL_TELEMETRY",
            "origin_scope": "ALLOWLISTED_OPTIONAL_TELEMETRY",
            "resource": "optional-telemetry-beacon",
            "evidence": "network-failures.json",
        }
    ]
    errors = _errors(record)

    assert any("classification occurrences 1 do not match observed 2" in error for error in errors)
    assert any("must use the exact allowlisted origin" in error for error in errors)


def test_print_limits_and_interactive_control_visibility_are_blocking() -> None:
    record = _record()
    print_check = record["visual"]["print_checks"][0]  # type: ignore[index]
    print_check["page_count"] = 5
    print_check["interactive_controls_hidden"] = False
    errors = _errors(record)

    assert any("5 pages exceeds maximum 4" in error for error in errors)
    assert any("interactive-only controls remain visible" in error for error in errors)


def test_independent_review_must_cover_every_viewport_and_print_artifact() -> None:
    record = _record()
    review = record["visual"]["independent_review"]  # type: ignore[index]
    review["reviewed_evidence"] = ["screenshots/compare-desktop.png"]
    errors = _errors(record)

    assert any("unreviewed screenshot or print evidence" in error for error in errors)


def test_owner_acceptance_is_human_separate_and_bound_to_visual_review() -> None:
    record = _record()
    owner = record["owner_acceptance"]  # type: ignore[index]
    owner["decision"] = "PENDING"
    owner["artifact"] = "reviews/independent-visual-review.json"
    owner["reviewed_visual_record"] = "reviews/another-review.json"
    errors = _errors(record)

    assert "owner_acceptance: an explicit human PASS decision is required" in errors
    assert "owner_acceptance: decision does not reference the independent review" in errors
    assert "owner_acceptance: owner decision must be a separate artifact" in errors


def test_schema_rejects_missing_gate_and_absolute_artifact_path() -> None:
    record = _record()
    del record["gate_claims"]["VISUAL"]  # type: ignore[index]
    record["structural"]["required_artifacts"][0] = "C:/private/manifest.json"  # type: ignore[index]
    errors = _errors(record)

    assert any(error.startswith("schema:gate_claims") for error in errors)
    assert any(error.startswith("schema:structural/required_artifacts/0") for error in errors)


def test_cli_returns_nonzero_and_machine_readable_result_for_rejected_packet() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(REJECTED_641_FIXTURE)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["overall"] == "NOT_ACCEPTED"
    assert payload["gates"]["VISUAL"] == "FAIL"
    assert result.stderr == ""


def test_schema_file_is_versioned_and_loadable() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == (
        "recordstracker.hosted-ui-acceptance.v1"
    )


def test_governance_docs_and_pr_template_require_all_four_gates() -> None:
    review_guide = REVIEW_GUIDE.read_text(encoding="utf-8")
    acceptance_guide = ACCEPTANCE_GUIDE.read_text(encoding="utf-8")
    pr_template = PR_TEMPLATE.read_text(encoding="utf-8")

    for gate in ("STRUCTURAL", "FUNCTIONAL", "VISUAL", "OWNER_ACCEPTANCE"):
        assert f"`{gate}`" in review_guide
        assert f"`{gate}`" in acceptance_guide
        assert f"`{gate}`" in pr_template
    for requirement in (
        "DOM and text",
        "12 viewport heights",
        "16 viewport heights",
        "24 viewport heights",
        "25 records",
        "4 pages",
        "HISTORICAL_REVALIDATION",
        "71/71/68/76",
    ):
        assert requirement in review_guide
    assert "automation cannot supply either human decision" in pr_template
