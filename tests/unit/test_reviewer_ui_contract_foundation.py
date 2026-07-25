"""Representative reusable reviewer UI contract outcomes."""
# ruff: noqa: E501

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("contracts", Path(__file__).with_name("reviewer_ui_contracts.py"))
assert SPEC and SPEC.loader
CONTRACTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACTS)
ReviewerContractError = CONTRACTS.ReviewerContractError
assert_destinations = CONTRACTS.assert_destinations
assert_information_tier = CONTRACTS.assert_information_tier
assert_help_surface = CONTRACTS.assert_help_surface
assert_facility_identity = CONTRACTS.assert_facility_identity
assert_continuity = CONTRACTS.assert_continuity
assert_actions = CONTRACTS.assert_actions
assert_result_structure = CONTRACTS.assert_result_structure


def test_destination_contract_exercises_response_mutation_provenance_and_unavailable_state():
    assert_destinations([{"kind":"get","destination":"/review","state":"available"},{"kind":"mutation","success":True,"failure":True},{"kind":"external","provenance":"source"},{"kind":"get","state":"unavailable"}], lambda path: 200)
    with pytest.raises(ReviewerContractError):
        assert_destinations([{"kind":"get", "destination":"/gone"}], lambda path: 404)
    assert_destinations([{"kind":"get", "destination":"/redirect", "redirect_allowed":True}], lambda path: 302)
    for status in (401, 500):
        with pytest.raises(ReviewerContractError):
            assert_destinations([{"kind":"get", "destination":"/bad"}], lambda path, value=status: value)
    with pytest.raises(ReviewerContractError):
        assert_destinations([{"kind":"external"}], lambda path: 200)


def test_tier_help_identity_continuity_responsive_and_structure_contracts():
    assert_information_tier("Reviewer record")
    with pytest.raises(ReviewerContractError):
        assert_information_tier("Run pipeline command")
    assert_help_surface([{"active":True,"focus":True,"announcements":1,"escape_dismisses":True}], escape_supported=True)
    assert_facility_identity([{"facility_id":"1","name":"A"},{"facility_id":"1","name":"Old","explanation":"historical"}])
    assert_continuity({"selection":"x","focus":"search","context":"results"},{"selection":"x","focus":"search","context":"results"})
    assert_actions([{"order":1,"visible":True,"keyboard":True,"left":0,"right":10},{"order":2,"visible":True,"keyboard":True,"left":11,"right":20}])
    assert_result_structure([{"rows":["1"]},{"rows":["1"],"distinct_purpose":True}],[{"empty":True,"consolidated":True}])
    assert_result_structure([{"rows":["1"]},{"rows":["1"],"registry_exception":True}],[{"empty":True,"consolidated":True}])
    with pytest.raises(ReviewerContractError):
        assert_facility_identity([{"facility_id":"1","name":""}])
    with pytest.raises(ReviewerContractError):
        assert_help_surface([{"active":True,"focus":False}], escape_supported=False)
    with pytest.raises(ReviewerContractError):
        assert_actions([{"order":1,"visible":False,"keyboard":True,"left":0,"right":10}])
