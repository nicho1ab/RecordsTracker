# ruff: noqa: E501

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "delivery_state", ROOT / "scripts" / "delivery_state.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DELIVERY = _load_module()


def _pr(
    number: int,
    state: str,
    head: str,
    *,
    head_branch: str = "topic",
    base_branch: str = "main",
    base_sha: str = "a" * 40,
) -> dict[str, object]:
    return {
        "number": number,
        "state": state,
        "head": {"sha": head, "ref": head_branch},
        "base": {"ref": base_branch, "sha": base_sha},
        "commits": 1,
        "changed_files": 6,
        "mergeable_state": "clean",
    }


def _worktree(branch: str = "topic") -> dict[str, object]:
    return {
        "path": "C:/OneDrive/Repo",
        "branch": branch,
        "head_sha": "a" * 40,
        "clean": True,
        "classification": "retained",
    }


def _snapshot() -> dict[str, object]:
    return {
        "schema_version": DELIVERY.SCHEMA_VERSION,
        "generated_at": "2026-07-25T00:00:00Z",
        "repository": {
            "owner": "nicho1ab",
            "name": "RecordsTracker",
            "canonical_identity": "nicho1ab/RecordsTracker",
            "remote_url_classification": "github_https",
        },
        "issue": {
            "number": 608,
            "state": "open",
            "title": "Delivery state",
            "observed_at": "2026-07-25T00:00:00Z",
        },
        "git": {
            "authoritative_main_branch": "main",
            "expected_main_sha": "a" * 40,
            "local_main_sha": "a" * 40,
            "remote_tracking_main_sha": "a" * 40,
            "live_remote_main_sha": "a" * 40,
            "current_branch": "topic",
            "current_head_sha": "b" * 40,
            "base_sha": "a" * 40,
            "dirty": False,
            "staged": False,
            "unstaged": False,
            "untracked": False,
        },
        "branch_ownership": {
            "local_branch": "topic",
            "live_remote_branch_exists": False,
            "live_remote_branch_sha": None,
            "stale_local_remote_tracking_ref_exists": False,
            "stale_local_remote_tracking_ref_sha": None,
            "open_prs_for_branch": [],
            "historical_closed_or_merged_prs_for_branch": [],
            "prs_for_exact_current_head": [],
            "classification": "UNOWNED_CURRENT_HEAD",
        },
        "pull_request": None,
        "changed_files": {
            "branch_diff": [],
            "staged": [],
            "unstaged": [],
            "untracked": [],
            "ignored_risk_paths": [],
        },
        "checks": {
            "required_names": list(DELIVERY.REQUIRED_CHECKS),
            "applicable_head_sha": None,
            "records": [],
            "status": "not_applicable_no_current_pr",
        },
        "worktrees": [_worktree()],
        "stash_protections": {
            "expected_identifiers": ["c" * 40],
            "observed_presence": True,
            "observed_identifiers": ["c" * 40],
            "contents_inspected": False,
        },
        "classifications": {"findings": []},
        "freshness": {
            "collection_started_at": "2026-07-25T00:00:00Z",
            "collection_finished_at": "2026-07-25T00:00:00Z",
            "expected_vs_observed": {
                "repository": "nicho1ab/RecordsTracker",
                "main_sha_matches": True,
                "branch_matches": True,
                "head_sha_matches": True,
            },
            "stale": False,
            "globally_atomic": False,
        },
        "next_legal_states": ["READ_ONLY_INSPECTION"],
        "prohibited_actions": ["commit"],
        "sources": ["local_git", "github_api"],
    }


@pytest.mark.parametrize(
    ("name", "kwargs", "classification", "codes", "may_continue"),
    [
        ("clean no PR", {}, "UNOWNED_CURRENT_HEAD", set(), True),
        (
            "exact open",
            {"branch_prs": [_pr(1, "open", "a" * 40)]},
            "EXISTING_EXACT_HEAD_PUBLICATION",
            {"EXISTING_EXACT_HEAD_PUBLICATION"},
            True,
        ),
        (
            "open unexpected head",
            {"branch_prs": [_pr(1, "open", "b" * 40)]},
            "ACTIVE_OWNERSHIP_CONFLICT",
            {"OPEN_BRANCH_OWNERSHIP_CONFLICT"},
            False,
        ),
        (
            "historical merged reuse",
            {"branch_prs": [_pr(2, "closed", "b" * 40)]},
            "HISTORICAL_BRANCH_REUSE",
            {"HISTORICAL_BRANCH_REUSE"},
            True,
        ),
        (
            "historical closed reuse",
            {"branch_prs": [_pr(3, "closed", "c" * 40)]},
            "HISTORICAL_BRANCH_REUSE",
            {"HISTORICAL_BRANCH_REUSE"},
            True,
        ),
        (
            "exact historical",
            {"branch_prs": [_pr(4, "closed", "a" * 40)]},
            "ACTIVE_OWNERSHIP_CONFLICT",
            {"EXACT_HEAD_HISTORICAL_PUBLICATION"},
            False,
        ),
        (
            "stale tracking",
            {"tracking_sha": "d" * 40},
            "STALE_REMOTE_TRACKING_REF",
            {"STALE_REMOTE_TRACKING_REF"},
            True,
        ),
        ("live expected", {"live_remote_sha": "a" * 40}, "UNOWNED_CURRENT_HEAD", set(), True),
        (
            "live unexpected",
            {"live_remote_sha": "e" * 40},
            "ACTIVE_OWNERSHIP_CONFLICT",
            {"UNEXPECTED_LIVE_REMOTE_SHA"},
            False,
        ),
        (
            "duplicate worktree",
            {"worktrees": [_worktree(), {**_worktree(), "path": "C:/Other"}]},
            "ACTIVE_OWNERSHIP_CONFLICT",
            {"AMBIGUOUS_WORKTREE_OWNERSHIP"},
            False,
        ),
        (
            "expected branch mismatch",
            {"expected_branch": "other"},
            "ACTIVE_OWNERSHIP_CONFLICT",
            {"EXPECTED_BRANCH_MISMATCH"},
            False,
        ),
        (
            "expected head mismatch",
            {"expected_head_sha": "f" * 40},
            "ACTIVE_OWNERSHIP_CONFLICT",
            {"EXPECTED_HEAD_MISMATCH"},
            False,
        ),
    ],
)
def test_branch_ownership_classifies_historical_and_blocking_states(
    name, kwargs, classification, codes, may_continue
) -> None:
    arguments = {
        "branch": "topic",
        "head_sha": "a" * 40,
        "live_remote_sha": None,
        "tracking_sha": None,
        "branch_prs": [],
        "worktrees": [_worktree()],
        "expected_branch": None,
        "expected_head_sha": None,
        "expected_pr": None,
    }
    arguments.update(kwargs)
    result, findings = DELIVERY.classify_branch_ownership(
        **arguments,
    )
    assert result == classification, name
    assert {item.code for item in findings} == codes
    assert all(item.may_continue is may_continue for item in findings)


def test_schema_accepts_complete_snapshot_and_rejects_incompatible_version() -> None:
    snapshot = _snapshot()
    DELIVERY.validate_snapshot(snapshot)
    snapshot["schema_version"] = "recordstracker.delivery-state.v2"
    with pytest.raises(DELIVERY.SchemaValidationError):
        DELIVERY.validate_snapshot(snapshot)


def test_schema_requires_immutable_head_and_no_stash_contents() -> None:
    snapshot = _snapshot()
    del snapshot["git"]["current_head_sha"]
    with pytest.raises(DELIVERY.SchemaValidationError):
        DELIVERY.validate_snapshot(snapshot)


def test_sanitized_fixture_validates_against_the_committed_schema() -> None:
    fixture = ROOT / "tests" / "fixtures" / "delivery_state" / "no-pr-stale-tracking-v1.json"
    DELIVERY.validate_snapshot(json.loads(fixture.read_text(encoding="utf-8")))
    snapshot = _snapshot()
    snapshot["stash_protections"]["contents_inspected"] = True
    with pytest.raises(DELIVERY.SchemaValidationError):
        DELIVERY.validate_snapshot(snapshot)


def test_serialization_is_deterministic() -> None:
    first = json.dumps(_snapshot(), indent=2, sort_keys=True)
    second = json.dumps(_snapshot(), indent=2, sort_keys=True)
    assert first == second


def test_paginated_github_transport_flattens_pages_and_rejects_malformed_data() -> None:
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, '[[{"number": 1}], [{"number": 2}]]', "")

    assert [item["number"] for item in DELIVERY.GitHubTransport(runner).paginated("endpoint")] == [
        1,
        2,
    ]

    def malformed(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, '[{"number": 1}]', "")

    with pytest.raises(DELIVERY.GitHubApiError):
        DELIVERY.GitHubTransport(malformed).paginated("endpoint")


def test_git_transport_keeps_windows_paths_as_one_subprocess_argument() -> None:
    commands: list[tuple[str, ...]] = []

    def runner(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "value\n", "")

    path = Path("C:/OneDrive Folder/RecordsTracker")
    assert DELIVERY.GitTransport(path, runner).read("rev-parse", "HEAD") == "value\n"
    assert commands[0][4] == str(path)


def test_write_output_requires_explicit_replacement(tmp_path: Path) -> None:
    path = tmp_path / "data" / "snapshot.json"
    DELIVERY.write_output(path, "first\n", replace=False)
    with pytest.raises(DELIVERY.DeliveryStateError):
        DELIVERY.write_output(path, "second\n", replace=False)
    DELIVERY.write_output(path, "second\n", replace=True)
    assert path.read_text(encoding="utf-8") == "second\n"


def test_main_returns_success_for_informational_findings(monkeypatch, capsys) -> None:
    snapshot = _snapshot()
    snapshot["classifications"]["findings"] = [
        DELIVERY.finding(
            "HISTORY", "INFORMATIONAL_DISCREPANCY", "history", "test", None, True, "continue"
        ).as_dict()
    ]
    monkeypatch.setattr(DELIVERY, "collect_snapshot", lambda **kwargs: snapshot)
    assert DELIVERY.main(["snapshot", "--protected-stash", "c" * 40]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == DELIVERY.SCHEMA_VERSION


def test_main_returns_nonzero_for_actual_blocker(monkeypatch) -> None:
    snapshot = _snapshot()
    snapshot["classifications"]["findings"] = [
        DELIVERY.finding(
            "BLOCK", "AUTHORIZATION_BLOCKER", "blocked", "test", "sha", False, "review"
        ).as_dict()
    ]
    monkeypatch.setattr(DELIVERY, "collect_snapshot", lambda **kwargs: snapshot)
    assert DELIVERY.main(["snapshot", "--protected-stash", "c" * 40]) == 1


def test_documentation_describes_snapshot_contract() -> None:
    content = (ROOT / "docs" / "developer" / "codex-workflow.md").read_text(encoding="utf-8")
    for phrase in (
        "Read-only delivery-state snapshots",
        "Historical merged or closed PRs",
        "live GitHub ref is authoritative",
        "open PR is an idempotent reuse state",
        "does not fetch, change refs",
    ):
        assert phrase in content


def test_contract_excludes_credentials_bodies_environment_and_stash_content() -> None:
    source = (ROOT / "scripts" / "delivery_state.py").read_text(encoding="utf-8")
    assert "full PR bodies" not in source
    assert "os.environ" not in source
    assert '"stash", "show"' not in source


class _CollectorGit:
    def __init__(self, *, status: str = "", ignored: str = "", main: str = "a" * 40, final_head: str | None = None, stash: str = "c" * 40) -> None:
        self.repo_root = Path("C:/OneDrive Folder/RecordsTracker")
        self.status, self.ignored, self.main = status, ignored, main
        self.final_head, self.stash = final_head, stash
        self.head_reads = 0

    def read(self, *args, **kwargs):
        if args == ("config", "--get", "remote.origin.url"):
            return "https://github.com/nicho1ab/RecordsTracker.git\n"
        if args == ("branch", "--show-current"):
            return "topic\n"
        if args == ("rev-parse", "HEAD"):
            self.head_reads += 1
            return (self.final_head if self.head_reads > 1 and self.final_head else "b" * 40) + "\n"
        if args == ("rev-parse", "main") or args == ("rev-parse", "origin/main"):
            return self.main + "\n"
        if args == ("merge-base", "main", "HEAD"):
            return self.main + "\n"
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return self.status
        if args == ("status", "--ignored", "--porcelain=v1", "--untracked-files=all"):
            return self.ignored
        if args == ("worktree", "list", "--porcelain"):
            return ""
        if args == ("stash", "list", "--format=%H %gd"):
            return (self.stash + " stash@{0}\n") if self.stash else ""
        if args == ("diff", "--name-only", "--merge-base", self.main, "HEAD"):
            return "branch.py\n"
        if args == ("diff", "--cached", "--name-only"):
            return "staged.py\n" if "A  staged.py" in self.status else ""
        if args == ("diff", "--name-only"):
            return "unstaged.py\n" if " unstaged.py" in self.status else ""
        raise AssertionError(args)

    def optional_ref(self, ref):
        return "d" * 40 if ref.endswith("topic") else None


class _CollectorHub:
    def __init__(self, *, live_main: str = "a" * 40, prs=None, checks=None, fail=False) -> None:
        self.live_main, self.prs, self.checks, self.fail = live_main, prs or [], checks or [] , fail
        self.main_reads = 0

    def api(self, endpoint, allow_not_found=False):
        if self.fail:
            raise DELIVERY.GitHubApiError("GitHub/API request failed")
        if endpoint == "repos/nicho1ab/RecordsTracker":
            return {"full_name": "nicho1ab/RecordsTracker", "default_branch": "main"}
        if endpoint.endswith("git/ref/heads/main"):
            self.main_reads += 1
            return {"object": {"sha": self.live_main}}
        if endpoint.endswith("/branches/topic"):
            return None
        if endpoint.endswith("/issues/608"):
            return {"state": "open", "title": "Delivery"}
        if "/pulls/" in endpoint:
            number = int(endpoint.rsplit("/", maxsplit=1)[1])
            return next((item for item in self.prs if item.get("number") == number), None)
        if "/check-runs" in endpoint:
            return {"check_runs": self.checks}
        raise AssertionError(endpoint)

    def paginated(self, endpoint):
        return self.prs


def _collect(monkeypatch, *, git=None, hub=None, expected_pr=None, **kwargs):
    git = git or _CollectorGit()
    monkeypatch.setattr(DELIVERY, "parse_worktrees", lambda output, transport: [{"path": str(git.repo_root), "branch": "topic", "head_sha": "b" * 40, "clean": True, "classification": "current"}])
    return DELIVERY.collect_snapshot(repo_root=git.repo_root, issue_number=608, expected_main_sha="a" * 40, expected_branch="topic", expected_head_sha="b" * 40, expected_pr=expected_pr, protected_stash_ids=["c" * 40], expected_repository="nicho1ab/RecordsTracker", clock=lambda: DELIVERY.datetime(2026, 7, 25, tzinfo=DELIVERY.UTC), git=git, github=hub or _CollectorHub(), **kwargs)


def test_collector_reports_separate_staged_unstaged_untracked_and_ignored_scope(monkeypatch) -> None:
    snapshot = _collect(monkeypatch, git=_CollectorGit(status="A  staged.py\n unstaged.py\n?? untracked.py\n", ignored="!! ordinary.tmp\n!! data/processed/evidence.json\n"))
    assert snapshot["changed_files"] == {"branch_diff": ["branch.py"], "staged": ["staged.py"], "unstaged": ["unstaged.py"], "untracked": ["untracked.py"], "ignored_risk_paths": ["data/processed/evidence.json"]}


def test_collector_blocks_missing_protected_stash_and_main_disagreement(monkeypatch) -> None:
    snapshot = _collect(monkeypatch, git=_CollectorGit(main="a" * 40, stash=""), hub=_CollectorHub(live_main="e" * 40))
    findings = {item["code"]: item for item in snapshot["classifications"]["findings"]}
    assert findings["PROTECTED_STASH_ABSENT"]["classification"] == "DESTRUCTIVE_ACTION_BLOCKER"
    assert findings["MAIN_STATE_DISAGREEMENT"]["classification"] == "AUTHORIZATION_BLOCKER"
    assert findings["MAIN_STATE_DISAGREEMENT"]["evidence"]["live_main_sha"] == "e" * 40


def test_collector_fails_closed_for_github_and_local_git_failures(monkeypatch) -> None:
    with pytest.raises(DELIVERY.GitHubApiError):
        _collect(monkeypatch, hub=_CollectorHub(fail=True))
    with pytest.raises(DELIVERY.LocalGitError):
        DELIVERY.GitTransport(Path("C:/repo"), lambda *args, **kwargs: (_ for _ in ()).throw(OSError())).read("status")


def test_collector_classifies_source_change_and_does_not_claim_atomicity(monkeypatch) -> None:
    snapshot = _collect(monkeypatch, git=_CollectorGit(final_head="f" * 40))
    assert any(item["code"] == "SOURCE_STATE_CHANGED_DURING_COLLECTION" for item in snapshot["classifications"]["findings"])
    assert snapshot["freshness"]["globally_atomic"] is False


def test_check_records_are_sha_linked_and_wrong_head_cannot_be_current_evidence() -> None:
    records = DELIVERY.parse_checks("b" * 40, [{"name": "validate", "status": "completed", "conclusion": "success", "details_url": "https://github.com/a/b/actions/runs/1/job/2"}], "2026-07-25T00:00:00Z")
    assert records[0]["head_sha"] == "b" * 40
    assert records[0]["expected_head_sha"] == "b" * 40
    assert records[0]["run_id"] == "1" and records[0]["job_id"] == "2"
    assert records[1]["status"] == "missing"


def _collector_exit_status(monkeypatch, snapshot: dict[str, object]) -> int:
    monkeypatch.setattr(DELIVERY, "collect_snapshot", lambda **kwargs: snapshot)
    return DELIVERY.main(["snapshot", "--protected-stash", "c" * 40])


@pytest.mark.parametrize(
    ("base_branch", "base_sha", "code", "evidence_field", "observed"),
    [
        ("release", "a" * 40, "PR_BASE_BRANCH_MISMATCH", "observed_base_branch", "release"),
        ("main", "e" * 40, "PR_BASE_MISMATCH", "pr_base_sha", "e" * 40),
    ],
)
def test_collector_blocks_expected_pr_base_mismatches(
    monkeypatch, base_branch, base_sha, code, evidence_field, observed
) -> None:
    expected = _pr(41, "open", "b" * 40, base_branch=base_branch, base_sha=base_sha)
    historical = _pr(99, "closed", "d" * 40)
    snapshot = _collect(monkeypatch, expected_pr=41, hub=_CollectorHub(prs=[historical, expected]))
    findings = {item["code"]: item for item in snapshot["classifications"]["findings"]}
    assert snapshot["pull_request"]["number"] == 41
    assert snapshot["pull_request"]["head_sha"] == "b" * 40
    assert findings[code]["classification"] == "AUTHORIZATION_BLOCKER"
    assert findings[code]["may_continue"] is False
    assert findings[code]["evidence"][evidence_field] == observed
    assert _collector_exit_status(monkeypatch, snapshot) == 1


@pytest.mark.parametrize(
    ("head_branch", "head_sha", "code", "evidence_field", "observed"),
    [
        ("other-topic", "b" * 40, "PR_HEAD_BRANCH_MISMATCH", "observed_head_branch", "other-topic"),
        ("topic", "e" * 40, "PR_HEAD_MISMATCH", "observed_head_sha", "e" * 40),
    ],
)
def test_collector_blocks_expected_pr_head_mismatches(
    monkeypatch, head_branch, head_sha, code, evidence_field, observed
) -> None:
    expected = _pr(42, "open", head_sha, head_branch=head_branch)
    historical = _pr(98, "closed", "d" * 40)
    snapshot = _collect(monkeypatch, expected_pr=42, hub=_CollectorHub(prs=[historical, expected]))
    findings = {item["code"]: item for item in snapshot["classifications"]["findings"]}
    assert snapshot["pull_request"]["number"] == 42
    assert snapshot["pull_request"]["head_sha"] == head_sha
    assert findings[code]["classification"] == "AUTHORIZATION_BLOCKER"
    assert findings[code]["may_continue"] is False
    assert findings[code]["evidence"][evidence_field] == observed
    assert _collector_exit_status(monkeypatch, snapshot) == 1


def test_collector_blocks_stale_successful_checks_from_another_head(monkeypatch) -> None:
    stale_head = "e" * 40
    checks = [
        {"name": name, "head_sha": stale_head, "status": "completed", "conclusion": "success", "details_url": f"https://github.com/a/b/actions/runs/{index}/job/{index + 10}"}
        for index, name in enumerate(DELIVERY.REQUIRED_CHECKS, start=1)
    ]
    checks.append({"name": "validate", "head_sha": "b" * 40, "status": "completed", "conclusion": "success", "details_url": "https://github.com/a/b/actions/runs/50/job/60"})
    snapshot = _collect(monkeypatch, expected_pr=43, hub=_CollectorHub(prs=[_pr(43, "open", "b" * 40)], checks=checks))
    findings = {item["code"]: item for item in snapshot["classifications"]["findings"]}
    records = snapshot["checks"]["records"]
    stale = [record for record in records if record["status"] == "stale"]
    missing = [record for record in records if record["status"] == "missing"]
    assert {record["name"] for record in stale} == set(DELIVERY.REQUIRED_CHECKS)
    assert all(record["head_sha"] == stale_head and record["expected_head_sha"] == "b" * 40 for record in stale)
    assert all(record["run_id"] and record["job_id"] and record["conclusion"] == "success" for record in stale)
    assert {record["name"] for record in missing} == {"docs-check", "fixtures", "security"}
    assert any(record["name"] == "validate" and record["head_sha"] == "b" * 40 and record["status"] == "completed" for record in records)
    assert snapshot["checks"]["status"] == "blocking_stale_evidence"
    assert findings["STALE_REQUIRED_CHECK_EVIDENCE"]["classification"] == "AUTHORIZATION_BLOCKER"
    assert findings["STALE_REQUIRED_CHECK_EVIDENCE"]["may_continue"] is False
    assert _collector_exit_status(monkeypatch, snapshot) == 1
