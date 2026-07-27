"""DA-031 deterministic read-only closure-linkage coverage."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "closure_linkage_inspection", ROOT / "scripts/closure_linkage_inspection.py"
)
assert spec and spec.loader
INSPECTOR = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = INSPECTOR
spec.loader.exec_module(INSPECTOR)


def contract(number=608, remain_open=True, **overrides):
    entry = {
        "repository": "nicho1ab/RecordsTracker",
        "issue_number": number,
        "role": "parent",
        "expected_pre_merge_state": "open",
        "expected_post_merge_state": "open",
        "closure_authorized": False,
        "reopen_authorized": False,
        "authority_reference": "#617",
        "rationale": "later work remains",
        "must_remain_open": remain_open,
    }
    entry.update(overrides)
    return [entry]


class FixtureTransport:
    def __init__(
        self,
        *,
        body="",
        closing=(),
        timeline=(),
        state="open",
        state_reason=None,
        closed_at=None,
        reopened_at=None,
        graphql_error=False,
        timeline_error=False,
        graphql_error_message="partial GraphQL response",
        timeline_error_message="partial timeline response",
        effect_available=False,
        repository_name="nicho1ab/RecordsTracker",
        failed_issue_numbers=(),
        merged_at=None,
    ):
        self.body = body
        self.closing = list(closing)
        self.timeline = list(timeline)
        self.state = state
        self.state_reason = state_reason
        self.closed_at = closed_at
        self.reopened_at = reopened_at
        self.graphql_error = graphql_error
        self.timeline_error = timeline_error
        self.graphql_error_message = graphql_error_message
        self.timeline_error_message = timeline_error_message
        self.development_link_effect_available = effect_available
        self.repository_name = repository_name
        self.failed_issue_numbers = set(failed_issue_numbers)
        self.merged_at = merged_at
        self.endpoints = []

    def api(self, endpoint):
        self.endpoints.append(endpoint)
        if endpoint == "repos/nicho1ab/RecordsTracker":
            return {"full_name": self.repository_name}
        if endpoint.endswith("/pulls/615"):
            return {
                "number": 615,
                "body": self.body,
                "base": {"ref": "main", "sha": "a" * 40},
                "head": {"ref": "topic", "sha": "b" * 40},
                "merged_at": self.merged_at,
            }
        number = int(endpoint.rsplit("/", maxsplit=1)[-1])
        if number in self.failed_issue_numbers:
            raise INSPECTOR.ClosureLinkageError("state collection unavailable")
        return {
            "state": self.state,
            "state_reason": self.state_reason,
            "closed_at": self.closed_at,
            "reopened_at": self.reopened_at,
        }

    def closing_issues(self, owner, name, number):
        if self.graphql_error:
            raise INSPECTOR.ClosureLinkageError(self.graphql_error_message)
        return [{"number": value} for value in self.closing]

    def paginated(self, endpoint):
        if self.timeline_error:
            raise INSPECTOR.ClosureLinkageError(self.timeline_error_message)
        return [
            value
            if isinstance(value, dict)
            else {"event": "connected", "source": {"issue": {"number": value}}}
            for value in self.timeline
        ]


def inspect(*, declarations=None, observed_at="2026-07-26T00:00:00Z", **transport):
    return INSPECTOR.inspect_pre_merge(
        repository="nicho1ab/RecordsTracker",
        pr_number=615,
        contract=declarations or contract(),
        transport=FixtureTransport(**transport),
        observed_at=observed_at,
    )


def codes(findings):
    return {item["code"] for item in findings}


def post_collection(evidence, states=None, *, availability="complete", merged_at=None):
    observations = []
    for number, state in (states or {}).items():
        observations.append({"issue_number": number, **state})
    return {
        "repository": evidence["repository"],
        "pull_request_number": evidence["pull_request"]["number"],
        "merged_at": merged_at,
        "availability": availability,
        "issue_states": observations,
    }


def test_complete_evidence_without_closing_reference_is_ready_and_sanitized():
    evidence = inspect(effect_available=True)
    assert evidence["primary_readiness_classification"] == "READY_FOR_SEPARATE_MERGE_AUTHORIZATION"
    assert codes(evidence["closure_risk_findings"]) == {"NO_CLOSING_LINKAGE_DETECTED"}
    assert evidence["evidence_source_availability"] == {
        "pr_body": "complete",
        "graphql_closing_references": "complete",
        "timeline": "complete",
        "development_link_closure_effect": "platform_not_exposed",
        "post_merge_issue_states": "not_observed",
    }
    assert evidence["residual_platform_limitations"] == [
        {
            "mechanism": "development_link_closure_effect",
            "availability": "platform_not_exposed",
            "rationale": (
                "GitHub supported read-only APIs expose development links but not their "
                "closure effect."
            ),
        }
    ]
    assert evidence["post_merge_verification_obligations"] == [
        {
            "repository": "nicho1ab/RecordsTracker",
            "pull_request_number": 615,
            "issue_number": 608,
            "expected_post_merge_state": "open",
            "immediate_observation_required": True,
        }
    ]
    assert "merge" in evidence["prohibited_actions"]
    assert '"body"' not in json.dumps(evidence)
    INSPECTOR.validate_evidence(evidence)


@pytest.mark.parametrize(
    ("body", "closing", "code"),
    [
        ("Fixes #608", (), "UNAUTHORIZED_CLOSURE_LINKAGE"),
        ("", (608,), "UNAUTHORIZED_CLOSURE_LINKAGE"),
        ("Fixes #999", (), "ISSUE_ROLE_UNDECLARED"),
    ],
)
def test_detectable_closing_references_fail_closed(body, closing, code):
    assert code in codes(inspect(body=body, closing=closing)["closure_risk_findings"])


def test_informational_cross_reference_is_recorded_without_blocking_readiness():
    evidence = inspect(
        timeline=(
            {
                "event": "cross-referenced",
                "source": {"issue": {"number": 608}},
                "actor": {"login": "nicho1ab"},
                "created_at": "2026-07-26T00:00:00Z",
            },
        )
    )
    assert evidence["primary_readiness_classification"] == "READY_FOR_SEPARATE_MERGE_AUTHORIZATION"
    assert evidence["observed_development_links"] == []
    assert evidence["observed_timeline_evidence"] == [
        {
            "event": "cross-referenced",
            "classification": "informational_cross_reference",
            "issue_number": 608,
            "target_pull_request_number": 615,
            "actor": "nicho1ab",
            "occurred_at": "2026-07-26T00:00:00Z",
            "commit_sha": None,
            "explicit_closure_semantic": False,
        }
    ]
    assert "UNAUTHORIZED_CLOSURE_LINKAGE" not in codes(evidence["closure_risk_findings"])
    assert (
        evidence["evidence_source_availability"]["development_link_closure_effect"]
        == "platform_not_exposed"
    )


def test_explicit_closing_development_linkage_conflicting_with_open_contract_is_not_ready():
    evidence = inspect(
        timeline=(
            {
                "event": "connected",
                "source": {"issue": {"number": 608}},
                "closes_issue": True,
            },
        )
    )
    assert evidence["primary_readiness_classification"] == "NOT_READY"
    assert "UNAUTHORIZED_CLOSURE_LINKAGE" in codes(evidence["closure_risk_findings"])


def test_committed_events_are_deterministic_operational_metadata():
    commits = (
        {
            "event": "committed",
            "sha": "a" * 40,
            "author": {"date": "2026-07-26T00:00:00Z"},
        },
        {
            "event": "committed",
            "sha": "b" * 40,
            "author": {"date": "2026-07-26T00:01:00Z"},
        },
    )
    evidence = inspect(timeline=commits)
    assert evidence["primary_readiness_classification"] == "READY_FOR_SEPARATE_MERGE_AUTHORIZATION"
    assert evidence["observed_development_links"] == []
    assert evidence["post_merge_verification_obligations"][0]["issue_number"] == 608
    assert [item["commit_sha"] for item in evidence["observed_timeline_evidence"]] == [
        "a" * 40,
        "b" * 40,
    ]
    assert {item["classification"] for item in evidence["observed_timeline_evidence"]} == {
        "operational_commit_event"
    }


def test_committed_events_coexist_with_informational_cross_reference_and_residual():
    evidence = inspect(
        timeline=(
            {
                "event": "cross-referenced",
                "source": {"issue": {"number": 608}},
            },
            {
                "event": "committed",
                "sha": "a" * 40,
                "author": {"date": "2026-07-26T00:00:00Z"},
            },
        )
    )
    assert evidence["primary_readiness_classification"] == "READY_FOR_SEPARATE_MERGE_AUTHORIZATION"
    assert evidence["residual_platform_limitations"][0]["availability"] == "platform_not_exposed"
    assert {item["classification"] for item in evidence["observed_timeline_evidence"]} == {
        "informational_cross_reference",
        "operational_commit_event",
    }


@pytest.mark.parametrize(
    "timeline",
    (
        ({"event": "committed", "sha": "a" * 40},),
        ({"event": "committed", "sha": "short", "author": {"date": "2026-07-26T00:00:00Z"}},),
        (
            {
                "event": "committed",
                "sha": "a" * 40,
                "author": {"date": "2026-07-26T00:00:00Z"},
                "source": {"issue": {"number": 608}},
            },
        ),
    ),
)
def test_malformed_or_linkage_shaped_committed_event_remains_evidence_incomplete(timeline):
    evidence = inspect(timeline=timeline)
    assert evidence["primary_readiness_classification"] == "EVIDENCE_INCOMPLETE"
    assert evidence["observed_timeline_evidence"][0]["classification"] == "unknown_timeline_event"


@pytest.mark.parametrize(
    "timeline",
    (
        ({"event": "unrecognized", "source": {"issue": {"number": 608}}},),
        ({"source": {"issue": {"number": 608}}},),
    ),
)
def test_unknown_or_malformed_timeline_event_remains_evidence_incomplete(timeline):
    evidence = inspect(timeline=timeline)
    assert evidence["primary_readiness_classification"] == "EVIDENCE_INCOMPLETE"
    assert evidence["observed_timeline_evidence"][0]["classification"] == "unknown_timeline_event"


def test_unavailable_and_partial_transport_sources_are_incomplete_not_ready():
    evidence = inspect(graphql_error=True, timeline_error=True, effect_available=True)
    assert evidence["primary_readiness_classification"] == "EVIDENCE_INCOMPLETE"
    assert evidence["evidence_source_availability"]["graphql_closing_references"] == "partial"
    assert evidence["evidence_source_availability"]["timeline"] == "partial"
    assert "CLOSURE_EVIDENCE_INCOMPLETE" in codes(evidence["closure_risk_findings"])


def test_pre_merge_state_mismatch_and_unknown_state_are_not_merge_ready():
    mismatch = inspect(state="closed", effect_available=True)
    assert "ISSUE_STATE_PRECONDITION_MISMATCH" in codes(mismatch["closure_risk_findings"])
    unknown = inspect(state="unknown", effect_available=True)
    assert unknown["primary_readiness_classification"] == "NOT_READY"


def test_duplicate_contract_and_unknown_discoverable_issue_are_rejected_or_incomplete():
    with pytest.raises(INSPECTOR.ClosureLinkageError, match="duplicate"):
        inspect(declarations=contract() * 2)
    evidence = inspect(body="Fixes #999")
    assert {"ISSUE_ROLE_UNDECLARED", "CLOSURE_AUTHORITY_MISSING"} <= codes(
        evidence["closure_risk_findings"]
    )


def test_graphql_connection_paginates_all_pages_and_rejects_duplicates():
    pages = iter(
        (
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "nodes": [{"number": 608}],
                                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                            }
                        }
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "nodes": [{"number": 609}],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    }
                }
            },
        )
    )

    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(next(pages)))

    transport = INSPECTOR.ReadOnlyGitHubTransport(runner)
    assert transport.closing_issues("nicho1ab", "RecordsTracker", 615) == [
        {"number": 608},
        {"number": 609},
    ]

    duplicate = {
        "data": {
            "repository": {
                "pullRequest": {
                    "closingIssuesReferences": {
                        "nodes": [{"number": 608}, {"number": 608}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }
    with pytest.raises(INSPECTOR.ClosureLinkageError, match="duplicate"):
        INSPECTOR.ReadOnlyGitHubTransport(
            lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(duplicate))
        ).closing_issues("nicho1ab", "RecordsTracker", 615)


def test_schema_rejects_malformed_contract_evidence_and_unknown_properties():
    evidence = inspect(effect_available=True)
    malformed = json.loads(json.dumps(evidence))
    malformed["pull_request"]["base_sha"] = "short"
    with pytest.raises(INSPECTOR.ClosureLinkageError):
        INSPECTOR.validate_evidence(malformed)
    malformed = json.loads(json.dumps(evidence))
    malformed["raw_pr_body"] = "forbidden"
    with pytest.raises(INSPECTOR.ClosureLinkageError):
        INSPECTOR.validate_evidence(malformed)
    malformed = json.loads(json.dumps(evidence))
    malformed["observed_timeline_evidence"] = [
        {
            "event": "cross-referenced",
            "classification": "unexpected",
            "issue_number": 608,
            "target_pull_request_number": 615,
            "actor": None,
            "occurred_at": None,
            "commit_sha": None,
            "explicit_closure_semantic": False,
        }
    ]
    with pytest.raises(INSPECTOR.ClosureLinkageError):
        INSPECTOR.validate_evidence(malformed)


def test_post_merge_reports_unauthorized_closure_without_recovery_action():
    evidence = inspect(effect_available=True)
    findings = INSPECTOR.verify_post_merge(
        evidence,
        post_collection(
            evidence,
            {
                608: {
                    "state": "closed",
                    "state_reason": "completed",
                    "closed_at": "2026-07-26T01:00:00Z",
                }
            },
            merged_at="2026-07-26T00:30:00Z",
        ),
    )
    assert "POST_MERGE_UNAUTHORIZED_CLOSURE" in codes(findings)
    assert "POST_MERGE_UNAUTHORIZED_REOPEN" not in codes(findings)


def test_post_merge_handles_authorized_closure_reopen_reason_and_timestamp_cases():
    authorized = inspect(
        declarations=contract(
            remain_open=False,
            expected_post_merge_state="closed",
            expected_post_merge_state_reason="completed",
            closure_authorized=True,
        ),
        body="Fixes #608",
        effect_available=True,
    )
    matched = INSPECTOR.verify_post_merge(
        authorized,
        post_collection(
            authorized,
            {
                608: {
                    "state": "closed",
                    "state_reason": "completed",
                    "closed_at": "2026-07-26T01:00:00Z",
                }
            },
            merged_at="2026-07-26T00:30:00Z",
        ),
    )
    assert codes(matched) == {"POST_MERGE_STATE_MATCHED"}
    reopened = INSPECTOR.verify_post_merge(
        authorized,
        post_collection(
            authorized,
            {
                608: {
                    "state": "open",
                    "state_reason": "reopened",
                    "closed_at": "2026-07-26T01:00:00Z",
                    "reopened_at": "2026-07-26T00:00:00Z",
                }
            },
            merged_at="2026-07-26T00:30:00Z",
        ),
    )
    assert {"POST_MERGE_UNAUTHORIZED_REOPEN", "POST_MERGE_TIMESTAMP_AMBIGUOUS"} <= codes(reopened)


def test_post_merge_reports_missing_unknown_and_reason_mismatch_outcomes():
    evidence = inspect(effect_available=True)
    assert codes(INSPECTOR.verify_post_merge(evidence, post_collection(evidence))) == {
        "CLOSURE_SOURCE_UNKNOWN"
    }
    missing = inspect(
        declarations=contract(
            remain_open=False, expected_post_merge_state="closed", closure_authorized=True
        ),
        effect_available=True,
    )
    assert "POST_MERGE_EXPECTED_CLOSURE_MISSING" in codes(
        INSPECTOR.verify_post_merge(missing, post_collection(missing, {608: {"state": "open"}}))
    )
    reason = inspect(
        declarations=contract(expected_post_merge_state_reason="not_planned"), effect_available=True
    )
    assert "POST_MERGE_STATE_REASON_MISMATCH" in codes(
        INSPECTOR.verify_post_merge(
            reason,
            post_collection(reason, {608: {"state": "open", "state_reason": "completed"}}),
        )
    )


def test_pr_615_fixture_regression_contains_sanitized_historical_evidence_only():
    fixture = json.loads(
        (ROOT / "tests/fixtures/closure_linkage/pr-615-da-031-v1.json").read_text(encoding="utf-8")
    )
    assert fixture["observed_closing_references"] == {
        "pr_body_issue_numbers": [],
        "graphql_issue_numbers": [],
    }
    evidence = inspect(timeline=fixture["observed_timeline_evidence"])
    assert evidence["primary_readiness_classification"] == "NOT_READY"
    assert fixture["later_reopened"] is True


def test_malformed_observable_source_remains_evidence_incomplete():
    evidence = inspect(graphql_error=True, graphql_error_message="malformed GraphQL response")
    assert evidence["primary_readiness_classification"] == "EVIDENCE_INCOMPLETE"
    assert evidence["evidence_source_availability"]["graphql_closing_references"] == "malformed"


def test_platform_residual_cannot_be_caller_supplied_to_bypass_observable_collection():
    evidence = inspect(effect_available=True, graphql_error=True)
    assert evidence["evidence_source_availability"]["development_link_closure_effect"] == (
        "platform_not_exposed"
    )
    assert evidence["primary_readiness_classification"] == "EVIDENCE_INCOMPLETE"


def test_read_only_transport_rejects_mutation_shaped_endpoint():
    with pytest.raises(INSPECTOR.ClosureLinkageError):
        INSPECTOR.ReadOnlyGitHubTransport().api("POST/repos/nicho1ab/RecordsTracker")


def test_contract_path_is_repository_relative_and_does_not_read_an_external_file(
    tmp_path, monkeypatch
):
    root = tmp_path / "repository"
    nested = root / "contracts" / "nested"
    nested.mkdir(parents=True)
    contract_path = nested / "contract.json"
    contract_path.write_text("[]", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text("external", encoding="utf-8")
    monkeypatch.setattr(INSPECTOR, "ROOT", root)
    assert (
        INSPECTOR._repository_contract_path(Path("contracts/nested/contract.json")) == contract_path
    )
    for rejected in (
        Path("../outside.json"),
        outside,
        Path("Z:/outside.json"),
        Path("//host/share/x"),
    ):
        with pytest.raises(INSPECTOR.ClosureLinkageError, match="contract path rejected"):
            INSPECTOR._repository_contract_path(rejected)
    assert outside.read_text(encoding="utf-8") == "external"


def test_contract_path_rejects_a_symlink_escape_when_supported(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("external", encoding="utf-8")
    escape = root / "escape.json"
    try:
        escape.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")
    monkeypatch.setattr(INSPECTOR, "ROOT", root)
    with pytest.raises(INSPECTOR.ClosureLinkageError, match="outside repository"):
        INSPECTOR._repository_contract_path(Path("escape.json"))


def test_post_merge_collection_uses_only_fixed_declared_issue_endpoints():
    evidence = inspect(effect_available=True)
    transport = FixtureTransport(state="closed", state_reason="completed")
    collection = INSPECTOR.collect_post_merge_issue_states(evidence, transport)
    assert collection["availability"] == "complete"
    assert collection["issue_states"] == [
        {
            "issue_number": 608,
            "state": "closed",
            "state_reason": "completed",
            "closed_at": None,
            "reopened_at": None,
        }
    ]
    assert transport.endpoints == [
        "repos/nicho1ab/RecordsTracker",
        "repos/nicho1ab/RecordsTracker/pulls/615",
        "repos/nicho1ab/RecordsTracker/issues/608",
    ]
    assert "repos/nicho1ab/RecordsTracker/issues/999" not in transport.endpoints


def test_post_merge_collection_rejects_identity_mismatch_and_fails_closed_when_partial():
    evidence = inspect(effect_available=True)
    with pytest.raises(INSPECTOR.ClosureLinkageError, match="repository identity mismatch"):
        INSPECTOR.collect_post_merge_issue_states(
            evidence, FixtureTransport(repository_name="other/repository")
        )
    partial = INSPECTOR.collect_post_merge_issue_states(
        evidence, FixtureTransport(failed_issue_numbers=(608,))
    )
    findings = INSPECTOR.verify_post_merge(evidence, partial)
    assert partial["availability"] == "incomplete"
    assert {"CLOSURE_EVIDENCE_INCOMPLETE", "CLOSURE_SOURCE_UNKNOWN"} <= codes(findings)


def test_post_merge_verification_rejects_undeclared_or_arbitrary_observations():
    evidence = inspect(effect_available=True)
    with pytest.raises(INSPECTOR.ClosureLinkageError, match="undeclared issue"):
        INSPECTOR.verify_post_merge(
            evidence,
            post_collection(evidence, {999: {"state": "closed"}}),
        )
