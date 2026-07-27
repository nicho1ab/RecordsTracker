"""Representative reusable reviewer UI contract outcomes."""
# ruff: noqa: E501

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "contracts", Path(__file__).with_name("reviewer_ui_contracts.py")
)
assert SPEC and SPEC.loader
CONTRACTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTRACTS
SPEC.loader.exec_module(CONTRACTS)
ReviewerContractError = CONTRACTS.ReviewerContractError
InformationTierException = CONTRACTS.InformationTierException
DuplicationException = CONTRACTS.DuplicationException
assert_destinations = CONTRACTS.assert_destinations
assert_fixture_integrity = CONTRACTS.assert_fixture_integrity
assert_information_tier = CONTRACTS.assert_information_tier
assert_help_surface = CONTRACTS.assert_help_surface
assert_facility_identity = CONTRACTS.assert_facility_identity
assert_continuity = CONTRACTS.assert_continuity
assert_actions = CONTRACTS.assert_actions
assert_result_structure = CONTRACTS.assert_result_structure

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")


def test_destination_contract_accepts_only_explicit_supported_kinds():
    assert_destinations(
        [
            {"kind": "get", "destination": "/review"},
            {"kind": "mutation", "success": True, "failure": True},
            {"kind": "external", "provenance": "source"},
            {
                "kind": "get",
                "state": "unavailable",
                "unavailable_reason": "No authorized reviewer route exists.",
            },
            {
                "kind": "external",
                "state": "unavailable",
                "unavailable_reason": "The source is unavailable.",
                "provenance": "source",
            },
            {
                "kind": "mutation",
                "state": "unavailable",
                "unavailable_reason": "This review state does not allow the action.",
            },
        ],
        lambda path: 200,
    )
    with pytest.raises(ReviewerContractError):
        assert_destinations([{"kind": "get", "destination": "/gone"}], lambda path: 404)
    assert_destinations(
        [{"kind": "get", "destination": "/redirect", "redirect_allowed": True}], lambda path: 302
    )
    for status in (401, 500):
        with pytest.raises(ReviewerContractError):
            assert_destinations(
                [{"kind": "get", "destination": "/bad"}], lambda path, value=status: value
            )
    with pytest.raises(ReviewerContractError):
        assert_destinations([{"kind": "external"}], lambda path: 200)
    for action in (
        {"destination": "/review"},
        {"kind": "", "destination": "/review"},
        {"kind": "queue", "destination": "/review"},
        {"state": "unavailable", "unavailable_reason": "Unavailable."},
        {"kind": "", "state": "unavailable", "unavailable_reason": "Unavailable."},
        {"kind": "queue", "state": "unavailable", "unavailable_reason": "Unavailable."},
        {"kind": ["get"], "state": "unavailable", "unavailable_reason": "Unavailable."},
        {
            "kind": "get",
            "state": "unavailable",
            "unavailable_reason": "Unavailable.",
            "destination": "/review",
        },
        {
            "kind": "mutation",
            "state": "unavailable",
            "unavailable_reason": "Unavailable.",
            "mutation_path": "/submit",
        },
    ):
        with pytest.raises(ReviewerContractError):
            assert_destinations([action], lambda path: 200)


def test_fixture_integrity_protects_reviewer_visible_relationships():
    artifact = json.loads(FIXTURE.read_text(encoding="utf-8"))
    [record] = artifact["records"]
    complaint_id = record["complaint"]["complaint_id"]
    facility_id = record["facility"]["facility_id"]
    document_id = record["source_document"]["document_id"]
    source_record_key = f"complaint:{complaint_id}"
    reviewer_states = [
        {
            "state_id": "fixture-status",
            "source_record_key": source_record_key,
        }
    ]
    route_references = [
        {
            "route_id": "complaint-detail",
            "destination": "/reviewer/records/detail",
            "complaint_id": complaint_id,
            "facility_id": facility_id,
            "document_id": document_id,
            "source_record_key": source_record_key,
        },
        {
            "route_id": "facility-review",
            "destination": "/reviewer/facilities/priorities",
            "facility_id": facility_id,
        },
    ]

    assert_fixture_integrity(
        artifact["records"],
        reviewer_states=reviewer_states,
        route_references=route_references,
    )

    broken_facility = copy.deepcopy(artifact["records"])
    broken_facility[0]["complaint"]["facility_id"] = "ccld:facility:missing"
    with pytest.raises(
        ReviewerContractError,
        match=r"complaint ccld:complaint:32-CR-20220407124448: complaint facility_id .* does not match",
    ):
        assert_fixture_integrity(broken_facility)

    broken_source_index = copy.deepcopy(artifact["records"])
    broken_source_index[0]["source_document"]["report_index"] = 50
    with pytest.raises(
        ReviewerContractError,
        match=r"complaint ccld:complaint:32-CR-20220407124448: source URL document index does not match",
    ):
        assert_fixture_integrity(broken_source_index)

    with pytest.raises(
        ReviewerContractError,
        match=r"reviewer state broken-state: source_record_key .* does not reference",
    ):
        assert_fixture_integrity(
            artifact["records"],
            reviewer_states=[
                {
                    "state_id": "broken-state",
                    "source_record_key": "complaint:missing",
                }
            ],
        )

    with pytest.raises(
        ReviewerContractError,
        match=r"route reference broken-route: document_id .* does not reference",
    ):
        assert_fixture_integrity(
            artifact["records"],
            route_references=[
                {
                    "route_id": "broken-route",
                    "destination": "/reviewer/records/detail",
                    "document_id": "ccld:document:missing",
                }
            ],
        )


def test_information_tier_exceptions_are_narrow_and_governed():
    assert_information_tier("Reviewer record")
    with pytest.raises(ReviewerContractError):
        assert_information_tier("Run pipeline command")
    for exception in (
        InformationTierException("", "approved terminology", frozenset({"sqlite"})),
        InformationTierException("RT-RC-002-sqlite", "", frozenset({"sqlite"})),
        InformationTierException("RT-RC-002-other", "unknown", frozenset({"sqlite"})),
        InformationTierException(
            "RT-RC-002-sqlite", "mismatched", frozenset({"connection string"})
        ),
        InformationTierException(
            "RT-RC-002-sqlite", "unrelated", frozenset({"sqlite", "connection string"})
        ),
        InformationTierException("RT-RC-002-any", "broad", frozenset({"*"})),
        InformationTierException(
            "550e8400-e29b-41d4-a716-446655440000", "free text", frozenset({"sqlite"})
        ),
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
    active_focus_surface = {
        "active": True,
        "trigger": "focus",
        "focus": True,
        "announcements": 1,
        "accessible_descriptions": 1,
        "native_title": False,
        "aria_description": False,
        "within_viewport": True,
        "overlaps_trigger": False,
        "escape_dismisses": True,
        "blur_dismisses": True,
        "outside_dismisses": True,
        "focus_restored": True,
    }
    for trigger in ("focus", "click", "tap"):
        assert_help_surface(
            [active_focus_surface | {"trigger": trigger}],
            escape_supported=True,
        )
    assert_help_surface(
        [
            active_focus_surface | {"active": False},
            active_focus_surface | {"trigger": "hover", "focus": False, "announcements": 0},
        ],
        escape_supported=True,
    )
    for update in (
        {"announcements": 0},
        {"announcements": 2},
        {"announcements": "1"},
        {"announcements": True},
        {"trigger": "keyboard"},
        {"focus": False},
        {"accessible_descriptions": 2},
        {"native_title": True},
        {"aria_description": True},
        {"within_viewport": False},
        {"overlaps_trigger": True},
        {"blur_dismisses": False},
        {"outside_dismisses": False},
        {"focus_restored": False},
    ):
        with pytest.raises(ReviewerContractError):
            assert_help_surface([active_focus_surface | update], escape_supported=True)
    with pytest.raises(ReviewerContractError):
        assert_help_surface(
            [active_focus_surface, active_focus_surface | {"trigger": "click"}],
            escape_supported=True,
        )
    assert_help_surface(
        [
            {
                "active": True,
                "trigger": "focus",
                "focus": True,
                "announcement_mode": "not-required",
                "help_type": "static-inline-definition",
                "announcements": 0,
                "accessible_descriptions": 1,
                "native_title": False,
                "aria_description": False,
                "within_viewport": True,
                "overlaps_trigger": False,
                "escape_dismisses": False,
                "blur_dismisses": False,
                "outside_dismisses": False,
                "focus_restored": False,
            }
        ],
        escape_supported=False,
    )
    with pytest.raises(ReviewerContractError):
        assert_help_surface(
            [
                {
                    "active": True,
                    "trigger": "focus",
                    "focus": True,
                    "announcement_mode": "not-required",
                    "help_type": "tooltip",
                    "announcements": 0,
                    "accessible_descriptions": 1,
                    "native_title": False,
                    "aria_description": False,
                    "within_viewport": True,
                    "overlaps_trigger": False,
                    "escape_dismisses": False,
                    "blur_dismisses": True,
                    "outside_dismisses": True,
                    "focus_restored": False,
                }
            ],
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
    assert_result_structure(
        [base, duplicate | {"duplication_exception": _duplication_exception()}], []
    )
    with pytest.raises(ReviewerContractError):
        assert_result_structure(
            [
                base,
                duplicate
                | {
                    "representation_id": "other-table",
                    "duplication_exception": _duplication_exception(),
                },
            ],
            [],
        )
    with pytest.raises(ReviewerContractError):
        assert_result_structure(
            [base, duplicate | {"duplication_exception": _duplication_exception()}],
            [{"empty": True, "consolidated": False}],
        )


def test_tier_help_identity_continuity_responsive_and_structure_contracts():
    assert_facility_identity(
        [
            {"facility_id": "1", "name": "A"},
            {"facility_id": "1", "name": "Old", "explanation": "historical"},
        ]
    )
    assert_continuity(
        {"selection": "x", "focus": "search", "context": "results"},
        {"selection": "x", "focus": "search", "context": "results"},
    )
    assert_actions(
        [
            {"order": 1, "visible": True, "keyboard": True, "left": 0, "right": 10},
            {"order": 2, "visible": True, "keyboard": True, "left": 11, "right": 20},
        ]
    )
    assert_result_structure(
        [
            {"rows": ["1"], "representation_id": "primary"},
            {"rows": ["2"], "representation_id": "secondary"},
        ],
        [{"empty": True, "consolidated": True}],
    )
    with pytest.raises(ReviewerContractError):
        assert_facility_identity([{"facility_id": "1", "name": ""}])
    with pytest.raises(ReviewerContractError):
        assert_help_surface(
            [
                {
                    "active": True,
                    "trigger": "focus",
                    "focus": False,
                    "announcements": 1,
                    "accessible_descriptions": 1,
                    "native_title": False,
                    "aria_description": False,
                    "within_viewport": True,
                    "overlaps_trigger": False,
                    "escape_dismisses": False,
                    "blur_dismisses": True,
                    "outside_dismisses": True,
                    "focus_restored": False,
                }
            ],
            escape_supported=False,
        )
    with pytest.raises(ReviewerContractError):
        assert_actions([{"order": 1, "visible": False, "keyboard": True, "left": 0, "right": 10}])
