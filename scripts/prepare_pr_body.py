"""Render, preflight, and safely repair governed pull-request evidence bodies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_independent_verification as verification

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
Runner = Callable[..., subprocess.CompletedProcess[str]]


class PrBodyLifecycleError(RuntimeError):
    """Base error for a safe open-pull-request body lifecycle failure."""


class GitHubApiError(PrBodyLifecycleError):
    """GitHub CLI or API access did not return usable lifecycle data."""


class RepositoryContextError(PrBodyLifecycleError):
    """The requested repository does not match the current repository context."""


class PullRequestReferenceError(PrBodyLifecycleError):
    """The supplied pull-request reference cannot be resolved safely."""


class PullRequestStateError(PrBodyLifecycleError):
    """The supplied pull request is unavailable or unsupported for repair."""


class ProposalValidationError(PrBodyLifecycleError):
    """The proposal fails the production independent-verification rules."""


class ConcurrentBodyUpdateError(PrBodyLifecycleError):
    """The live body changed after the expected lifecycle snapshot."""


class PersistenceMismatchError(PrBodyLifecycleError):
    """GitHub did not persist the validated proposed body."""


class OpenPullRequest:
    """The minimum current PR state needed for governed body validation."""

    def __init__(
        self,
        *,
        repository: str,
        number: int,
        body: str,
        base: str,
        base_sha: str,
        head: str,
        head_sha: str,
        changed_files: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.number = number
        self.body = body
        self.base = base
        self.base_sha = base_sha
        self.head = head
        self.head_sha = head_sha
        self.changed_files = changed_files


def normalize_body(body: str) -> str:
    """Normalize transport line endings without changing substantive Markdown."""

    return body.replace("\r\n", "\n").replace("\r", "\n")


def body_sha256(body: str) -> str:
    """Return a stable hash of the transport-normalized body."""

    return hashlib.sha256(normalize_body(body).encode("utf-8")).hexdigest()


def _changed_files_from_git(base: str) -> list[str]:
    commands = (
        ("git", "diff", "--name-only", "--merge-base", base, "HEAD"),
        ("git", "diff", "--name-only"),
        ("git", "diff", "--cached", "--name-only"),
        ("git", "ls-files", "--others", "--exclude-standard"),
    )
    files: dict[str, None] = {}
    for command in commands:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if line.strip():
                files.setdefault(line.strip(), None)
    return list(files)


def _print_violations(violations: list[str]) -> int:
    if violations:
        print("Independent verification failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("Independent verification passed.")
    return 0


def render_body(output: Path) -> int:
    output.write_text(TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Wrote PR evidence template to {output}")
    return 0


def preflight_body(
    *,
    body_path: Path,
    changed_files_path: Path | None,
    base: str,
    repo_root: Path,
) -> int:
    body = body_path.read_text(encoding="utf-8")
    changed_files = (
        verification._changed_files(changed_files_path)
        if changed_files_path is not None
        else _changed_files_from_git(base)
    )
    return _print_violations(
        verification.find_verification_violations(repo_root, body, changed_files)
    )


def _parse_json(output: str, description: str) -> dict[str, object]:
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        raise GitHubApiError(f"malformed GitHub/API response for {description}") from error
    if not isinstance(value, dict):
        raise GitHubApiError(f"malformed GitHub/API response for {description}")
    return value


def _required_string(value: object, description: str) -> str:
    if not isinstance(value, str) or not value:
        raise GitHubApiError(f"malformed GitHub/API response: missing {description}")
    return value


def _nested_string(value: dict[str, object], key: str, nested_key: str, description: str) -> str:
    nested = value.get(key)
    if not isinstance(nested, dict):
        raise GitHubApiError(f"malformed GitHub/API response: missing {description}")
    return _required_string(nested.get(nested_key), description)


class GitHubTransport:
    """A small, injectable GitHub CLI transport with no credential output."""

    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or subprocess.run

    def _api(self, *arguments: str) -> str:
        command = ("gh", "api", *arguments)
        try:
            result = self._runner(command, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as error:
            raise GitHubApiError("GitHub/API request failed") from error
        return result.stdout

    def repository(self, repository: str) -> str:
        data = _parse_json(self._api(f"repos/{repository}"), "repository")
        resolved = _required_string(data.get("full_name"), "repository full_name")
        if resolved.casefold() != repository.casefold():
            raise RepositoryContextError(
                f"requested repository {repository!r} resolved as unexpected {resolved!r}"
            )
        return resolved

    def pull_request(self, repository: str, number: int) -> dict[str, object]:
        return _parse_json(
            self._api(f"repos/{repository}/pulls/{number}"), f"pull request #{number}"
        )

    def changed_files(self, repository: str, number: int) -> tuple[str, ...]:
        output = self._api(
            "--paginate",
            f"repos/{repository}/pulls/{number}/files?per_page=100",
            "--jq",
            ".[].filename",
        )
        return tuple(line.strip() for line in output.splitlines() if line.strip())

    def update_body(self, repository: str, number: int, body: str) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        ) as payload:
            payload.write(json.dumps({"body": body}, ensure_ascii=False))
            payload_path = Path(payload.name)
        try:
            self._api(
                "--method",
                "PATCH",
                f"repos/{repository}/pulls/{number}",
                "--input",
                str(payload_path),
            )
        finally:
            payload_path.unlink(missing_ok=True)


_NUMBER_REFERENCE = re.compile(r"^#?(?P<number>[1-9][0-9]*)$")
_QUALIFIED_REFERENCE = re.compile(
    r"^(?P<repository>[^/\s]+/[^#\s]+)#(?P<number>[1-9][0-9]*)$"
)
_URL_REFERENCE = re.compile(
    r"^https://github\.com/(?P<repository>[^/\s]+/[^/\s]+)/pull/(?P<number>[1-9][0-9]*)/?$"
)


def resolve_pull_request_number(reference: str, repository: str) -> int:
    """Resolve numeric, qualified, and GitHub URL pull-request references."""

    value = reference.strip()
    for pattern in (_NUMBER_REFERENCE, _QUALIFIED_REFERENCE, _URL_REFERENCE):
        match = pattern.fullmatch(value)
        if match is None:
            continue
        qualified_repository = match.groupdict().get("repository")
        if qualified_repository and qualified_repository.casefold() != repository.casefold():
            raise RepositoryContextError(
                f"pull-request reference belongs to {qualified_repository!r}, not {repository!r}"
            )
        return int(match.group("number"))
    raise PullRequestReferenceError(
        "cannot resolve pull-request reference; use a number, #number, "
        "owner/repository#number, or a github.com pull-request URL"
    )


def repository_from_git(repo_root: Path) -> str:
    """Derive only a GitHub repository identity from the current origin remote."""

    try:
        result = subprocess.run(
            ("git", "config", "--get", "remote.origin.url"),
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RepositoryContextError("cannot determine current origin repository") from error
    remote = result.stdout.strip()
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([^/\s]+/[^/\s]+?)(?:\.git)?",
        remote,
    )
    if match is None:
        raise RepositoryContextError("current origin is not a github.com owner/repository remote")
    return match.group(1)


def fetch_open_pull_request(
    transport: GitHubTransport, repository: str, reference: str
) -> OpenPullRequest:
    """Fetch current live PR evidence and its complete, paginated changed-file scope."""

    resolved_repository = transport.repository(repository)
    if resolved_repository.casefold() != repository.casefold():
        raise RepositoryContextError(
            f"requested repository {repository!r} resolved as unexpected {resolved_repository!r}"
        )
    number = resolve_pull_request_number(reference, resolved_repository)
    data = transport.pull_request(resolved_repository, number)
    if data.get("state") != "open":
        raise PullRequestStateError(
            f"pull request #{number} is not open; open-PR body repair supports "
            "open pull requests only"
        )
    body = data.get("body")
    if body is None:
        body = ""
    if not isinstance(body, str):
        raise GitHubApiError("malformed GitHub/API response: missing pull-request body")
    return OpenPullRequest(
        repository=resolved_repository,
        number=number,
        body=body,
        base=_nested_string(data, "base", "ref", "pull-request base"),
        base_sha=_nested_string(data, "base", "sha", "pull-request base SHA"),
        head=_nested_string(data, "head", "ref", "pull-request head"),
        head_sha=_nested_string(data, "head", "sha", "pull-request head SHA"),
        changed_files=transport.changed_files(resolved_repository, number),
    )


def verification_violations(repo_root: Path, body: str, changed_files: Sequence[str]) -> list[str]:
    """Use exactly the production independent-verification implementation."""

    return verification.find_verification_violations(repo_root, body, list(changed_files))


def validate_open_pull_request(repo_root: Path, pull_request: OpenPullRequest) -> list[str]:
    """Validate the live API body against the current complete API file scope."""

    return verification_violations(repo_root, pull_request.body, pull_request.changed_files)


def validate_proposed_repair(
    repo_root: Path, pull_request: OpenPullRequest, proposal: str
) -> list[str]:
    """Validate a file proposal against live scope without mutating GitHub."""

    return verification_violations(repo_root, proposal, pull_request.changed_files)


def _raise_for_violations(violations: list[str]) -> None:
    if violations:
        raise ProposalValidationError("; ".join(violations))


def preview_open_pull_request_repair(
    *, repo_root: Path, pull_request: OpenPullRequest, proposal: str
) -> tuple[list[str], list[str], bool]:
    """Return live/proposed validation results and normalized material difference."""

    live_violations = validate_open_pull_request(repo_root, pull_request)
    proposal_violations = validate_proposed_repair(repo_root, pull_request, proposal)
    differs = normalize_body(pull_request.body) != normalize_body(proposal)
    return live_violations, proposal_violations, differs


def apply_open_pull_request_repair(
    *,
    transport: GitHubTransport,
    repo_root: Path,
    repository: str,
    reference: str,
    proposal: str,
    expected_body_sha256: str | None,
    confirmed: bool,
) -> bool:
    """Safely apply one validated body-only repair, returning whether it mutated GitHub."""

    initial = fetch_open_pull_request(transport, repository, reference)
    _raise_for_violations(validate_proposed_repair(repo_root, initial, proposal))
    if normalize_body(initial.body) == normalize_body(proposal):
        return False
    if not confirmed:
        raise ProposalValidationError("apply requires --confirm-update before any PR-body mutation")
    if expected_body_sha256 is None:
        raise ConcurrentBodyUpdateError(
            "apply requires --expected-body-sha256 from the previewed live body"
        )
    refreshed = fetch_open_pull_request(transport, initial.repository, str(initial.number))
    if body_sha256(refreshed.body) != expected_body_sha256:
        raise ConcurrentBodyUpdateError(
            "live PR body changed after preview; fetch and validate a new proposal before applying"
        )
    _raise_for_violations(validate_proposed_repair(repo_root, refreshed, proposal))
    transport.update_body(refreshed.repository, refreshed.number, proposal)
    persisted = fetch_open_pull_request(transport, refreshed.repository, str(refreshed.number))
    _raise_for_violations(validate_open_pull_request(repo_root, persisted))
    if normalize_body(persisted.body) != normalize_body(proposal):
        raise PersistenceMismatchError(
            "GitHub persisted a materially different PR body than the validated proposal"
        )
    return True


def _read_proposal(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProposalValidationError(f"cannot read proposed PR body: {path}") from error


def _print_open_pr_summary(pull_request: OpenPullRequest) -> None:
    print(
        f"Open PR #{pull_request.number} in {pull_request.repository}: "
        f"base {pull_request.base}@{pull_request.base_sha}, "
        f"head {pull_request.head}@{pull_request.head_sha}, "
        f"{len(pull_request.changed_files)} changed files."
    )
    print(f"Current body SHA-256: {body_sha256(pull_request.body)}")


def _print_lifecycle_error(error: PrBodyLifecycleError) -> int:
    if isinstance(error, ProposalValidationError):
        print(f"Validation failure: {error}")
    elif isinstance(error, ConcurrentBodyUpdateError):
        print(f"Concurrency conflict: {error}")
    elif isinstance(error, PersistenceMismatchError):
        print(f"Persistence mismatch: {error}")
    elif isinstance(error, (GitHubApiError, PullRequestReferenceError, PullRequestStateError)):
        print(f"GitHub/API failure: {error}")
    else:
        print(f"Repository context failure: {error}")
    return 1


def _open_pr_repository(args: argparse.Namespace) -> str:
    derived = repository_from_git(args.repo_root)
    if args.repo is not None and args.repo.casefold() != derived.casefold():
        raise RepositoryContextError(
            f"explicit repository {args.repo!r} does not match current origin {derived!r}"
        )
    return args.repo or derived


def open_pr_main(args: argparse.Namespace, transport: GitHubTransport | None = None) -> int:
    """Run one noninteractive open-PR lifecycle action without printing full bodies."""

    client = transport or GitHubTransport()
    try:
        repository = _open_pr_repository(args)
        pull_request = fetch_open_pull_request(client, repository, args.pr)
        if args.open_pr_action == "validate":
            _print_open_pr_summary(pull_request)
            return _print_violations(validate_open_pull_request(args.repo_root, pull_request))
        proposal = _read_proposal(args.body)
        if args.open_pr_action == "preview":
            live, proposed, differs = preview_open_pull_request_repair(
                repo_root=args.repo_root, pull_request=pull_request, proposal=proposal
            )
            _print_open_pr_summary(pull_request)
            print("Current body validation: " + ("passed" if not live else "failed"))
            for violation in live:
                print(f"- {violation}")
            if proposed:
                print("Proposed body validation: failed")
                for violation in proposed:
                    print(f"- {violation}")
                return 1
            print("Proposed body validation: passed")
            print("Proposed body differs materially: " + ("yes" if differs else "no"))
            return 0
        changed = apply_open_pull_request_repair(
            transport=client,
            repo_root=args.repo_root,
            repository=repository,
            reference=args.pr,
            proposal=proposal,
            expected_body_sha256=args.expected_body_sha256,
            confirmed=args.confirm_update,
        )
    except PrBodyLifecycleError as error:
        return _print_lifecycle_error(error)
    if changed:
        print("PR body update applied and refetched validation passed.")
    else:
        print("PR body already matches validated proposal; no update applied.")
    return 0


def _add_open_pr_arguments(parser: argparse.ArgumentParser, *, proposal: bool) -> None:
    parser.add_argument(
        "--pr", required=True, help="PR number, qualified reference, or GitHub PR URL"
    )
    parser.add_argument(
        "--repo", help="GitHub owner/repository; must match current origin when supplied"
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    if proposal:
        parser.add_argument(
            "--body", type=Path, required=True, help="proposed governed PR-body file"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    render = subparsers.add_parser("render", help="copy the authoritative PR template")
    render.add_argument("--output", type=Path, required=True)
    preflight = subparsers.add_parser(
        "preflight", help="validate a proposed body with the same rules as CI"
    )
    preflight.add_argument("--body", type=Path, required=True)
    preflight.add_argument("--changed-files", type=Path)
    preflight.add_argument("--base", default="origin/main")
    preflight.add_argument("--repo-root", type=Path, default=Path("."))
    open_pr = subparsers.add_parser(
        "open-pr", help="validate, preview, or explicitly apply a body-only open-PR repair"
    )
    open_pr_subparsers = open_pr.add_subparsers(dest="open_pr_action", required=True)
    validate = open_pr_subparsers.add_parser("validate", help="validate the current live PR body")
    _add_open_pr_arguments(validate, proposal=False)
    preview = open_pr_subparsers.add_parser(
        "preview", help="validate a proposed repair without mutation"
    )
    _add_open_pr_arguments(preview, proposal=True)
    apply = open_pr_subparsers.add_parser(
        "apply", help="explicitly update only a validated PR body"
    )
    _add_open_pr_arguments(apply, proposal=True)
    apply.add_argument("--expected-body-sha256", help="current body hash reported by preview")
    apply.add_argument("--confirm-update", action="store_true", help="confirm the body-only update")
    args = parser.parse_args(argv)
    if args.command == "render":
        return render_body(args.output)
    if args.command == "preflight":
        return preflight_body(
            body_path=args.body,
            changed_files_path=args.changed_files,
            base=args.base,
            repo_root=args.repo_root,
        )
    return open_pr_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
