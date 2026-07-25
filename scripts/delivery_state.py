"""Create a read-only, versioned RecordsTracker delivery-state snapshot.

The command reports current Git and GitHub state; it never fetches, changes
refs, stages files, edits GitHub objects, or inspects protected stash content.
"""
# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "delivery-state-snapshot-v1.schema.json"
SCHEMA_VERSION = "recordstracker.delivery-state.v1"
REQUIRED_CHECKS = ("validate", "docs-check", "fixtures", "security")
CLASSIFICATIONS = (
    "INFORMATIONAL_DISCREPANCY",
    "RECOVERABLE_AUTOMATION_FAILURE",
    "AUTHORIZATION_BLOCKER",
    "DEPENDENCY_BLOCKER",
    "MATERIAL_IMPLEMENTATION_BLOCKER",
    "DESTRUCTIVE_ACTION_BLOCKER",
    "GOVERNED_BOUNDARY_REVIEW_REQUIRED",
)
Runner = Callable[..., subprocess.CompletedProcess[str]]
Clock = Callable[[], datetime]


class DeliveryStateError(RuntimeError):
    """Base class for a classified read-only snapshot failure."""


class LocalGitError(DeliveryStateError):
    """A required local Git read did not return usable data."""


class GitHubApiError(DeliveryStateError):
    """A required GitHub read did not return usable data."""


class RepositoryContextError(DeliveryStateError):
    """The requested repository does not match the local origin."""


class SchemaValidationError(DeliveryStateError):
    """The generated snapshot does not satisfy the committed schema."""


@dataclass(frozen=True)
class Finding:
    code: str
    classification: str
    message: str
    source: str
    affected_identifier: str | None
    may_continue: bool
    recovery_or_required_authority: str
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "classification": self.classification,
            "message": self.message,
            "source": self.source,
            "affected_identifier": self.affected_identifier,
            "may_continue": self.may_continue,
            "recovery_or_required_authority": self.recovery_or_required_authority,
            "evidence": self.evidence,
        }


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso_time(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--at must use YYYY-MM-DDTHH:MM:SSZ") from error


def finding(
    code: str,
    classification: str,
    message: str,
    source: str,
    affected_identifier: str | None,
    may_continue: bool,
    recovery: str,
    **evidence: Any,
) -> Finding:
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"unsupported classification: {classification}")
    return Finding(
        code=code,
        classification=classification,
        message=message,
        source=source,
        affected_identifier=affected_identifier,
        may_continue=may_continue,
        recovery_or_required_authority=recovery,
        evidence=evidence,
    )


class GitTransport:
    """Read-only local Git transport with no implicit fetch or cleanup."""

    def __init__(self, repo_root: Path, runner: Runner | None = None) -> None:
        self.repo_root = repo_root
        self._runner = runner or subprocess.run

    def read(self, *arguments: str, allow_failure: bool = False) -> str:
        try:
            result = self._runner(
                (
                    "git",
                    "-c",
                    f"safe.directory={self.repo_root}",
                    "-C",
                    str(self.repo_root),
                    *arguments,
                ),
                check=not allow_failure,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise LocalGitError("local Git read failed") from error
        if result.returncode and not allow_failure:
            raise LocalGitError("local Git read failed")
        return result.stdout

    def optional_ref(self, ref: str) -> str | None:
        value = self.read("rev-parse", "--verify", "--quiet", ref, allow_failure=True).strip()
        return value or None


class GitHubTransport:
    """Read-only GitHub CLI transport; bodies and credentials are never emitted."""

    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or subprocess.run

    def api(self, *arguments: str, allow_not_found: bool = False) -> Any | None:
        try:
            result = self._runner(
                ("gh", "api", *arguments), check=False, capture_output=True, text=True
            )
        except OSError as error:
            raise GitHubApiError("GitHub/API request failed") from error
        if result.returncode:
            if allow_not_found and "404" in result.stderr:
                return None
            raise GitHubApiError("GitHub/API request failed")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise GitHubApiError("malformed GitHub/API response") from error

    def paginated(self, endpoint: str) -> list[dict[str, Any]]:
        value = self.api("--paginate", "--slurp", endpoint)
        if not isinstance(value, list) or not all(isinstance(page, list) for page in value):
            raise GitHubApiError("malformed paginated GitHub/API response")
        flattened = [item for page in value for item in page]
        if not all(isinstance(item, dict) for item in flattened):
            raise GitHubApiError("malformed paginated GitHub/API response")
        return flattened


def repository_from_origin(git: GitTransport) -> tuple[str, str, str]:
    remote_url = git.read("config", "--get", "remote.origin.url").strip()
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([^/\s]+)/([^/\s]+?)(?:\.git)?",
        remote_url,
    )
    if match is None:
        raise RepositoryContextError("current origin is not a github.com owner/repository remote")
    owner, name = match.groups()
    return owner, name, remote_url


def status_summary(git: GitTransport) -> tuple[bool, bool, bool, list[str], list[str]]:
    staged = False
    unstaged = False
    untracked = False
    paths: list[str] = []
    untracked_paths: list[str] = []
    for line in git.read("status", "--porcelain=v1", "--untracked-files=all").splitlines():
        if len(line) < 4:
            continue
        index, worktree, path = line[0], line[1], line[3:]
        paths.append(path)
        staged = staged or index not in {" ", "?"}
        unstaged = unstaged or worktree not in {" ", "?"}
        untracked = untracked or index == "?"
        if index == "?":
            untracked_paths.append(path)
    return staged, unstaged, untracked, sorted(paths), sorted(untracked_paths)


def ignored_risk_paths(git: GitTransport) -> list[str]:
    output = git.read("status", "--ignored", "--porcelain=v1", "--untracked-files=all")
    results = []
    for line in output.splitlines():
        if not line.startswith("!! "):
            continue
        path = line[3:].replace("\\", "/")
        if path.startswith("data/processed/"):
            results.append(path)
    return sorted(set(results))


def parse_worktrees(output: str, git: GitTransport) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, str] = {}
    for line in [*output.splitlines(), ""]:
        if line:
            key, _, value = line.partition(" ")
            current[key] = value
            continue
        if not current:
            continue
        path = Path(current["worktree"])
        entry_git = GitTransport(path, git._runner)
        staged, unstaged, untracked, _, _ = status_summary(entry_git)
        branch_ref = current.get("branch")
        records.append(
            {
                "path": str(path),
                "branch": branch_ref.removeprefix("refs/heads/") if branch_ref else None,
                "head_sha": current.get("HEAD"),
                "clean": not any((staged, unstaged, untracked)),
                "classification": "current" if path == git.repo_root else "registered",
            }
        )
        current = {}
    return sorted(records, key=lambda item: item["path"])


def parse_checks(
    expected_head_sha: str, values: Sequence[dict[str, Any]], observed_at: str
) -> list[dict[str, Any]]:
    results = []
    for name in REQUIRED_CHECKS:
        matching = [value for value in values if str(value.get("name")) == name]
        current = False
        for value in matching:
            observed_head_sha = str(value.get("head_sha") or expected_head_sha)
            details_url = str(value.get("details_url") or "")
            match = re.search(r"/actions/runs/(\d+)(?:/job/(\d+))?", details_url)
            is_stale = observed_head_sha != expected_head_sha
            current = current or not is_stale
            results.append(
                {
                    "name": name,
                    "head_sha": observed_head_sha,
                    "expected_head_sha": expected_head_sha,
                    "status": "stale" if is_stale else str(value.get("status")),
                    "conclusion": value.get("conclusion") if value else None,
                    "run_id": match.group(1) if match else None,
                    "job_id": match.group(2) if match and match.group(2) else None,
                    "observed_at": observed_at,
                }
            )
        if not current:
            results.append(
                {
                    "name": name,
                    "head_sha": expected_head_sha,
                    "expected_head_sha": expected_head_sha,
                    "status": "missing",
                    "conclusion": None,
                    "run_id": None,
                    "job_id": None,
                    "observed_at": observed_at,
                }
            )
    return results


def classify_branch_ownership(
    *,
    branch: str,
    head_sha: str,
    live_remote_sha: str | None,
    tracking_sha: str | None,
    branch_prs: Sequence[dict[str, Any]],
    worktrees: Sequence[dict[str, Any]],
    expected_branch: str | None,
    expected_head_sha: str | None,
    expected_pr: int | None,
) -> tuple[str, list[Finding]]:
    findings: list[Finding] = []
    open_prs = [item for item in branch_prs if item.get("state") == "open"]
    exact_head_prs = [
        item
        for item in branch_prs
        if isinstance(item.get("head"), dict) and item["head"].get("sha") == head_sha
    ]
    exact_open = [item for item in exact_head_prs if item.get("state") == "open"]
    exact_historical = [item for item in exact_head_prs if item.get("state") != "open"]
    historical_reuse = [
        item
        for item in branch_prs
        if item.get("state") != "open"
        and isinstance(item.get("head"), dict)
        and item["head"].get("sha") != head_sha
    ]
    branch_owners = [item for item in worktrees if item.get("branch") == branch]

    if expected_branch and expected_branch != branch:
        findings.append(
            finding(
                "EXPECTED_BRANCH_MISMATCH",
                "AUTHORIZATION_BLOCKER",
                "current branch differs from the expected branch",
                "local_git",
                branch,
                False,
                "Use the authorized worktree and reviewed branch.",
                expected_branch=expected_branch,
                observed_branch=branch,
            )
        )
    if expected_head_sha and expected_head_sha != head_sha:
        findings.append(
            finding(
                "EXPECTED_HEAD_MISMATCH",
                "AUTHORIZATION_BLOCKER",
                "current HEAD differs from the expected reviewed SHA",
                "local_git",
                head_sha,
                False,
                "Refresh review state before any lifecycle operation.",
                expected_head_sha=expected_head_sha,
                observed_head_sha=head_sha,
            )
        )
    if live_remote_sha and live_remote_sha != head_sha:
        findings.append(
            finding(
                "UNEXPECTED_LIVE_REMOTE_SHA",
                "AUTHORIZATION_BLOCKER",
                "live remote branch exists at an unexpected SHA",
                "github",
                branch,
                False,
                "Resolve branch ownership with fresh authorized review.",
                live_remote_sha=live_remote_sha,
                current_head_sha=head_sha,
            )
        )
    if len(branch_owners) > 1:
        findings.append(
            finding(
                "AMBIGUOUS_WORKTREE_OWNERSHIP",
                "DESTRUCTIVE_ACTION_BLOCKER",
                "more than one registered worktree owns the same branch",
                "local_git",
                branch,
                False,
                "Stop before any branch or worktree operation.",
                worktree_paths=[item["path"] for item in branch_owners],
            )
        )
    if exact_open:
        findings.append(
            finding(
                "EXISTING_EXACT_HEAD_PUBLICATION",
                "INFORMATIONAL_DISCREPANCY",
                "an open PR already represents the exact current head",
                "github",
                head_sha,
                True,
                "Reuse the existing PR; do not create a duplicate.",
                pr_numbers=[item.get("number") for item in exact_open],
            )
        )
    elif open_prs:
        findings.append(
            finding(
                "OPEN_BRANCH_OWNERSHIP_CONFLICT",
                "AUTHORIZATION_BLOCKER",
                "an open PR owns this branch at a different head",
                "github",
                branch,
                False,
                "Resolve the unexpected open PR before publication.",
                pr_numbers=[item.get("number") for item in open_prs],
                current_head_sha=head_sha,
            )
        )
    if exact_historical:
        findings.append(
            finding(
                "EXACT_HEAD_HISTORICAL_PUBLICATION",
                "AUTHORIZATION_BLOCKER",
                "a closed or merged PR already represents the exact current head",
                "github",
                head_sha,
                False,
                "Treat publication as duplicate or inconsistent until an authorized review establishes a new head or disposition.",
                pr_numbers=[item.get("number") for item in exact_historical],
            )
        )
    if historical_reuse:
        findings.append(
            finding(
                "HISTORICAL_BRANCH_REUSE",
                "INFORMATIONAL_DISCREPANCY",
                "historical PRs use this branch name at different head SHAs",
                "github",
                branch,
                True,
                "Record historical evidence and continue with current-head ownership checks.",
                pr_numbers=[item.get("number") for item in historical_reuse],
                current_head_sha=head_sha,
            )
        )
    if tracking_sha and not live_remote_sha:
        findings.append(
            finding(
                "STALE_REMOTE_TRACKING_REF",
                "INFORMATIONAL_DISCREPANCY",
                "a local remote-tracking ref remains although the live GitHub branch is absent",
                "local_git+github",
                branch,
                True,
                "Use the live GitHub ref as authoritative; do not clean up as a side effect.",
                tracking_sha=tracking_sha,
            )
        )

    blockers = [item for item in findings if not item.may_continue]
    if blockers:
        return "ACTIVE_OWNERSHIP_CONFLICT", findings
    if exact_open:
        return "EXISTING_EXACT_HEAD_PUBLICATION", findings
    if historical_reuse:
        return "HISTORICAL_BRANCH_REUSE", findings
    if tracking_sha and not live_remote_sha:
        return "STALE_REMOTE_TRACKING_REF", findings
    return "UNOWNED_CURRENT_HEAD", findings


def validate_snapshot(snapshot: dict[str, Any], schema_path: Path = SCHEMA_PATH) -> None:
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise SchemaValidationError("unsupported delivery-state schema version")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(snapshot)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as error:
        raise SchemaValidationError("delivery-state snapshot failed schema validation") from error


def collect_snapshot(
    *,
    repo_root: Path,
    issue_number: int | None,
    expected_main_sha: str | None,
    expected_branch: str | None,
    expected_head_sha: str | None,
    expected_pr: int | None,
    protected_stash_ids: Sequence[str],
    expected_repository: str | None,
    clock: Clock = utc_now,
    git: GitTransport | None = None,
    github: GitHubTransport | None = None,
) -> dict[str, Any]:
    started = clock()
    local = git or GitTransport(repo_root)
    remote = github or GitHubTransport()
    owner, name, remote_url = repository_from_origin(local)
    repository = f"{owner}/{name}"
    if expected_repository and expected_repository.casefold() != repository.casefold():
        raise RepositoryContextError("explicit repository does not match current origin")
    repository_data = remote.api(f"repos/{repository}")
    if not isinstance(repository_data, dict) or repository_data.get("full_name") != repository:
        raise GitHubApiError("repository identity could not be verified")
    branch = local.read("branch", "--show-current").strip()
    if not branch:
        raise LocalGitError("current worktree is detached")
    head_sha = local.read("rev-parse", "HEAD").strip()
    main_branch = str(repository_data.get("default_branch") or "main")
    local_main_sha = local.read("rev-parse", main_branch).strip()
    tracking_main_sha = local.read("rev-parse", f"origin/{main_branch}").strip()
    live_main_data = remote.api(f"repos/{repository}/git/ref/heads/{main_branch}")
    if not isinstance(live_main_data, dict):
        raise GitHubApiError("live main ref is unavailable")
    live_main_sha = str(((live_main_data.get("object") or {}).get("sha")) or "")
    if not live_main_sha:
        raise GitHubApiError("live main SHA is unavailable")
    staged, unstaged, untracked, _, untracked_paths = status_summary(local)
    base_sha = local.read("merge-base", main_branch, "HEAD").strip()
    worktrees = parse_worktrees(local.read("worktree", "list", "--porcelain"), local)
    tracking_sha = local.optional_ref(f"refs/remotes/origin/{branch}")
    live_branch_data = remote.api(f"repos/{repository}/branches/{branch}", allow_not_found=True)
    live_remote_sha = (
        str(((live_branch_data or {}).get("commit") or {}).get("sha"))
        if isinstance(live_branch_data, dict)
        else None
    )
    prs = remote.paginated(f"repos/{repository}/pulls?state=all&head={owner}:{branch}&per_page=100")
    open_prs = [item for item in prs if item.get("state") == "open"]
    current_pr = next(
        (item for item in open_prs if (item.get("head") or {}).get("sha") == head_sha), None
    )
    ownership, findings = classify_branch_ownership(
        branch=branch,
        head_sha=head_sha,
        live_remote_sha=live_remote_sha,
        tracking_sha=tracking_sha,
        branch_prs=prs,
        worktrees=worktrees,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
        expected_pr=expected_pr,
    )
    if expected_main_sha and expected_main_sha not in {
        local_main_sha,
        tracking_main_sha,
        live_main_sha,
    }:
        findings.append(
            finding(
                "EXPECTED_MAIN_MISMATCH",
                "AUTHORIZATION_BLOCKER",
                "an observed main SHA differs from the expected authoritative SHA",
                "local_git+github",
                expected_main_sha,
                False,
                "Refresh authoritative main state before proceeding.",
                expected_main_sha=expected_main_sha,
                local_main_sha=local_main_sha,
                tracking_main_sha=tracking_main_sha,
                live_main_sha=live_main_sha,
            )
        )
    if len({local_main_sha, tracking_main_sha, live_main_sha}) != 1:
        findings.append(
            finding(
                "MAIN_STATE_DISAGREEMENT",
                "AUTHORIZATION_BLOCKER",
                "local, remote-tracking, and live main SHAs disagree",
                "local_git+github",
                main_branch,
                False,
                "Refresh and reconcile main state through an authorized lifecycle operation.",
                local_main_sha=local_main_sha,
                tracking_main_sha=tracking_main_sha,
                live_main_sha=live_main_sha,
            )
        )
    expected_pr_data: dict[str, Any] | None = None
    if expected_pr is not None:
        expected_pr_response = remote.api(
            f"repos/{repository}/pulls/{expected_pr}", allow_not_found=True
        )
        if expected_pr_response is not None and not isinstance(expected_pr_response, dict):
            raise GitHubApiError("expected pull-request response is malformed")
        expected_pr_data = expected_pr_response
        if expected_pr_data is None or expected_pr_data.get("state") != "open":
            findings.append(
                finding(
                    "EXPECTED_PR_UNAVAILABLE",
                    "AUTHORIZATION_BLOCKER",
                    "the expected PR is not open and available for current-head review",
                    "github",
                    str(expected_pr),
                    False,
                    "Refresh reviewed PR ownership before a lifecycle action.",
                    expected_pr=expected_pr,
                    current_head_sha=head_sha,
                    observed_state=expected_pr_data.get("state") if expected_pr_data else None,
                )
            )
    issue: dict[str, Any] | None = None
    if issue_number is not None:
        issue_data = remote.api(f"repos/{repository}/issues/{issue_number}")
        if not isinstance(issue_data, dict):
            raise GitHubApiError("issue response is malformed")
        issue = {
            "number": issue_number,
            "state": issue_data.get("state"),
            "title": issue_data.get("title"),
            "observed_at": iso_time(clock()),
        }
    checks: list[dict[str, Any]] = []
    checks_status = "not_applicable_no_current_pr"
    pull_request: dict[str, Any] | None = None
    observed_pr_data = expected_pr_data if expected_pr is not None else None
    if observed_pr_data is None and current_pr is not None:
        current_pr_data = remote.api(f"repos/{repository}/pulls/{current_pr.get('number')}")
        if not isinstance(current_pr_data, dict):
            raise GitHubApiError("current pull-request response is malformed")
        observed_pr_data = current_pr_data
    if observed_pr_data is not None:
        check_data = remote.api(f"repos/{repository}/commits/{head_sha}/check-runs")
        check_runs = check_data.get("check_runs") if isinstance(check_data, dict) else None
        if not isinstance(check_runs, list) or not all(
            isinstance(item, dict) for item in check_runs
        ):
            raise GitHubApiError("check evidence response is malformed")
        checks = parse_checks(head_sha, check_runs, iso_time(clock()))
        checks_status = "observed"
        pull_request = {
            "number": observed_pr_data.get("number"),
            "state": observed_pr_data.get("state"),
            "base_branch": (observed_pr_data.get("base") or {}).get("ref"),
            "head_branch": (observed_pr_data.get("head") or {}).get("ref"),
            "base_sha": (observed_pr_data.get("base") or {}).get("sha"),
            "head_sha": (observed_pr_data.get("head") or {}).get("sha"),
            "commit_count": observed_pr_data.get("commits"),
            "changed_file_count": observed_pr_data.get("changed_files"),
            "mergeability": observed_pr_data.get("mergeable_state"),
            "observed_at": iso_time(clock()),
        }
        if expected_pr is not None and pull_request["number"] != expected_pr:
            findings.append(
                finding(
                    "EXPECTED_PR_MISMATCH",
                    "AUTHORIZATION_BLOCKER",
                    "current PR differs from the expected PR",
                    "github",
                    str(pull_request["number"]),
                    False,
                    "Refresh reviewed PR state before a lifecycle action.",
                    expected_pr=expected_pr,
                    observed_pr=pull_request["number"],
                )
            )
        if pull_request["head_branch"] != branch:
            findings.append(
                finding(
                    "PR_HEAD_BRANCH_MISMATCH",
                    "AUTHORIZATION_BLOCKER",
                    "observed PR head branch does not match the expected current branch",
                    "github",
                    str(pull_request["number"]),
                    False,
                    "Refresh reviewed PR head state before publication or merge.",
                    expected_head_branch=branch,
                    observed_head_branch=pull_request["head_branch"],
                    expected_head_sha=head_sha,
                    observed_head_sha=pull_request["head_sha"],
                )
            )
        if pull_request["head_sha"] != head_sha:
            findings.append(
                finding(
                    "PR_HEAD_MISMATCH",
                    "AUTHORIZATION_BLOCKER",
                    "current PR head does not match current worktree HEAD",
                    "github",
                    str(pull_request["number"]),
                    False,
                    "Refresh ownership and PR state before publication or merge.",
                    expected_head_sha=head_sha,
                    observed_head_sha=pull_request["head_sha"],
                )
            )
        if pull_request["base_branch"] != main_branch:
            findings.append(
                finding(
                    "PR_BASE_BRANCH_MISMATCH",
                    "AUTHORIZATION_BLOCKER",
                    "observed PR base branch does not match the authoritative main branch",
                    "github",
                    str(pull_request["number"]),
                    False,
                    "Refresh reviewed PR base state before a lifecycle action.",
                    expected_base_branch=main_branch,
                    observed_base_branch=pull_request["base_branch"],
                    expected_base_sha=expected_main_sha,
                    observed_base_sha=pull_request["base_sha"],
                )
            )
        if expected_main_sha and pull_request["base_sha"] != expected_main_sha:
            findings.append(
                finding(
                    "PR_BASE_MISMATCH",
                    "AUTHORIZATION_BLOCKER",
                    "current PR base does not match the expected main SHA",
                    "github",
                    str(pull_request["number"]),
                    False,
                    "Refresh reviewed PR base state before a lifecycle action.",
                    expected_main_sha=expected_main_sha,
                    pr_base_sha=pull_request["base_sha"],
                )
            )
        stale_without_current_success = sorted(
            {
                record["name"]
                for record in checks
                if record["status"] == "stale"
                and not any(
                    candidate["name"] == record["name"]
                    and candidate["head_sha"] == head_sha
                    and candidate["status"] == "completed"
                    and candidate["conclusion"] == "success"
                    for candidate in checks
                )
            }
        )
        if stale_without_current_success:
            checks_status = "blocking_stale_evidence"
            findings.append(
                finding(
                    "STALE_REQUIRED_CHECK_EVIDENCE",
                    "AUTHORIZATION_BLOCKER",
                    "successful required-check evidence belongs to another head",
                    "github",
                    str(pull_request["number"]),
                    False,
                    "Wait for equivalent successful checks at the current reviewed head.",
                    stale_check_names=stale_without_current_success,
                    expected_head_sha=head_sha,
                )
            )
    stash_ids = [
        line.split(maxsplit=1)[0]
        for line in local.read("stash", "list", "--format=%H %gd").splitlines()
        if line
    ]
    protected_stash_ids = sorted(set(protected_stash_ids))
    protected = [value for value in protected_stash_ids if value in stash_ids]
    if len(protected) != len(protected_stash_ids):
        findings.append(
            finding(
                "PROTECTED_STASH_ABSENT",
                "DESTRUCTIVE_ACTION_BLOCKER",
                "the expected protected stash identifier is absent",
                "local_git",
                ",".join(protected_stash_ids),
                False,
                "Stop before cleanup or worktree lifecycle action.",
                expected_identifiers=protected_stash_ids,
                observed_identifiers=stash_ids,
            )
        )
    final_head_sha = local.read("rev-parse", "HEAD").strip()
    final_live_main_data = remote.api(f"repos/{repository}/git/ref/heads/{main_branch}")
    final_live_main_sha = str(((final_live_main_data or {}).get("object") or {}).get("sha") or "")
    if final_head_sha != head_sha or final_live_main_sha != live_main_sha:
        findings.append(
            finding(
                "SOURCE_STATE_CHANGED_DURING_COLLECTION",
                "RECOVERABLE_AUTOMATION_FAILURE",
                "critical Git or GitHub identifiers changed while collecting the snapshot",
                "local_git+github",
                branch,
                False,
                "Recollect the snapshot from stable local and remote state.",
                initial_head_sha=head_sha,
                final_head_sha=final_head_sha,
                initial_live_main_sha=live_main_sha,
                final_live_main_sha=final_live_main_sha,
            )
        )
    if pull_request is not None:
        final_pr_data = remote.api(f"repos/{repository}/pulls/{pull_request['number']}")
        final_pr_identity = {
            "state": final_pr_data.get("state") if isinstance(final_pr_data, dict) else None,
            "base_sha": ((final_pr_data.get("base") or {}).get("sha"))
            if isinstance(final_pr_data, dict)
            else None,
            "head_sha": ((final_pr_data.get("head") or {}).get("sha"))
            if isinstance(final_pr_data, dict)
            else None,
        }
        initial_pr_identity = {
            "state": pull_request["state"],
            "base_sha": pull_request["base_sha"],
            "head_sha": pull_request["head_sha"],
        }
        if final_pr_identity != initial_pr_identity:
            findings.append(
                finding(
                    "GITHUB_METADATA_CHANGED_DURING_COLLECTION",
                    "RECOVERABLE_AUTOMATION_FAILURE",
                    "PR metadata changed while collecting the snapshot",
                    "github",
                    str(pull_request["number"]),
                    False,
                    "Recollect the snapshot from stable GitHub state.",
                    initial=initial_pr_identity,
                    final=final_pr_identity,
                )
            )
    current_main = next((item for item in worktrees if item["path"] == str(repo_root)), None)
    if current_main is None:
        findings.append(
            finding(
                "WORKTREE_CHANGED_DURING_COLLECTION",
                "RECOVERABLE_AUTOMATION_FAILURE",
                "current worktree was not present in the final worktree inventory",
                "local_git",
                str(repo_root),
                False,
                "Recollect the snapshot from a stable worktree.",
                observed_worktree=False,
            )
        )
    ended = clock()
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_time(ended),
        "repository": {
            "owner": owner,
            "name": name,
            "canonical_identity": repository,
            "remote_url_classification": "github_https"
            if remote_url.startswith("https://github.com/")
            else "github_ssh",
        },
        "issue": issue,
        "git": {
            "authoritative_main_branch": main_branch,
            "expected_main_sha": expected_main_sha,
            "local_main_sha": local_main_sha,
            "remote_tracking_main_sha": tracking_main_sha,
            "live_remote_main_sha": live_main_sha,
            "current_branch": branch,
            "current_head_sha": head_sha,
            "base_sha": base_sha,
            "dirty": bool(staged or unstaged or untracked),
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
        },
        "branch_ownership": {
            "local_branch": branch,
            "live_remote_branch_exists": live_remote_sha is not None,
            "live_remote_branch_sha": live_remote_sha,
            "stale_local_remote_tracking_ref_exists": tracking_sha is not None
            and live_remote_sha is None,
            "stale_local_remote_tracking_ref_sha": tracking_sha,
            "open_prs_for_branch": [item.get("number") for item in open_prs],
            "historical_closed_or_merged_prs_for_branch": [
                item.get("number") for item in prs if item.get("state") != "open"
            ],
            "prs_for_exact_current_head": [
                item.get("number")
                for item in prs
                if (item.get("head") or {}).get("sha") == head_sha
            ],
            "classification": ownership,
        },
        "pull_request": pull_request,
        "changed_files": {
            "branch_diff": sorted(
                line
                for line in local.read(
                    "diff", "--name-only", "--merge-base", base_sha, "HEAD"
                ).splitlines()
                if line
            ),
            "staged": sorted(
                line for line in local.read("diff", "--cached", "--name-only").splitlines() if line
            ),
            "unstaged": sorted(
                line for line in local.read("diff", "--name-only").splitlines() if line
            ),
            "untracked": untracked_paths,
            "ignored_risk_paths": ignored_risk_paths(local),
        },
        "checks": {
            "required_names": list(REQUIRED_CHECKS),
            "applicable_head_sha": head_sha if current_pr else None,
            "records": checks,
            "status": checks_status,
        },
        "worktrees": worktrees,
        "stash_protections": {
            "expected_identifiers": protected_stash_ids,
            "observed_presence": len(protected) == len(protected_stash_ids),
            "observed_identifiers": stash_ids,
            "contents_inspected": False,
        },
        "classifications": {"findings": [item.as_dict() for item in findings]},
        "freshness": {
            "collection_started_at": iso_time(started),
            "collection_finished_at": iso_time(ended),
            "expected_vs_observed": {
                "repository": expected_repository or repository,
                "expected_pr": expected_pr,
                "main_sha_matches": expected_main_sha is None or expected_main_sha == live_main_sha,
                "branch_matches": expected_branch is None or expected_branch == branch,
                "head_sha_matches": expected_head_sha is None or expected_head_sha == head_sha,
                "pr_matches": expected_pr is None
                or (pull_request is not None and pull_request["number"] == expected_pr),
            },
            "stale": any(not item.may_continue for item in findings),
            "globally_atomic": False,
        },
        "next_legal_states": ["READ_ONLY_INSPECTION", "IMPLEMENTATION_WITH_SEPARATE_AUTHORIZATION"],
        "prohibited_actions": [
            "branch_or_worktree_mutation",
            "staging",
            "commit",
            "push",
            "pr_or_issue_mutation",
            "check_rerun",
            "merge",
            "deployment",
            "production_data_mutation",
            "stash_mutation",
        ],
        "sources": ["local_git", "github_api"],
    }
    validate_snapshot(snapshot)
    return snapshot


def write_output(path: Path, content: str, replace: bool) -> None:
    if path.exists() and not replace:
        raise DeliveryStateError("output path exists; explicit replacement is required")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot = subparsers.add_parser(
        "snapshot", help="collect a read-only delivery-state JSON snapshot"
    )
    snapshot.add_argument("--repo-root", type=Path, default=Path("."))
    snapshot.add_argument("--repo")
    snapshot.add_argument("--issue", type=int)
    snapshot.add_argument("--expected-main-sha")
    snapshot.add_argument("--expected-branch")
    snapshot.add_argument("--expected-head-sha")
    snapshot.add_argument("--expected-pr", type=int)
    snapshot.add_argument("--protected-stash", action="append", required=True)
    snapshot.add_argument("--at", type=parse_iso_time)
    snapshot.add_argument("--output", type=Path)
    snapshot.add_argument("--replace-output", action="store_true")
    args = parser.parse_args(argv)
    clock = (lambda: args.at) if args.at else utc_now
    try:
        report = collect_snapshot(
            repo_root=args.repo_root.resolve(),
            issue_number=args.issue,
            expected_main_sha=args.expected_main_sha,
            expected_branch=args.expected_branch,
            expected_head_sha=args.expected_head_sha,
            expected_pr=args.expected_pr,
            protected_stash_ids=args.protected_stash,
            expected_repository=args.repo,
            clock=clock,
        )
        content = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            write_output(args.output, content, args.replace_output)
        else:
            print(content, end="")
        blockers = [
            item for item in report["classifications"]["findings"] if not item["may_continue"]
        ]
        return 1 if blockers else 0
    except DeliveryStateError as error:
        print(f"delivery-state snapshot failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
