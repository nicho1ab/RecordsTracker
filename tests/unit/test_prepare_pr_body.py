from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "prepare_pr_body.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prepare_pr_body", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _completed_body() -> str:
    template = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    replacements = (
        ("<!-- Example: Closes #123 -->", "Closes #608"),
        (
            "- Intended outcome:",
            "- Intended outcome: Preflight catches invalid PR evidence.",
        ),
        (
            "- Major files or components changed:",
            "- Major files or components changed: verification tooling",
        ),
        (
            "- Important behavior intentionally left unchanged or out of scope:",
            "- Important behavior intentionally left unchanged or out of scope: human approval",
        ),
        (
            "- Reviewer UI regression contracts: <!-- List affected, added, updated, "
            "superseded, or Not applicable - <specific reason>. -->",
            "- Reviewer UI regression contracts: Added `RT-RC-001`; remaining "
            "contracts are not applicable - verification tooling only.",
        ),
        (
            "| <!-- One criterion per row --> | <!-- Test, diff, review artifact, "
            "or other concrete result --> |",
            "| PR body is preflighted | Focused validator test passes |",
        ),
        (
            "| `<!-- command -->` | <!-- Pass, fail, or not run --> | "
            "<!-- Implementation-caused, pre-existing, environmental, or none --> |",
            "| `pytest tests/unit/test_prepare_pr_body.py` | Pass | none |",
        ),
        ("<!-- None, or command and disposition -->", "None"),
        ("<!-- None, or command and evidence that it predates this change -->", "None"),
        ("<!-- None, or command and environment limitation -->", "None"),
        (
            "- Tests intentionally not run and why:",
            "- Tests intentionally not run and why: Full suite not run for this focused test.",
        ),
        (
            "<!-- Updated docs, or why no user-facing or documentation-impacting "
            "behavior changed -->",
            "Developer workflow guidance updated.",
        ),
        (
            "- Assumptions and limitations:",
            "- Assumptions and limitations: Human review remains controlling.",
        ),
        (
            "- Remaining risks or follow-up:",
            "- Remaining risks or follow-up: Required GitHub checks remain authoritative.",
        ),
    )
    completed = template
    for old, new in replacements:
        completed = completed.replace(old, new)
    for boundary in (
        "Schemas and migrations",
        "Ingestion and source-connector contracts",
        "Security and privacy",
        "Production data and correction behavior",
        "Deployment and infrastructure",
        "Repository governance",
        "Required GitHub workflows and checks",
        "Tests or checks weakened to obtain passage",
    ):
        completed = completed.replace(
            f"| {boundary} |  |  |",
            f"| {boundary} | Authorized change | Focused Issue #608 contract evidence. |",
        )
    return completed


def test_render_copies_the_authoritative_template(tmp_path: Path) -> None:
    prepare = _load_module()
    output = tmp_path / "body.md"

    assert prepare.render_body(output) == 0
    template = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    assert output.read_text(encoding="utf-8") == template


def test_compact_policy_preparation_is_deterministic_and_independently_valid() -> None:
    prepare = _load_module()
    verification = _load_module_from_path(
        "independent_verification_for_compact_policy",
        ROOT / "scripts" / "check_independent_verification.py",
    )
    paths = ["docs/developer/codex-workflow.md"]
    scope_hash = prepare.changed_scope_sha256(paths)
    identity = {
        "repository": "nicho1ab/RecordsTracker",
        "pull_request_number": 617,
        "base_ref": "main",
        "base_sha": "a" * 40,
        "head_ref": "codex/test",
        "head_sha": "a" * 40,
        "tree_sha": "c" * 40,
        "changed_file_inventory_hash": scope_hash,
        "pr_body_hash": "d" * 64,
        "policy_version": "1.0.2",
        "schema_version": "recordstracker.evidence-reuse-validation-impact.v1",
        "validator_version": "evaluator-v1",
        "governed_boundary_classification": ["Repository governance"],
        "dependency_state_digest": "d" * 64,
    }
    policy_input = {
        "kind": "input",
        "schema_version": "recordstracker.evidence-reuse-validation-impact.v1",
        "repository_state": identity,
        "changed_file_inventory": {"complete": True, "paths": paths},
        "dependency_state": {"status": "known", "digest": "d" * 64},
        "evidence": [],
        "required_check_runs": [
            {
                "check_name": check,
                "run_id": number,
                "job_id": number + 10,
                "status": "success",
                "conclusion": "success",
                "head_sha": "a" * 40,
                "tree_sha": "c" * 40,
                "changed_file_inventory_hash": scope_hash,
                "pr_body_hash": "d" * 64,
            }
            for number, check in enumerate(("validate", "docs-check", "fixtures", "security"), 1)
        ],
    }
    completed = _completed_body()
    start = completed.index("## Validation impact and evidence delta")
    end = completed.index("## UI and accessibility evidence", start)
    prefix = completed[:start]
    suffix = completed[end:]
    first = prepare.render_compact_policy_evidence(
        policy_input,
        delta="Documentation delta.",
        validation_newly_performed=["focused"],
        live_evidence_recollected=["required checks"],
        body_prefix=prefix,
        body_suffix=suffix,
    )
    assert first == prepare.render_compact_policy_evidence(
        policy_input,
        delta="Documentation delta.",
        validation_newly_performed=["focused"],
        live_evidence_recollected=["required checks"],
        body_prefix=prefix,
        body_suffix=suffix,
    )
    assert "command" not in first.lower()
    body = prefix + first + suffix
    envelope = json.loads(first.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert envelope["policy_input"]["repository_state"]["pr_body_hash"] == (
        verification.canonical_compact_body_sha256(body)
    )
    live = {
        **{
            field: envelope["policy_input"]["repository_state"][field]
            for field in (
                "repository",
                "pull_request_number",
                "base_ref",
                "base_sha",
                "head_ref",
                "head_sha",
            )
        },
        "body": body,
        "changed_file_inventory_complete": True,
        "required_check_runs_complete": True,
        "required_check_runs": [
            {
                field: run[field]
                for field in ("check_name", "run_id", "job_id", "status", "conclusion", "head_sha")
            }
            | {
                "repository": envelope["policy_input"]["repository_state"]["repository"],
                "event": "pull_request",
                "pull_request_numbers": [
                    envelope["policy_input"]["repository_state"]["pull_request_number"]
                ],
                "job_run_id": run["run_id"],
            }
            for run in envelope["policy_input"]["required_check_runs"]
        ],
    }
    assert verification.validate_pr_evidence(ROOT, body, paths, live_pr_state=live).violations == ()


def test_preflight_uses_validator_rules_and_actionable_failures(tmp_path: Path, capsys) -> None:
    prepare = _load_module()
    body = tmp_path / "body.md"
    changed = tmp_path / "changed.txt"
    body.write_text(_completed_body(), encoding="utf-8")
    changed.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert (
        prepare.preflight_body(
            body_path=body,
            changed_files_path=changed,
            base="origin/main",
            repo_root=ROOT,
        )
        == 1
    )
    failure_message = (
        "Required GitHub workflows and checks: changes require Concern - review required"
    )
    assert failure_message in capsys.readouterr().out

    body.write_text(
        _completed_body().replace(
            "| Required GitHub workflows and checks | Authorized change | "
            "Focused Issue #608 contract evidence. |",
            "| Required GitHub workflows and checks | Concern - review required | "
            "Required validation changes are reviewed. |",
        ),
        encoding="utf-8",
    )
    assert (
        prepare.preflight_body(
            body_path=body,
            changed_files_path=changed,
            base="origin/main",
            repo_root=ROOT,
        )
        == 0
    )
    assert "Independent verification passed." in capsys.readouterr().out


def test_automatic_changed_file_discovery_includes_untracked_files(monkeypatch) -> None:
    prepare = _load_module()
    commands: list[tuple[str, ...]] = []
    outputs = iter(
        (
            "committed.py\nrenamed.py\ndeleted.py\nshared.py\n",
            "unstaged.py\nshared.py\n",
            "staged.py\nshared.py\n",
            "untracked.py\n",
        )
    )

    def fake_run(command, **_kwargs):
        commands.append(command)
        output = next(outputs)
        return CompletedProcess(command, 0, stdout=output)

    monkeypatch.setattr(prepare.subprocess, "run", fake_run)

    discovered = prepare._changed_files_from_git("origin/main")

    assert discovered == [
        "committed.py",
        "renamed.py",
        "deleted.py",
        "shared.py",
        "unstaged.py",
        "staged.py",
        "untracked.py",
    ]
    assert ("git", "ls-files", "--others", "--exclude-standard") in commands
    assert "ignored.tmp" not in discovered


class FakeTransport:
    def __init__(
        self,
        bodies: list[str],
        changed_files: tuple[str, ...] = ("scripts/prepare_pr_body.py",),
    ) -> None:
        self._bodies = iter(bodies)
        self.changed_files_value = changed_files
        self.update_calls: list[tuple[str, int, str]] = []
        self.last_body = bodies[-1]

    def repository(self, repository: str) -> str:
        return repository

    def pull_request(self, _repository: str, _number: int) -> dict[str, object]:
        try:
            self.last_body = next(self._bodies)
        except StopIteration:
            pass
        return {
            "state": "open",
            "body": self.last_body,
            "base": {"ref": "main", "sha": "base-sha"},
            "head": {"ref": "repair", "sha": "head-sha"},
        }

    def changed_files(self, _repository: str, _number: int) -> tuple[str, ...]:
        return self.changed_files_value

    def update_body(self, repository: str, number: int, body: str) -> dict[str, object]:
        self.update_calls.append((repository, number, body))
        return {"body": body}


def _fetch(prepare: ModuleType, transport: FakeTransport, body: str):
    return prepare.fetch_open_pull_request(transport, "nicho1ab/RecordsTracker", "#613")


def _preconditions(
    prepare: ModuleType,
    current: str,
    proposal: str,
    *,
    body_hash: str | None = None,
    changed_files: tuple[str, ...] = ("scripts/prepare_pr_body.py",),
) -> object:
    return prepare.MutationPreconditions(
        repository="nicho1ab/RecordsTracker",
        number=613,
        state="open",
        draft=False,
        base="main",
        base_sha="base-sha",
        head="repair",
        head_sha="head-sha",
        scope_sha256=prepare.changed_scope_sha256(changed_files),
        body_sha256=body_hash or prepare.body_sha256(current),
        candidate_sha256=prepare.body_sha256(proposal),
        authorization="body-only",
    )


def test_fetches_live_body_paginated_files_and_pr_identity() -> None:
    prepare = _load_module()
    commands: list[tuple[str, ...]] = []

    def runner(command, **_kwargs):
        commands.append(command)
        if command[2] == "repos/nicho1ab/RecordsTracker":
            return CompletedProcess(command, 0, stdout='{"full_name": "nicho1ab/RecordsTracker"}')
        if command[2] == "repos/nicho1ab/RecordsTracker/pulls/613":
            return CompletedProcess(
                command,
                0,
                stdout=(
                    '{"state":"open","body":"body","base":{"ref":"main","sha":"base"},'
                    '"head":{"ref":"repair","sha":"head"}}'
                ),
            )
        return CompletedProcess(command, 0, stdout="first.py\nsecond.py\n")

    pull_request = prepare.fetch_open_pull_request(
        prepare.GitHubTransport(runner), "nicho1ab/RecordsTracker", "#613"
    )

    assert pull_request.repository == "nicho1ab/RecordsTracker"
    assert pull_request.base == "main"
    assert pull_request.head_sha == "head"
    assert pull_request.changed_files == ("first.py", "second.py")
    assert "--paginate" in commands[-1]


def test_valid_live_body_validates_without_mutation() -> None:
    prepare = _load_module()
    transport = FakeTransport([_completed_body()])
    pull_request = _fetch(prepare, transport, _completed_body())

    assert prepare.validate_open_pull_request(ROOT, pull_request) == []
    assert transport.update_calls == []


def test_invalid_live_body_reports_actionable_production_violations_without_mutation() -> None:
    prepare = _load_module()
    transport = FakeTransport(["# Pull Request Evidence\n"])
    pull_request = _fetch(prepare, transport, "")

    violations = prepare.validate_open_pull_request(ROOT, pull_request)

    assert "missing governing issue reference" in violations
    assert transport.update_calls == []


def test_empty_live_body_is_valid_api_data_that_can_be_repaired() -> None:
    prepare = _load_module()

    class EmptyBodyTransport(FakeTransport):
        def pull_request(self, _repository: str, _number: int) -> dict[str, object]:
            return {
                "state": "open",
                "body": None,
                "base": {"ref": "main", "sha": "base-sha"},
                "head": {"ref": "repair", "sha": "head-sha"},
            }

    pull_request = prepare.fetch_open_pull_request(
        EmptyBodyTransport([""]), "nicho1ab/RecordsTracker", "613"
    )

    assert pull_request.body == ""
    violations = prepare.validate_open_pull_request(ROOT, pull_request)
    assert "missing governing issue reference" in violations


def test_preview_validates_proposal_against_live_scope_without_mutation() -> None:
    prepare = _load_module()
    invalid_live = "# Pull Request Evidence\n"
    proposal = _completed_body()
    transport = FakeTransport([invalid_live])
    pull_request = _fetch(prepare, transport, invalid_live)

    live, proposed, differs = prepare.preview_open_pull_request_repair(
        repo_root=ROOT, pull_request=pull_request, proposal=proposal
    )

    assert "missing governing issue reference" in live
    assert proposed == []
    assert differs is True
    assert transport.update_calls == []


def test_invalid_proposal_cannot_update_open_pr() -> None:
    prepare = _load_module()
    transport = FakeTransport([_completed_body()])

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="613",
        proposal="# Pull Request Evidence\n",
        preconditions=_preconditions(prepare, _completed_body(), "# Pull Request Evidence\n"),
        confirmed=True,
    )

    assert attempt.outcome is prepare.PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED
    assert transport.update_calls == []


def test_apply_requires_explicit_confirmation_before_mutation() -> None:
    prepare = _load_module()
    current = _completed_body()
    proposal = current.replace("Preflight catches", "Open PR repair catches")
    transport = FakeTransport([current])

    with pytest.raises(prepare.ProposalValidationError, match="--confirm-update"):
        prepare.apply_open_pull_request_repair(
            transport=transport,
            repo_root=ROOT,
            repository="nicho1ab/RecordsTracker",
            reference="613",
            proposal=proposal,
            preconditions=_preconditions(prepare, current, proposal),
            confirmed=False,
        )

    assert transport.update_calls == []


def test_apply_updates_only_body_then_refetches_and_revalidates() -> None:
    prepare = _load_module()
    current = _completed_body()
    proposal = current.replace("Preflight catches", "Open PR repair catches")
    transport = FakeTransport([current, current, proposal])

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="613",
        proposal=proposal,
        preconditions=_preconditions(prepare, current, proposal),
        confirmed=True,
    )

    assert attempt.outcome is prepare.PersistenceOutcome.IMMEDIATE_CONVERGENCE
    assert attempt.mutation_count == 1
    assert transport.update_calls == [("nicho1ab/RecordsTracker", 613, proposal)]


def test_apply_is_idempotent_when_transport_normalized_bodies_match() -> None:
    prepare = _load_module()
    current = _completed_body()
    transport = FakeTransport([current.replace("\n", "\r\n")])

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="613",
        proposal=current,
        preconditions=_preconditions(prepare, current, current),
        confirmed=False,
    )
    assert attempt.outcome is prepare.PersistenceOutcome.NO_MUTATION_ALREADY_CONVERGED
    assert transport.update_calls == []


def test_apply_rejects_a_concurrent_live_body_change() -> None:
    prepare = _load_module()
    current = _completed_body()
    proposal = current.replace("Preflight catches", "Open PR repair catches")
    changed_elsewhere = current.replace("Preflight catches", "Another editor catches")
    transport = FakeTransport([current, changed_elsewhere])

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="613",
        proposal=proposal,
        preconditions=_preconditions(prepare, current, proposal),
        confirmed=True,
    )

    assert attempt.outcome is prepare.PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED
    assert transport.update_calls == []


def test_apply_rejects_an_incorrect_expected_body_hash() -> None:
    prepare = _load_module()
    current = _completed_body()
    proposal = current.replace("Preflight catches", "Open PR repair catches")
    transport = FakeTransport([current, current])

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="613",
        proposal=proposal,
        preconditions=_preconditions(prepare, current, proposal, body_hash="0" * 64),
        confirmed=True,
    )

    assert transport.update_calls == []
    assert attempt.outcome is prepare.PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED
    assert transport.update_calls == []


def test_apply_reports_persistence_mismatch_after_refetch() -> None:
    prepare = _load_module()
    current = _completed_body()
    proposal = current.replace("Preflight catches", "Open PR repair catches")
    persisted_different = current.replace("Preflight catches", "Different valid body catches")
    transport = FakeTransport([current, current, persisted_different])

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="613",
        proposal=proposal,
        preconditions=_preconditions(prepare, current, proposal),
        confirmed=True,
        sleeper=lambda _seconds: None,
    )
    assert attempt.outcome is prepare.PersistenceOutcome.STABLE_PERSISTENCE_MISMATCH


def test_apply_reports_invalid_persisted_body_after_update() -> None:
    prepare = _load_module()
    current = _completed_body()
    proposal = current.replace("Preflight catches", "Open PR repair catches")
    transport = FakeTransport([current, current, "# Pull Request Evidence\n"])

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="613",
        proposal=proposal,
        preconditions=_preconditions(prepare, current, proposal),
        confirmed=True,
        sleeper=lambda _seconds: None,
    )

    assert transport.update_calls == [("nicho1ab/RecordsTracker", 613, proposal)]
    assert attempt.outcome is prepare.PersistenceOutcome.STABLE_PERSISTENCE_MISMATCH


def test_github_read_and_update_failures_are_classified() -> None:
    prepare = _load_module()

    def read_failure(command, **_kwargs):
        raise CalledProcessError(1, command)

    with pytest.raises(prepare.GitHubApiError, match="GitHub/API request failed"):
        prepare.GitHubTransport(read_failure).repository("nicho1ab/RecordsTracker")

    def update_failure(command, **_kwargs):
        if "--method" in command:
            raise CalledProcessError(1, command)
        return CompletedProcess(command, 0, stdout="")

    with pytest.raises(prepare.GitHubApiError, match="GitHub/API request failed"):
        prepare.GitHubTransport(update_failure).update_body("nicho1ab/RecordsTracker", 613, "body")


def test_missing_closed_and_wrong_repository_references_fail_safely() -> None:
    prepare = _load_module()

    with pytest.raises(prepare.PullRequestReferenceError):
        prepare.resolve_pull_request_number("not-a-pr", "nicho1ab/RecordsTracker")
    with pytest.raises(prepare.RepositoryContextError):
        prepare.resolve_pull_request_number("other/repository#613", "nicho1ab/RecordsTracker")

    class ClosedTransport(FakeTransport):
        def pull_request(self, _repository: str, _number: int) -> dict[str, object]:
            return {"state": "closed", "body": ""}

    with pytest.raises(prepare.PullRequestStateError, match="not open"):
        prepare.fetch_open_pull_request(ClosedTransport([""]), "nicho1ab/RecordsTracker", "613")

    class WrongRepositoryTransport(FakeTransport):
        def repository(self, _repository: str) -> str:
            return "other/repository"

    with pytest.raises(prepare.RepositoryContextError):
        prepare.fetch_open_pull_request(
            WrongRepositoryTransport([""]), "nicho1ab/RecordsTracker", "613"
        )


def test_body_transport_preserves_multiline_unicode_quotes_and_markdown() -> None:
    prepare = _load_module()
    body = _completed_body().replace(
        "Developer workflow guidance updated.",
        'Developer workflow guidance updated: "quoted", `code`, café, and a table.\n\n'
        "| A | B |\n| --- | --- |\n| ✓ | value |",
    )
    transport = FakeTransport([body.replace("\n", "\r\n"), body.replace("\n", "\r\n"), body])

    attempt = prepare.apply_open_pull_request_repair(
        transport=transport,
        repo_root=ROOT,
        repository="nicho1ab/RecordsTracker",
        reference="https://github.com/nicho1ab/RecordsTracker/pull/613",
        proposal=body,
        preconditions=_preconditions(prepare, body.replace("\n", "\r\n"), body),
        confirmed=True,
    )
    assert attempt.outcome is prepare.PersistenceOutcome.NO_MUTATION_ALREADY_CONVERGED
    assert transport.update_calls == []


def test_transport_update_payload_contains_only_the_pr_body() -> None:
    prepare = _load_module()
    payloads: list[dict[str, object]] = []

    def runner(command, **_kwargs):
        payloads.append(json.loads(Path(command[-1]).read_text(encoding="utf-8")))
        return CompletedProcess(command, 0, stdout="{}")

    body = 'only body\nwith "quotes", `Markdown`, and café'
    prepare.GitHubTransport(runner).update_body("nicho1ab/RecordsTracker", 613, body)

    assert payloads == [{"body": body}]


def test_pr_preparation_guidance_documents_supported_open_pr_repair() -> None:
    guidance_paths = (
        ROOT / "AGENTS.md",
        ROOT / ".github" / "copilot-instructions.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "docs" / "developer" / "codex-workflow.md",
    )
    guidance = "\n".join(path.read_text(encoding="utf-8") for path in guidance_paths)

    assert "creating or repairing a PR body" in guidance
    assert "open-PR repair remains deferred" not in guidance
    assert "freeform PR body cannot substitute" in guidance
    assert "race between that final refetch and the update request" in guidance
