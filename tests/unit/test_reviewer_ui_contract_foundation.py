"""Representative reusable reviewer UI contract outcomes."""
# ruff: noqa: E501

import importlib.util
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("contracts", Path(__file__).with_name("reviewer_ui_contracts.py"))
assert SPEC and SPEC.loader
CONTRACTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTRACTS
SPEC.loader.exec_module(CONTRACTS)
ReviewerContractError = CONTRACTS.ReviewerContractError
InformationTierException = CONTRACTS.InformationTierException
DuplicationException = CONTRACTS.DuplicationException
assert_destinations = CONTRACTS.assert_destinations
assert_information_tier = CONTRACTS.assert_information_tier
assert_help_surface = CONTRACTS.assert_help_surface
assert_facility_identity = CONTRACTS.assert_facility_identity
assert_continuity = CONTRACTS.assert_continuity
assert_actions = CONTRACTS.assert_actions
assert_result_structure = CONTRACTS.assert_result_structure


def test_destination_contract_accepts_only_explicit_supported_kinds():
    assert_destinations(
        [
            {"kind": "get", "destination": "/review"},
            {"kind": "mutation", "success": True, "failure": True},
            {"kind": "external", "provenance": "source"},
            {"kind": "get", "state": "unavailable"},
        ],
        lambda path: 200,
    )
    with pytest.raises(ReviewerContractError):
        assert_destinations([{"kind": "get", "destination": "/gone"}], lambda path: 404)
    assert_destinations([{"kind": "get", "destination": "/redirect", "redirect_allowed": True}], lambda path: 302)
    for status in (401, 500):
        with pytest.raises(ReviewerContractError):
            assert_destinations([{"kind": "get", "destination": "/bad"}], lambda path, value=status: value)
    with pytest.raises(ReviewerContractError):
        assert_destinations([{"kind":"external"}], lambda path: 200)
    for action in ({"destination": "/review"}, {"kind": "", "destination": "/review"}, {"kind": "queue", "destination": "/review"}):
        with pytest.raises(ReviewerContractError):
            assert_destinations([action], lambda path: 200)


def test_information_tier_exceptions_are_narrow_and_governed():
    assert_information_tier("Reviewer record")
    with pytest.raises(ReviewerContractError):
        assert_information_tier("Run pipeline command")
    for exception in (
        InformationTierException("", "approved terminology", frozenset({"sqlite"})),
        InformationTierException("RT-RC-002-sqlite", "", frozenset({"sqlite"})),
        InformationTierException("RT-RC-002-any", "broad", frozenset({"*"})),
    ):
        with pytest.raises(ReviewerContractError):
            assert_information_tier("SQLite", exception=exception)
    sqlite_exception = InformationTierException(
        "RT-RC-002-sqlite", "A governed fixture label needs this exact term.", frozenset({"sqlite"})
    )
    assert_information_tier("SQLite fixture label", exception=sqlite_exception)
    with pytest.raises(ReviewerContractError):
        assert_information_tier("SQLite pipeline command", exception=sqlite_exception)


def test_help_surface_requires_explicit_valid_announcement_evidence():
    assert_help_surface(
        [{"active": True, "focus": True, "announcements": 1, "escape_dismisses": True}], escape_supported=True
    )
    for surface in (
        {"active": True, "focus": True, "announcements": 0},
        {"active": True, "focus": True, "announcements": 2},
        {"active": True, "focus": True},
        {"active": True, "focus": True, "announcements": "1"},
        {"active": True, "focus": True, "announcements": True},
    ):
        with pytest.raises(ReviewerContractError):
            assert_help_surface([surface], escape_supported=False)
    assert_help_surface(
        [{"active": True, "focus": True, "announcement_mode": "not-required", "help_type": "static-inline-definition", "announcements": 0}],
        escape_supported=False,
    )
    with pytest.raises(ReviewerContractError):
        assert_help_surface(
            [{"active": True, "focus": True, "announcement_mode": "not-required", "help_type": "tooltip", "announcements": 0}],
            escape_supported=False,
        )


def _duplication_exception(**overrides: object) -> DuplicationException:
    values: dict[str, object] = {
        "exception_id": "RT-RC-006-distinct-purpose",
        "reason": "Comparison representation has a separately governed task.",
        "representation_id": "comparison-table",
        "duplicate_of_id": "summary-cards",
        "section_id": "comparison",
    }
    values.update(overrides)
    return DuplicationException(**values)  # type: ignore[arg-type]


def test_duplication_exceptions_are_narrow_and_do_not_mask_empty_sections():
    base = {"rows": ["1"], "representation_id": "summary-cards", "section_id": "comparison"}
    duplicate = {"rows": ["1"], "representation_id": "comparison-table", "section_id": "comparison"}
    with pytest.raises(ReviewerContractError):
        assert_result_structure([base, duplicate], [])
    with pytest.raises(ReviewerContractError):
        assert_result_structure([base, duplicate | {"registry_exception": True}], [])
    for exception in (
        _duplication_exception(exception_id=""),
        _duplication_exception(reason=""),
        _duplication_exception(section_id="other"),
    ):
        with pytest.raises(ReviewerContractError):
            assert_result_structure([base, duplicate | {"duplication_exception": exception}], [])
    assert_result_structure([base, duplicate | {"duplication_exception": _duplication_exception()}], [])
    with pytest.raises(ReviewerContractError):
        assert_result_structure(
            [base, duplicate | {"representation_id": "other-table", "duplication_exception": _duplication_exception()}], []
        )
    with pytest.raises(ReviewerContractError):
        assert_result_structure(
            [base, duplicate | {"duplication_exception": _duplication_exception()}], [{"empty": True, "consolidated": False}]
        )


def test_tier_help_identity_continuity_responsive_and_structure_contracts():
    assert_facility_identity([{"facility_id": "1", "name": "A"}, {"facility_id": "1", "name": "Old", "explanation": "historical"}])
    assert_continuity({"selection": "x", "focus": "search", "context": "results"}, {"selection": "x", "focus": "search", "context": "results"})
    assert_actions([{"order": 1, "visible": True, "keyboard": True, "left": 0, "right": 10}, {"order": 2, "visible": True, "keyboard": True, "left": 11, "right": 20}])
    assert_result_structure([{"rows": ["1"], "representation_id": "primary"}, {"rows": ["2"], "representation_id": "secondary"}], [{"empty": True, "consolidated": True}])
    with pytest.raises(ReviewerContractError):
        assert_facility_identity([{"facility_id": "1", "name": ""}])
    with pytest.raises(ReviewerContractError):
        assert_help_surface([{"active": True, "focus": False, "announcements": 1}], escape_supported=False)
    with pytest.raises(ReviewerContractError):
        assert_actions([{"order": 1, "visible": False, "keyboard": True, "left": 0, "right": 10}])
