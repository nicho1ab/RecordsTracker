"""Render, preflight, and safely repair governed pull-request evidence bodies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_independent_verification as verification

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
SUPPORTED_POLICY_VERSION = verification.SUPPORTED_POLICY_VERSION
SUPPORTED_SCHEMA_VERSION = verification.SUPPORTED_SCHEMA_VERSION
Runner = Callable[..., subprocess.CompletedProcess[str]]


class PrBodyLifecycleError(RuntimeError):
    """Base error for a safe open-pull-request body lifecycle failure."""


class GitHubApiError(PrBodyLifecycleError):
    """GitHub CLI or API access did not return usable lifecycle data."""


class MutationResponseError(GitHubApiError):
    """The completed body PATCH did not return a usable response representation."""


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


class PersistenceOutcome(StrEnum):
    """Stable, machine-readable conclusions for one guarded persistence attempt."""

    NO_MUTATION_PRECONDITION_FAILED = "NO_MUTATION_PRECONDITION_FAILED"
    NO_MUTATION_ALREADY_CONVERGED = "NO_MUTATION_ALREADY_CONVERGED"
    MUTATION_API_FAILED = "MUTATION_API_FAILED"
    MUTATION_RESPONSE_INVALID = "MUTATION_RESPONSE_INVALID"
    IMMEDIATE_CONVERGENCE = "IMMEDIATE_CONVERGENCE"
    DELAYED_CONVERGENCE = "DELAYED_CONVERGENCE"
    TRANSIENT_REPRESENTATION_DISAGREEMENT = "TRANSIENT_REPRESENTATION_DISAGREEMENT"
    STABLE_PERSISTENCE_MISMATCH = "STABLE_PERSISTENCE_MISMATCH"
    PR_IDENTITY_CHANGED = "PR_IDENTITY_CHANGED"
    UNEXPLAINED_NONCANDIDATE_BODY_CHANGE = "UNEXPLAINED_NONCANDIDATE_BODY_CHANGE"
    POST_PERSISTENCE_VALIDATION_FAILED = "POST_PERSISTENCE_VALIDATION_FAILED"
    GRAPHQL_UNAVAILABLE = "GRAPHQL_UNAVAILABLE"
    OBSERVATION_API_FAILED = "OBSERVATION_API_FAILED"


PERSISTENCE_EVIDENCE_SCHEMA_VERSION = "pr-body-persistence-attempt-v1"
DEFAULT_STABILIZATION_OBSERVATIONS = 3
DEFAULT_STABILIZATION_INTERVAL_SECONDS = 1.0


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _raw_body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def changed_scope_sha256(changed_files: Sequence[str]) -> str:
    """Hash the canonical complete changed-file scope without platform variance."""

    canonical = verification.normalize_changed_files(changed_files)
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def build_body_payload(body: str) -> bytes:
    """Build the only supported UTF-8 request payload for a PR-body mutation."""

    payload = {"body": body}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    decoded = json.loads(encoded.decode("utf-8"))
    if not isinstance(decoded, dict) or tuple(decoded) != ("body",) or decoded["body"] != body:
        raise ProposalValidationError(
            "PR-body mutation payload must contain exactly the body field"
        )
    return encoded


class MutationPreconditions(NamedTuple):
    """Immutable facts an explicitly authorized body-only mutation must bind."""

    repository: str
    number: int
    state: str
    draft: bool
    base: str
    base_sha: str
    head: str
    head_sha: str
    scope_sha256: str
    body_sha256: str
    candidate_sha256: str
    authorization: str


class PersistenceObservation(NamedTuple):
    """Sanitized body observation; full PR body text is intentionally absent."""

    source: str
    observed_at: str
    normalized_body_sha256: str | None
    mojibake_detected: bool | None
    api_status: int | None
    equals_candidate: bool | None
    representations_agree: bool | None
    identity_and_scope_stable: bool | None


class PersistenceAttempt:
    """Versioned, sanitized evidence for one and only one possible PATCH."""

    def __init__(
        self,
        *,
        preconditions: MutationPreconditions,
        candidate_normalized_sha256: str,
        candidate_request_sha256: str,
    ) -> None:
        self.preconditions = preconditions
        self.candidate_normalized_sha256 = candidate_normalized_sha256
        self.candidate_request_sha256 = candidate_request_sha256
        self.payload_sha256: str | None = None
        self.payload_keys: tuple[str, ...] = ()
        self.mutation_count = 0
        self.observations: list[PersistenceObservation] = []
        self.classifications: list[PersistenceOutcome] = []
        self.outcome: PersistenceOutcome | None = None
        self.validator_violations: tuple[str, ...] = ()
        self.final_state = "not_started"

    def add_classification(self, outcome: PersistenceOutcome) -> None:
        if outcome not in self.classifications:
            self.classifications.append(outcome)

    def finish(self, outcome: PersistenceOutcome, *, final_state: str) -> PersistenceAttempt:
        self.add_classification(outcome)
        self.outcome = outcome
        self.final_state = final_state
        return self

    def to_evidence(self) -> dict[str, object]:
        """Return JSON-safe evidence without full bodies, tokens, or headers."""

        return {
            "schema_version": PERSISTENCE_EVIDENCE_SCHEMA_VERSION,
            "repository": self.preconditions.repository,
            "pull_request": self.preconditions.number,
            "immutable_expected_values": {
                "state": self.preconditions.state,
                "draft": self.preconditions.draft,
                "base": self.preconditions.base,
                "base_sha": self.preconditions.base_sha,
                "head": self.preconditions.head,
                "head_sha": self.preconditions.head_sha,
                "scope_sha256": self.preconditions.scope_sha256,
                "live_body_sha256": self.preconditions.body_sha256,
                "candidate_body_sha256": self.preconditions.candidate_sha256,
            },
            "mutation_authorization": self.preconditions.authorization,
            "candidate_normalized_sha256": self.candidate_normalized_sha256,
            "candidate_request_sha256": self.candidate_request_sha256,
            "payload_sha256": self.payload_sha256,
            "payload_keys": list(self.payload_keys),
            "mutation_count": self.mutation_count,
            "observations": [observation._asdict() for observation in self.observations],
            "classifications": [outcome.value for outcome in self.classifications],
            "outcome": self.outcome.value if self.outcome else None,
            "validator_violations": list(self.validator_violations),
            "final_state": self.final_state,
            "globally_atomic": False,
            "prohibited_actions": ["retry", "rollback", "second PATCH"],
            "source_attribution": ["REST", "GraphQL where available"],
        }


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
        state: str = "open",
        draft: bool = False,
        title: str = "",
    ) -> None:
        self.repository = repository
        self.number = number
        self.body = body
        self.base = base
        self.base_sha = base_sha
        self.head = head
        self.head_sha = head_sha
        self.changed_files = changed_files
        self.state = state
        self.draft = draft
        self.title = title


def normalize_body(body: str) -> str:
    """Delegate to the canonical validator normalization boundary."""

    return verification.normalize_pr_body(body)


def body_sha256(body: str) -> str:
    """Return the canonical validator's normalized UTF-8 body hash."""

    return verification.normalized_body_sha256(body)


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


def render_compact_policy_evidence(
    policy_input: dict[str, object],
    *,
    delta: str,
    validation_newly_performed: list[str],
    live_evidence_recollected: list[str],
    body_prefix: str = "",
    body_suffix: str = "",
) -> str:
    """Format compact evidence with the validator's non-self-referential body hash."""

    preliminary = verification.compact_policy_section(
        policy_input,
        delta=delta,
        validation_newly_performed=validation_newly_performed,
        live_evidence_recollected=live_evidence_recollected,
    )
    bound_input = verification.bind_compact_policy_body_hash(
        policy_input, body_prefix + preliminary + body_suffix
    )
    rendered = verification.compact_policy_section(
        bound_input,
        delta=delta,
        validation_newly_performed=validation_newly_performed,
        live_evidence_recollected=live_evidence_recollected,
    )
    repository_state = bound_input.get("repository_state")
    if not isinstance(repository_state, dict):
        raise ValueError("compact policy input is missing repository state")
    body_hash = repository_state.get("pr_body_hash")
    if not isinstance(body_hash, str):
        raise ValueError("compact policy input is missing bound body hash")
    if (
        verification.canonical_compact_body_sha256(body_prefix + rendered + body_suffix)
        != body_hash
    ):
        raise ValueError("compact policy body hash did not stabilize")
    return rendered


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
        list(verification.validate_pr_evidence(repo_root, body, changed_files).violations)
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

    def update_body(self, repository: str, number: int, body: str) -> dict[str, object]:
        """Issue one byte-safe body-only PATCH and return its REST response."""

        encoded_payload = build_body_payload(body)
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as payload:
            payload.write(encoded_payload)
            payload_path = Path(payload.name)
        try:
            response = self._api(
                "--method",
                "PATCH",
                f"repos/{repository}/pulls/{number}",
                "--input",
                str(payload_path),
            )
            try:
                return _parse_json(
                    response, f"PR-body mutation response for pull request #{number}"
                )
            except GitHubApiError as error:
                raise MutationResponseError("malformed PR-body mutation response") from error
        finally:
            try:
                payload_path.unlink(missing_ok=True)
            except OSError:
                # Cleanup is best-effort only; it must not hide whether PATCH ran.
                pass

    def graphql_body(self, repository: str, number: int) -> str:
        """Read one body representation through a fixed, non-interpolated query."""

        owner, name = repository.split("/", 1)
        query = (
            "query($owner:String!,$name:String!,$number:Int!){"
            "repository(owner:$owner,name:$name){pullRequest(number:$number){body}}}"
        )
        data = _parse_json(
            self._api(
                "graphql",
                "-f",
                f"query={query}",
                "-F",
                f"owner={owner}",
                "-F",
                f"name={name}",
                "-F",
                f"number={number}",
            ),
            f"GraphQL pull-request body for #{number}",
        )
        repository_data = data.get("data")
        if not isinstance(repository_data, dict):
            raise GitHubApiError("malformed GitHub/API response: missing GraphQL data")
        node = repository_data.get("repository")
        if not isinstance(node, dict) or not isinstance(node.get("pullRequest"), dict):
            raise GitHubApiError("malformed GitHub/API response: missing GraphQL pull request")
        body = node["pullRequest"].get("body")
        if not isinstance(body, str):
            raise GitHubApiError("malformed GitHub/API response: missing GraphQL body")
        return body


_NUMBER_REFERENCE = re.compile(r"^#?(?P<number>[1-9][0-9]*)$")
_QUALIFIED_REFERENCE = re.compile(r"^(?P<repository>[^/\s]+/[^#\s]+)#(?P<number>[1-9][0-9]*)$")
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
    title = data.get("title")
    draft = data.get("draft", False)
    if not isinstance(draft, bool):
        raise GitHubApiError("malformed GitHub/API response: invalid pull-request draft state")
    return OpenPullRequest(
        repository=resolved_repository,
        number=number,
        body=body,
        base=_nested_string(data, "base", "ref", "pull-request base"),
        base_sha=_nested_string(data, "base", "sha", "pull-request base SHA"),
        head=_nested_string(data, "head", "ref", "pull-request head"),
        head_sha=_nested_string(data, "head", "sha", "pull-request head SHA"),
        changed_files=transport.changed_files(resolved_repository, number),
        state="open",
        draft=draft,
        title=title if isinstance(title, str) else "",
    )


def _live_state_for_pull_request(
    pull_request: OpenPullRequest, live_pr_state: Mapping[str, object] | None, *, body: str | None = None
) -> Mapping[str, object] | None:
    if live_pr_state is None:
        return None
    expected = {
        "repository": pull_request.repository,
        "pull_request_number": pull_request.number,
        "base_ref": pull_request.base,
        "base_sha": pull_request.base_sha,
        "head_ref": pull_request.head,
        "head_sha": pull_request.head_sha,
    }
    if any(live_pr_state.get(key) != value for key, value in expected.items()):
        raise ProposalValidationError("authoritative live PR state does not match current PR identity")
    if live_pr_state.get("changed_file_inventory_complete") is not True:
        raise ProposalValidationError("authoritative changed-file inventory is incomplete")
    if body is None and normalize_body(str(live_pr_state.get("body", ""))) != normalize_body(pull_request.body):
        raise ProposalValidationError("authoritative live PR state body is stale")
    normalized = dict(live_pr_state)
    normalized["body"] = pull_request.body if body is None else body
    return normalized


def verification_violations(
    repo_root: Path, body: str, changed_files: Sequence[str], live_pr_state: Mapping[str, object] | None = None
) -> list[str]:
    """Use exactly the production independent-verification implementation."""

    return list(verification.validate_pr_evidence(repo_root, body, changed_files, live_pr_state=live_pr_state).violations)


def validate_open_pull_request(repo_root: Path, pull_request: OpenPullRequest, live_pr_state: Mapping[str, object] | None = None) -> list[str]:
    """Validate the live API body against the current complete API file scope."""

    return verification_violations(repo_root, pull_request.body, pull_request.changed_files, _live_state_for_pull_request(pull_request, live_pr_state))


def validate_proposed_repair(
    repo_root: Path, pull_request: OpenPullRequest, proposal: str, live_pr_state: Mapping[str, object] | None = None
) -> list[str]:
    """Validate a file proposal against live scope without mutating GitHub."""

    return verification_violations(repo_root, proposal, pull_request.changed_files, _live_state_for_pull_request(pull_request, live_pr_state, body=proposal))


def _raise_for_violations(violations: list[str]) -> None:
    if violations:
        raise ProposalValidationError("; ".join(violations))


def preview_open_pull_request_repair(
    *, repo_root: Path, pull_request: OpenPullRequest, proposal: str, live_pr_state: Mapping[str, object] | None = None
) -> tuple[list[str], list[str], bool]:
    """Return live/proposed validation results and normalized material difference."""

    live_violations = validate_open_pull_request(repo_root, pull_request, live_pr_state)
    proposal_violations = validate_proposed_repair(repo_root, pull_request, proposal, live_pr_state)
    differs = normalize_body(pull_request.body) != normalize_body(proposal)
    return live_violations, proposal_violations, differs


def _precondition_mismatches(
    pull_request: OpenPullRequest,
    preconditions: MutationPreconditions,
    *,
    include_body: bool,
) -> list[str]:
    observed = (
        ("repository", pull_request.repository, preconditions.repository),
        ("number", pull_request.number, preconditions.number),
        ("state", pull_request.state, preconditions.state),
        ("draft", pull_request.draft, preconditions.draft),
        ("base", pull_request.base, preconditions.base),
        ("base SHA", pull_request.base_sha, preconditions.base_sha),
        ("head", pull_request.head, preconditions.head),
        ("head SHA", pull_request.head_sha, preconditions.head_sha),
        (
            "changed-file scope SHA-256",
            changed_scope_sha256(pull_request.changed_files),
            preconditions.scope_sha256,
        ),
    )
    mismatches = [f"{name} changed" for name, actual, expected in observed if actual != expected]
    if include_body and body_sha256(pull_request.body) != preconditions.body_sha256:
        mismatches.append("live body changed")
    return mismatches


def _contains_mojibake(body: str) -> bool:
    return "\u00e2\u20ac\u201d" in normalize_body(body)


def _record_observation(
    attempt: PersistenceAttempt,
    *,
    source: str,
    body: str | None,
    candidate: str,
    api_status: int | None,
    representations_agree: bool | None,
    identity_and_scope_stable: bool | None,
    now: Callable[[], str],
) -> None:
    attempt.observations.append(
        PersistenceObservation(
            source=source,
            observed_at=now(),
            normalized_body_sha256=body_sha256(body) if body is not None else None,
            mojibake_detected=_contains_mojibake(body) if body is not None else None,
            api_status=api_status,
            equals_candidate=normalize_body(body) == normalize_body(candidate)
            if body is not None
            else None,
            representations_agree=representations_agree,
            identity_and_scope_stable=identity_and_scope_stable,
        )
    )


def _graphql_body_or_none(
    transport: GitHubTransport,
    repository: str,
    number: int,
    attempt: PersistenceAttempt,
) -> str | None:
    try:
        return transport.graphql_body(repository, number)
    except (AttributeError, GitHubApiError):
        attempt.add_classification(PersistenceOutcome.GRAPHQL_UNAVAILABLE)
        return None


def _observe_live_representations(
    *,
    transport: GitHubTransport,
    repository: str,
    number: int,
    preconditions: MutationPreconditions,
    candidate: str,
    attempt: PersistenceAttempt,
    label: str,
    now: Callable[[], str],
) -> OpenPullRequest | None:
    try:
        observed = fetch_open_pull_request(transport, repository, str(number))
    except PullRequestStateError:
        attempt.add_classification(PersistenceOutcome.PR_IDENTITY_CHANGED)
        _record_observation(
            attempt,
            source=f"{label}:rest",
            body=None,
            candidate=candidate,
            api_status=None,
            representations_agree=None,
            identity_and_scope_stable=False,
            now=now,
        )
        return None
    except GitHubApiError:
        attempt.add_classification(PersistenceOutcome.OBSERVATION_API_FAILED)
        _record_observation(
            attempt,
            source=f"{label}:rest",
            body=None,
            candidate=candidate,
            api_status=None,
            representations_agree=None,
            identity_and_scope_stable=None,
            now=now,
        )
        return None
    topology_stable = not _precondition_mismatches(observed, preconditions, include_body=False)
    graphql_body = _graphql_body_or_none(transport, repository, number, attempt)
    representations_agree = (
        normalize_body(observed.body) == normalize_body(graphql_body)
        if graphql_body is not None
        else None
    )
    _record_observation(
        attempt,
        source=f"{label}:rest",
        body=observed.body,
        candidate=candidate,
        api_status=200,
        representations_agree=representations_agree,
        identity_and_scope_stable=topology_stable,
        now=now,
    )
    if graphql_body is not None:
        _record_observation(
            attempt,
            source=f"{label}:graphql",
            body=graphql_body,
            candidate=candidate,
            api_status=200,
            representations_agree=representations_agree,
            identity_and_scope_stable=topology_stable,
            now=now,
        )
    else:
        _record_observation(
            attempt,
            source=f"{label}:graphql",
            body=None,
            candidate=candidate,
            api_status=None,
            representations_agree=None,
            identity_and_scope_stable=topology_stable,
            now=now,
        )
    return observed


def _complete_convergence(
    *,
    repo_root: Path,
    pull_request: OpenPullRequest,
    attempt: PersistenceAttempt,
    delayed: bool,
    live_pr_state: Mapping[str, object] | None = None,
) -> PersistenceAttempt:
    if live_pr_state is None:
        violations = tuple(validate_open_pull_request(repo_root, pull_request))
    else:
        refreshed_live_state = _live_state_for_pull_request(
            pull_request, live_pr_state, body=pull_request.body
        )
        violations = tuple(
            verification_violations(
                repo_root, pull_request.body, pull_request.changed_files, refreshed_live_state
            )
        )
    attempt.validator_violations = violations
    if violations:
        return attempt.finish(
            PersistenceOutcome.POST_PERSISTENCE_VALIDATION_FAILED,
            final_state="converged_body_failed_production_validation",
        )
    outcome = (
        PersistenceOutcome.DELAYED_CONVERGENCE
        if delayed
        else PersistenceOutcome.IMMEDIATE_CONVERGENCE
    )
    return attempt.finish(outcome, final_state="converged_and_production_validated")


def apply_open_pull_request_repair(
    *,
    transport: GitHubTransport,
    repo_root: Path,
    repository: str,
    reference: str,
    proposal: str,
    preconditions: MutationPreconditions,
    confirmed: bool,
    max_observations: int = DEFAULT_STABILIZATION_OBSERVATIONS,
    interval_seconds: float = DEFAULT_STABILIZATION_INTERVAL_SECONDS,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], str] = _utc_now,
    live_pr_state: Mapping[str, object] | None = None,
) -> PersistenceAttempt:
    """Apply at most one body PATCH and classify sanitized persistence evidence.

    The only loop below is bounded, read-only observation. No branch can issue a
    second PATCH or a rollback request after the mutation budget is consumed.
    """

    if max_observations < 0 or interval_seconds < 0:
        raise ProposalValidationError("stabilization bounds must be non-negative")
    if preconditions.authorization != "body-only":
        raise ProposalValidationError("apply requires explicit body-only mutation intent")
    candidate_normalized_hash = body_sha256(proposal)
    attempt = PersistenceAttempt(
        preconditions=preconditions,
        candidate_normalized_sha256=candidate_normalized_hash,
        candidate_request_sha256=_raw_body_sha256(proposal),
    )
    if candidate_normalized_hash != preconditions.candidate_sha256:
        return attempt.finish(
            PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED,
            final_state="candidate_hash_mismatch",
        )
    try:
        initial = fetch_open_pull_request(transport, repository, reference)
    except (GitHubApiError, PullRequestStateError):
        return attempt.finish(
            PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED,
            final_state="initial_observation_failed",
        )
    initial_mismatches = _precondition_mismatches(initial, preconditions, include_body=True)
    _record_observation(
        attempt,
        source="pre_mutation:rest",
        body=initial.body,
        candidate=proposal,
        api_status=200,
        representations_agree=None,
        identity_and_scope_stable=not initial_mismatches,
        now=now,
    )
    if initial_mismatches:
        return attempt.finish(
            PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED,
            final_state="; ".join(initial_mismatches),
        )
    violations = tuple(validate_proposed_repair(repo_root, initial, proposal, live_pr_state))
    if violations:
        attempt.validator_violations = violations
        return attempt.finish(
            PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED,
            final_state="candidate_failed_production_validation",
        )
    if normalize_body(initial.body) == normalize_body(proposal):
        completed = _complete_convergence(
            repo_root=repo_root, pull_request=initial, attempt=attempt, delayed=False, live_pr_state=live_pr_state
        )
        if completed.outcome is PersistenceOutcome.POST_PERSISTENCE_VALIDATION_FAILED:
            return completed
        return completed.finish(
            PersistenceOutcome.NO_MUTATION_ALREADY_CONVERGED, final_state="already_converged"
        )
    if not confirmed:
        raise ProposalValidationError("apply requires --confirm-update before any PR-body mutation")
    # A fresh refetch binds the mutation to current immutable state immediately before PATCH.
    refreshed = _observe_live_representations(
        transport=transport,
        repository=repository,
        number=initial.number,
        preconditions=preconditions,
        candidate=proposal,
        attempt=attempt,
        label="pre_patch",
        now=now,
    )
    if refreshed is None:
        if PersistenceOutcome.PR_IDENTITY_CHANGED in attempt.classifications:
            return attempt.finish(
                PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED,
                final_state="pre_patch_PR_identity_changed",
            )
        return attempt.finish(
            PersistenceOutcome.OBSERVATION_API_FAILED, final_state="pre_patch_failed"
        )
    refreshed_mismatches = _precondition_mismatches(refreshed, preconditions, include_body=True)
    if refreshed_mismatches:
        return attempt.finish(
            PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED,
            final_state="; ".join(refreshed_mismatches),
        )
    payload = build_body_payload(proposal)
    attempt.payload_sha256 = hashlib.sha256(payload).hexdigest()
    decoded_payload = json.loads(payload.decode("utf-8"))
    attempt.payload_keys = tuple(decoded_payload)
    if attempt.payload_keys != ("body",):
        return attempt.finish(
            PersistenceOutcome.NO_MUTATION_PRECONDITION_FAILED,
            final_state="payload_not_body_only",
        )
    if attempt.mutation_count != 0:
        raise AssertionError("one-mutation budget already consumed")
    attempt.mutation_count = 1
    try:
        response = transport.update_body(refreshed.repository, refreshed.number, proposal)
    except MutationResponseError:
        return attempt.finish(
            PersistenceOutcome.MUTATION_RESPONSE_INVALID,
            final_state="PATCH_response_malformed",
        )
    except GitHubApiError:
        return attempt.finish(PersistenceOutcome.MUTATION_API_FAILED, final_state="PATCH_failed")
    response_body = response.get("body") if isinstance(response, dict) else None
    if not isinstance(response_body, str):
        _record_observation(
            attempt,
            source="mutation_response:rest",
            body=None,
            candidate=proposal,
            api_status=200,
            representations_agree=None,
            identity_and_scope_stable=None,
            now=now,
        )
        return attempt.finish(
            PersistenceOutcome.MUTATION_RESPONSE_INVALID,
            final_state="PATCH_response_missing_body",
        )
    _record_observation(
        attempt,
        source="mutation_response:rest",
        body=response_body,
        candidate=proposal,
        api_status=200,
        representations_agree=None,
        identity_and_scope_stable=None,
        now=now,
    )
    last_rest_hash: str | None = None
    for index in range(max_observations + 1):
        label = "immediate" if index == 0 else f"stabilization:{index}"
        try:
            observed = _observe_live_representations(
                transport=transport,
                repository=repository,
                number=initial.number,
                preconditions=preconditions,
                candidate=proposal,
                attempt=attempt,
                label=label,
                now=now,
            )
        except BaseException:
            return attempt.finish(
                PersistenceOutcome.OBSERVATION_API_FAILED,
                final_state="post_PATCH_observation_interrupted",
            )
        if observed is None:
            if PersistenceOutcome.PR_IDENTITY_CHANGED in attempt.classifications:
                return attempt.finish(
                    PersistenceOutcome.PR_IDENTITY_CHANGED,
                    final_state="post_PATCH_PR_identity_changed",
                )
            return attempt.finish(
                PersistenceOutcome.OBSERVATION_API_FAILED,
                final_state="post_PATCH_observation_failed",
            )
        topology_mismatches = _precondition_mismatches(observed, preconditions, include_body=False)
        if topology_mismatches:
            return attempt.finish(
                PersistenceOutcome.PR_IDENTITY_CHANGED,
                final_state="; ".join(topology_mismatches),
            )
        rest_hash = body_sha256(observed.body)
        latest_graphql = next(
            (item for item in reversed(attempt.observations) if item.source == f"{label}:graphql"),
            None,
        )
        graph_matches = (
            latest_graphql is None
            or latest_graphql.normalized_body_sha256 is None
            or latest_graphql.equals_candidate is True
        )
        rest_matches = normalize_body(observed.body) == normalize_body(proposal)
        representations_agree = (
            latest_graphql is None
            or latest_graphql.normalized_body_sha256 is None
            or latest_graphql.normalized_body_sha256 == rest_hash
        )
        if rest_matches and graph_matches and representations_agree:
            return _complete_convergence(
                repo_root=repo_root, pull_request=observed, attempt=attempt, delayed=index > 0,
                live_pr_state=live_pr_state
            )
        if not representations_agree:
            attempt.add_classification(PersistenceOutcome.TRANSIENT_REPRESENTATION_DISAGREEMENT)
        if last_rest_hash is not None and rest_hash != last_rest_hash and not rest_matches:
            return attempt.finish(
                PersistenceOutcome.UNEXPLAINED_NONCANDIDATE_BODY_CHANGE,
                final_state="noncandidate_body_changed_during_stabilization",
            )
        last_rest_hash = rest_hash
        if index < max_observations:
            try:
                sleeper(interval_seconds)
            except BaseException:
                return attempt.finish(
                    PersistenceOutcome.OBSERVATION_API_FAILED,
                    final_state="post_PATCH_stabilization_interrupted",
                )
    return attempt.finish(
        PersistenceOutcome.STABLE_PERSISTENCE_MISMATCH,
        final_state="bounded_read_only_stabilization_exhausted",
    )


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


def _write_persistence_evidence(repo_root: Path, path: Path, attempt: PersistenceAttempt) -> None:
    """Persist only opt-in sanitized lifecycle evidence, never a full PR body."""

    root = repo_root.resolve()
    destination = path.resolve()
    try:
        destination.relative_to(root / "data" / "processed")
    except ValueError as error:
        raise ProposalValidationError(
            "persistence evidence must be stored under data/processed"
        ) from error
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(attempt.to_evidence(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("expected boolean value true or false")


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
        live_pr_state = (
            _parse_json(args.live_pr_state.read_text(encoding="utf-8"), "authoritative live PR state")
            if args.live_pr_state is not None
            else None
        )
        if args.open_pr_action == "validate":
            _print_open_pr_summary(pull_request)
            return _print_violations(
                validate_open_pull_request(args.repo_root, pull_request, live_pr_state)
            )
        proposal = _read_proposal(args.body)
        if args.open_pr_action == "preview":
            live, proposed, differs = preview_open_pull_request_repair(
                repo_root=args.repo_root, pull_request=pull_request, proposal=proposal,
                live_pr_state=live_pr_state
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
        preconditions = MutationPreconditions(
            repository=repository,
            number=pull_request.number,
            state=args.expected_state,
            draft=args.expected_draft,
            base=args.expected_base,
            base_sha=args.expected_base_sha,
            head=args.expected_head,
            head_sha=args.expected_head_sha,
            scope_sha256=args.expected_scope_sha256,
            body_sha256=args.expected_body_sha256,
            candidate_sha256=args.expected_candidate_sha256,
            authorization=args.body_only_intent,
        )
        attempt = apply_open_pull_request_repair(
            transport=client,
            repo_root=args.repo_root,
            repository=repository,
            reference=args.pr,
            proposal=proposal,
            preconditions=preconditions,
            confirmed=args.confirm_update,
            max_observations=args.max_observations,
            interval_seconds=args.interval_seconds,
            live_pr_state=live_pr_state,
        )
    except PrBodyLifecycleError as error:
        return _print_lifecycle_error(error)
    if args.evidence is not None:
        try:
            _write_persistence_evidence(args.repo_root, args.evidence, attempt)
        except (OSError, PrBodyLifecycleError):
            print("Persistence evidence write failed after the recorded mutation outcome.")
            print(f"Persistence outcome: {attempt.outcome.value if attempt.outcome else 'UNKNOWN'}")
            print(f"Mutation count: {attempt.mutation_count}")
            return 1
    print(f"Persistence outcome: {attempt.outcome.value if attempt.outcome else 'UNKNOWN'}")
    print(f"Mutation count: {attempt.mutation_count}")
    if attempt.outcome in {
        PersistenceOutcome.IMMEDIATE_CONVERGENCE,
        PersistenceOutcome.DELAYED_CONVERGENCE,
        PersistenceOutcome.NO_MUTATION_ALREADY_CONVERGED,
    }:
        return 0
    return 1


def _add_open_pr_arguments(parser: argparse.ArgumentParser, *, proposal: bool) -> None:
    parser.add_argument(
        "--pr", required=True, help="PR number, qualified reference, or GitHub PR URL"
    )
    parser.add_argument(
        "--repo", help="GitHub owner/repository; must match current origin when supplied"
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--live-pr-state", type=Path, help="authoritative normalized live PR snapshot")
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
    apply.add_argument("--expected-body-sha256", required=True)
    apply.add_argument("--expected-candidate-sha256", required=True)
    apply.add_argument("--expected-state", required=True, choices=("open",))
    apply.add_argument("--expected-draft", required=True, type=_parse_bool)
    apply.add_argument("--expected-base", required=True)
    apply.add_argument("--expected-base-sha", required=True)
    apply.add_argument("--expected-head", required=True)
    apply.add_argument("--expected-head-sha", required=True)
    apply.add_argument("--expected-scope-sha256", required=True)
    apply.add_argument(
        "--body-only-intent",
        required=True,
        choices=("body-only",),
        help="explicit mutation intent; no other PR field is permitted",
    )
    apply.add_argument("--confirm-update", action="store_true", help="confirm the body-only update")
    apply.add_argument("--max-observations", type=int, default=DEFAULT_STABILIZATION_OBSERVATIONS)
    apply.add_argument(
        "--interval-seconds", type=float, default=DEFAULT_STABILIZATION_INTERVAL_SECONDS
    )
    apply.add_argument(
        "--evidence",
        type=Path,
        help="optional ignored-path destination for sanitized persistence evidence",
    )
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
