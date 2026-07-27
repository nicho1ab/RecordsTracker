"""Deterministic DA-030 coverage for guarded PR-body persistence attempts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "prepare_pr_body.py"
BODY = (ROOT / "tests" / "fixtures" / "pr_body_validation" / "pr-615-full-template.md").read_text(
    encoding="utf-8"
)
SCOPE = ("scripts/prepare_pr_body.py",)


def _prepare() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prepare_pr_body_persistence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SequenceTransport:
    """Sanitized deterministic REST/GraphQL transport with observable PATCH count."""

    def __init__(
        self,
        rest_bodies: list[str],
        *,
        graphql_bodies: list[str] | None = None,
        response_body: str | None = None,
        changed_files: tuple[str, ...] = SCOPE,
        fail_patch: bool = False,
        fail_observation_after_patch: bool = False,
        head_after_patch: str = "head-sha",
        state_after_patch: str = "open",
        scope_after_patch: tuple[str, ...] | None = None,
    ) -> None:
        self.rest_bodies = iter(rest_bodies)
        self.last_rest_body = rest_bodies[-1]
        self.graphql_bodies = iter(graphql_bodies) if graphql_bodies is not None else None
        self.last_graphql_body = graphql_bodies[-1] if graphql_bodies else None
        self.response_body = response_body
        self.changed_files_value = changed_files
        self.scope_after_patch = scope_after_patch
        self.head_after_patch = head_after_patch
        self.state_after_patch = state_after_patch
        self.fail_patch = fail_patch
        self.fail_observation_after_patch = fail_observation_after_patch
        self.patch_calls: list[tuple[str, int, str]] = []
        self.error_type: type[Exception] = RuntimeError

    def repository(self, repository: str) -> str:
        return repository

    def pull_request(self, _repository: str, _number: int) -> dict[str, object]:
        if self.fail_observation_after_patch and self.patch_calls:
            raise self.error_type("sanitized read failure")
        try:
            self.last_rest_body = next(self.rest_bodies)
        except StopIteration:
            pass
        return {
            "state": self.state_after_patch if self.patch_calls else "open",
            "draft": False,
            "title": "Sanitized test PR",
            "body": self.last_rest_body,
            "base": {"ref": "main", "sha": "base-sha"},
            "head": {
                "ref": "persistence",
                "sha": self.head_after_patch if self.patch_calls else "head-sha",
            },
        }

    def changed_files(self, _repository: str, _number: int) -> tuple[str, ...]:
        if self.patch_calls and self.scope_after_patch is not None:
            return self.scope_after_patch
        return self.changed_files_value

    def update_body(self, repository: str, number: int, body: str) -> dict[str, object]:
        self.patch_calls.append((repository, number, body))
        if self.fail_patch:
            raise self.error_type("sanitized PATCH failure")
        return {"body": self.response_body if self.response_body is not None else body}

    def graphql_body(self, _repository: str, _number: int) -> str:
        if self.graphql_bodies is None:
            raise self.error_type("GraphQL unavailable")
        try:
            self.last_graphql_body = next(self.graphql_bodies)
        except StopIteration:
            pass
        assert self.last_graphql_body is not None
        return self.last_graphql_body


def _preconditions(prepare: ModuleType, initial: str, candidate: str) -> object:
    return prepare.MutationPreconditions(
        repository="nicho1ab/RecordsTracker",
        number=616,
        state="open",
        draft=False,
        base="main",
        base_sha="base-sha",
        head="persistence",
        head_sha="head-sha",
        scope_sha256=prepare.changed_scope_sha256(SCOPE),
        body_sha256=prepare.body_sha256(initial),
        candidate_sha256=prepare.body_sha256(candidate),
        authorization="body-only",
    )


def _apply(
    prepare: ModuleType,
    transport: SequenceTransport,
    initial: str,
    candidate: str,
    **kwargs: object,
):
    transport.error_type = prepare.GitHubApiError
    options: dict[str, object] = {
        "sleeper": lambda _seconds: None,
        "now": lambda: "2026-07-26T00:00:00+00:00",
    }
    options.update(kwargs)
    return prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="616",
        proposal=candidate,
        preconditions=_preconditions(prepare, initial, candidate),
        confirmed=True,
        **options,
    )


def test_precondition_mismatch_has_zero_patches() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    transport = SequenceTransport([BODY])
    preconditions = _preconditions(prepare, BODY, candidate)._replace(body_sha256="0" * 64)

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="616",
        proposal=candidate,
        preconditions=preconditions,
        confirmed=True,
        sleeper=lambda _seconds: None,
    )

    assert attempt.outcome is prepare.PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED
    assert attempt.mutation_count == 0
    assert transport.patch_calls == []


def test_stale_candidate_hash_has_zero_patches() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    transport = SequenceTransport([BODY])
    preconditions = _preconditions(prepare, BODY, candidate)._replace(candidate_sha256="f" * 64)

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="616",
        proposal=candidate,
        preconditions=preconditions,
        confirmed=True,
        sleeper=lambda _seconds: None,
    )

    assert attempt.outcome is prepare.PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED
    assert attempt.mutation_count == 0


def test_utf8_payload_is_body_only_hashable_and_contains_no_bom(tmp_path: Path) -> None:
    prepare = _prepare()
    body = 'Line — café\n"quoted"'
    payload = prepare.build_body_payload(body)
    captured: list[tuple[Path, bytes]] = []

    def runner(command, **_kwargs):
        path = Path(command[-1])
        captured.append((path, path.read_bytes()))
        return type("Result", (), {"stdout": '{"body":"ok"}'})()

    prepare.GitHubTransport(runner).update_body("nicho1ab/RecordsTracker", 616, body)

    assert payload == captured[0][1]
    assert not payload.startswith(b"\xef\xbb\xbf")
    assert json.loads(payload.decode("utf-8")) == {"body": body}
    assert not captured[0][0].exists()


def test_immediate_rest_and_graphql_convergence_records_single_mutation() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    transport = SequenceTransport([BODY, BODY, candidate], graphql_bodies=[BODY, candidate])

    attempt = _apply(prepare, transport, BODY, candidate)

    assert attempt.outcome is prepare.PersistenceOutcome.IMMEDIATE_CONVERGENCE
    assert attempt.mutation_count == 1
    assert transport.patch_calls == [("nicho1ab/RecordsTracker", 616, candidate)]
    assert attempt.payload_keys == ("body",)


def test_pr_615_style_mojibake_can_converge_only_after_bounded_read_only_polling() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA—030")
    mojibake = candidate.replace("—", "â€”")
    transport = SequenceTransport(
        [BODY, BODY, mojibake, candidate], graphql_bodies=[BODY, mojibake, candidate]
    )

    attempt = _apply(prepare, transport, BODY, candidate, max_observations=2)

    assert attempt.outcome is prepare.PersistenceOutcome.DELAYED_CONVERGENCE
    assert attempt.mutation_count == 1
    assert any(item.mojibake_detected for item in attempt.observations)


def test_stable_mismatch_never_retries_or_rolls_back() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    mismatch = BODY.replace("DA-029", "Different valid evidence")
    transport = SequenceTransport([BODY, BODY, mismatch], graphql_bodies=[BODY, mismatch])

    attempt = _apply(prepare, transport, BODY, candidate, max_observations=2)

    assert attempt.outcome is prepare.PersistenceOutcome.STABLE_PERSISTENCE_MISMATCH
    assert attempt.mutation_count == 1
    assert len(transport.patch_calls) == 1


def test_invalid_mutation_response_is_distinct_after_one_patch() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")

    class InvalidResponseTransport(SequenceTransport):
        def update_body(self, repository: str, number: int, body: str) -> dict[str, object]:
            super().update_body(repository, number, body)
            return {"not_body": body}

    invalid = InvalidResponseTransport([BODY, BODY])
    attempt = _apply(prepare, invalid, BODY, candidate)

    assert attempt.outcome is prepare.PersistenceOutcome.MUTATION_RESPONSE_INVALID
    assert attempt.mutation_count == len(invalid.patch_calls) == 1


def test_malformed_mutation_response_is_not_folded_into_api_failure() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")

    class MalformedResponseTransport(SequenceTransport):
        def update_body(self, repository: str, number: int, body: str) -> dict[str, object]:
            super().update_body(repository, number, body)
            raise prepare.MutationResponseError("sanitized malformed response")

    malformed = MalformedResponseTransport([BODY, BODY])
    attempt = _apply(prepare, malformed, BODY, candidate)

    assert attempt.outcome is prepare.PersistenceOutcome.MUTATION_RESPONSE_INVALID
    assert attempt.mutation_count == len(malformed.patch_calls) == 1


def test_transient_rest_graphql_disagreement_is_not_success_until_converged() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    transport = SequenceTransport(
        [BODY, BODY, candidate, candidate],
        graphql_bodies=[BODY, BODY, candidate],
    )

    attempt = _apply(prepare, transport, BODY, candidate, max_observations=2)

    assert attempt.outcome is prepare.PersistenceOutcome.DELAYED_CONVERGENCE
    assert (
        prepare.PersistenceOutcome.TRANSIENT_REPRESENTATION_DISAGREEMENT
        in attempt.classifications
    )


def test_stable_rest_graphql_disagreement_is_not_success() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    graph_mismatch = BODY.replace("DA-029", "GraphQL disagreement")
    transport = SequenceTransport(
        [BODY, BODY, candidate], graphql_bodies=[BODY, graph_mismatch]
    )

    attempt = _apply(prepare, transport, BODY, candidate, max_observations=0)

    assert attempt.outcome is prepare.PersistenceOutcome.STABLE_PERSISTENCE_MISMATCH
    assert (
        prepare.PersistenceOutcome.TRANSIENT_REPRESENTATION_DISAGREEMENT
        in attempt.classifications
    )


def test_graphql_unavailability_is_informational_after_rest_convergence() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    transport = SequenceTransport([BODY, BODY, candidate])

    attempt = _apply(prepare, transport, BODY, candidate)

    assert attempt.outcome is prepare.PersistenceOutcome.IMMEDIATE_CONVERGENCE
    assert prepare.PersistenceOutcome.GRAPHQL_UNAVAILABLE in attempt.classifications
    assert any(
        item.source.endswith(":graphql") and item.normalized_body_sha256 is None
        for item in attempt.observations
    )


def test_canonical_comparison_accepts_crlf_but_rejects_mojibake() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA—030")
    assert prepare.body_sha256(candidate) == prepare.body_sha256(candidate.replace("\n", "\r\n"))
    assert prepare.body_sha256(candidate) != prepare.body_sha256(candidate.replace("—", "â€”"))


@pytest.mark.parametrize("changed", ["head", "scope"])
def test_identity_or_scope_change_after_patch_blocks_success(changed: str) -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    transport = SequenceTransport(
        [BODY, BODY, candidate],
        graphql_bodies=[BODY, candidate],
        head_after_patch="other-head" if changed == "head" else "head-sha",
        scope_after_patch=("unexpected.py",) if changed == "scope" else None,
    )

    attempt = _apply(prepare, transport, BODY, candidate)

    assert attempt.outcome is prepare.PersistenceOutcome.PR_IDENTITY_CHANGED
    assert attempt.mutation_count == 1


def test_noncandidate_body_change_during_polling_is_truthful_unexplained_classification() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    first = BODY.replace("DA-029", "First observed replacement")
    second = BODY.replace("DA-029", "Second observed replacement")
    transport = SequenceTransport([BODY, BODY, first, second], graphql_bodies=[BODY, first, second])

    attempt = _apply(prepare, transport, BODY, candidate, max_observations=2)

    assert attempt.outcome is prepare.PersistenceOutcome.UNEXPLAINED_NONCANDIDATE_BODY_CHANGE
    assert attempt.mutation_count == 1


def test_closed_pr_after_patch_is_identity_change_not_observation_failure() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    transport = SequenceTransport([BODY, BODY, candidate], state_after_patch="closed")

    attempt = _apply(prepare, transport, BODY, candidate)

    assert attempt.outcome is prepare.PersistenceOutcome.PR_IDENTITY_CHANGED
    assert attempt.mutation_count == len(transport.patch_calls) == 1


def test_mutation_and_observation_failures_are_distinct_and_preserve_budget() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    patch_failure = _apply(
        prepare, SequenceTransport([BODY, BODY], fail_patch=True), BODY, candidate
    )
    observation_failure = _apply(
        prepare,
        SequenceTransport([BODY, BODY], fail_observation_after_patch=True),
        BODY,
        candidate,
    )

    assert patch_failure.outcome is prepare.PersistenceOutcome.MUTATION_API_FAILED
    assert observation_failure.outcome is prepare.PersistenceOutcome.OBSERVATION_API_FAILED
    assert patch_failure.mutation_count == observation_failure.mutation_count == 1


def test_post_persistence_validation_failure_is_not_a_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    monkeypatch.setattr(prepare, "validate_open_pull_request", lambda *_args: ["ordered failure"])
    transport = SequenceTransport([BODY, BODY, candidate], graphql_bodies=[BODY, candidate])

    attempt = _apply(prepare, transport, BODY, candidate)

    assert attempt.outcome is prepare.PersistenceOutcome.POST_PERSISTENCE_VALIDATION_FAILED
    assert attempt.validator_violations == ("ordered failure",)


def test_already_matching_body_cannot_hide_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare = _prepare()
    monkeypatch.setattr(prepare, "validate_open_pull_request", lambda *_args: ["ordered failure"])
    transport = SequenceTransport([BODY])

    attempt = _apply(prepare, transport, BODY, BODY)

    assert attempt.outcome is prepare.PersistenceOutcome.POST_PERSISTENCE_VALIDATION_FAILED
    assert attempt.mutation_count == 0


def test_interruption_after_patch_reports_one_possible_mutation_without_second_patch() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    mismatch = BODY.replace("DA-029", "Persistent mismatch")
    transport = SequenceTransport([BODY, BODY, mismatch], graphql_bodies=[BODY, mismatch])

    attempt = _apply(
        prepare,
        transport,
        BODY,
        candidate,
        max_observations=1,
        sleeper=lambda _seconds: (_ for _ in ()).throw(RuntimeError("cancelled")),
    )

    assert attempt.outcome is prepare.PersistenceOutcome.OBSERVATION_API_FAILED
    assert attempt.mutation_count == len(transport.patch_calls) == 1


def test_evidence_is_deterministic_and_never_contains_full_body() -> None:
    prepare = _prepare()
    candidate = BODY.replace("DA-029", "DA-030")
    transport = SequenceTransport([BODY, BODY, candidate], graphql_bodies=[BODY, candidate])

    attempt = _apply(prepare, transport, BODY, candidate)
    evidence = attempt.to_evidence()
    serialized = json.dumps(evidence, sort_keys=True)

    assert evidence["schema_version"] == "pr-body-persistence-attempt-v1"
    assert evidence["globally_atomic"] is False
    assert candidate not in serialized
    assert "secret" not in serialized.casefold()
    assert evidence["payload_keys"] == ["body"]


def test_evidence_destination_is_limited_to_ignored_processed_storage(
    tmp_path: Path,
) -> None:
    prepare = _prepare()
    attempt = prepare.PersistenceAttempt(
        preconditions=_preconditions(prepare, BODY, BODY),
        candidate_normalized_sha256=prepare.body_sha256(BODY),
        candidate_request_sha256="a" * 64,
    )

    with pytest.raises(prepare.ProposalValidationError, match="data/processed"):
        prepare._write_persistence_evidence(ROOT, tmp_path / "evidence.json", attempt)


def test_payload_cleanup_failure_does_not_hide_successful_patch_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare = _prepare()

    def runner(_command, **_kwargs):
        return type("Result", (), {"stdout": '{"body":"ok"}'})()

    monkeypatch.setattr(Path, "unlink", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))

    response = prepare.GitHubTransport(runner).update_body("nicho1ab/RecordsTracker", 616, "body")

    assert response == {"body": "ok"}
