"""Inspect GitHub issue-closing evidence without lifecycle mutation.

The inspector evaluates one declared, exact-issue contract.  It makes only
repository-fixed read requests and emits sanitized evidence; it never grants
merge authority or performs a GitHub mutation, recovery operation, or closure.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "closure-linkage-evidence-v1.schema.json"
SCHEMA_VERSION = "recordstracker.closure-linkage-evidence.v1"
ROLE_VALUES = {
    "completed_target",
    "parent",
    "continuation",
    "related",
    "historical_evidence",
    "unknown",
}
READINESS_VALUES = {
    "READY_FOR_SEPARATE_MERGE_AUTHORIZATION",
    "NOT_READY",
    "EVIDENCE_INCOMPLETE",
}
RISK_CODES = {
    "NO_CLOSING_LINKAGE_DETECTED",
    "AUTHORIZED_CLOSURE_LINKAGE",
    "UNAUTHORIZED_CLOSURE_LINKAGE",
    "CLOSURE_EVIDENCE_INCOMPLETE",
    "ISSUE_STATE_PRECONDITION_MISMATCH",
    "ISSUE_ROLE_UNDECLARED",
    "CLOSURE_AUTHORITY_MISSING",
    "POST_MERGE_STATE_MATCHED",
    "POST_MERGE_UNAUTHORIZED_CLOSURE",
    "POST_MERGE_EXPECTED_CLOSURE_MISSING",
    "POST_MERGE_UNAUTHORIZED_REOPEN",
    "POST_MERGE_EXPECTED_REOPEN_MISSING",
    "POST_MERGE_STATE_REASON_MISMATCH",
    "POST_MERGE_TIMESTAMP_AMBIGUOUS",
    "CLOSURE_SOURCE_UNKNOWN",
}
PROHIBITED_ACTIONS = [
    "merge",
    "issue_close",
    "issue_reopen",
    "development_link_mutation",
    "pr_body_mutation",
    "recovery_mutation",
]
TIMELINE_CLASSIFICATIONS = {
    "informational_cross_reference",
    "explicit_closing_reference",
    "observed_development_link",
    "observed_closing_development_link",
    "operational_commit_event",
    "reopen_event",
    "close_event",
    "unknown_timeline_event",
}
MAX_GRAPHQL_PAGES = 20
Runner = Callable[..., subprocess.CompletedProcess[str]]
CLOSING_REFERENCE = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#([1-9][0-9]*)\b"
)
COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
GRAPHQL_CLOSING_QUERY = """query ClosingIssues(
  $owner: String!, $name: String!, $number: Int!, $cursor: String
) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      closingIssuesReferences(first: 100, after: $cursor) {
        nodes { number state closedAt }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}"""


class ClosureLinkageError(RuntimeError):
    """A required read-only observation was unavailable or malformed."""


class ReadOnlyGitHubTransport:
    """Fixed, read-only GitHub CLI transport with deterministic pagination."""

    development_link_effect_available = False

    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or subprocess.run

    def _run(self, arguments: Sequence[str]) -> Any:
        command = ("gh", "api", *arguments)
        try:
            result = self._runner(command, check=False, capture_output=True, text=True)
        except OSError as error:
            raise ClosureLinkageError("read-only GitHub request failed") from error
        if result.returncode:
            raise ClosureLinkageError("read-only GitHub request failed")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ClosureLinkageError("malformed GitHub response") from error

    def api(self, endpoint: str) -> dict[str, Any]:
        if not endpoint.startswith("repos/") or any(
            method in endpoint.upper() for method in ("POST", "PATCH", "PUT", "DELETE")
        ):
            raise ClosureLinkageError("non-read-only endpoint rejected")
        value = self._run((endpoint,))
        if not isinstance(value, dict):
            raise ClosureLinkageError("malformed GitHub object response")
        return value

    def paginated(self, endpoint: str) -> list[dict[str, Any]]:
        if not endpoint.startswith("repos/"):
            raise ClosureLinkageError("non-read-only endpoint rejected")
        value = self._run(("--paginate", "--slurp", endpoint))
        if not isinstance(value, list) or not all(isinstance(page, list) for page in value):
            raise ClosureLinkageError("malformed paginated GitHub response")
        result = [item for page in value for item in page]
        if not all(isinstance(item, dict) for item in result):
            raise ClosureLinkageError("malformed paginated GitHub response")
        return result

    def closing_issues(self, owner: str, name: str, number: int) -> list[dict[str, Any]]:
        """Return every GraphQL closing-reference node, or fail without a partial result."""
        if "mutation" in GRAPHQL_CLOSING_QUERY.casefold():
            raise ClosureLinkageError("GraphQL mutation rejected")
        result: list[dict[str, Any]] = []
        seen: set[int] = set()
        cursor: str | None = None
        for _ in range(MAX_GRAPHQL_PAGES):
            arguments = [
                "graphql",
                "-f",
                f"query={GRAPHQL_CLOSING_QUERY}",
                "-F",
                f"owner={owner}",
                "-F",
                f"name={name}",
                "-F",
                f"number={number}",
            ]
            if cursor is not None:
                arguments.extend(("-F", f"cursor={cursor}"))
            value = self._run(tuple(arguments))
            try:
                connection = value["data"]["repository"]["pullRequest"]["closingIssuesReferences"]
                nodes = connection["nodes"]
                page_info = connection["pageInfo"]
                has_next_page = page_info["hasNextPage"]
                end_cursor = page_info["endCursor"]
            except (KeyError, TypeError) as error:
                raise ClosureLinkageError("malformed closing-issue response") from error
            if (
                not isinstance(nodes, list)
                or not all(isinstance(item, dict) for item in nodes)
                or not isinstance(has_next_page, bool)
                or (end_cursor is not None and not isinstance(end_cursor, str))
            ):
                raise ClosureLinkageError("malformed closing-issue response")
            for item in nodes:
                issue_number = _issue_number(item.get("number"))
                if issue_number is None or issue_number in seen:
                    raise ClosureLinkageError("duplicate or invalid GraphQL closing reference")
                seen.add(issue_number)
                result.append(item)
            if not has_next_page:
                return result
            if not end_cursor or end_cursor == cursor:
                raise ClosureLinkageError("malformed GraphQL pagination cursor")
            cursor = end_cursor
        raise ClosureLinkageError("GraphQL closing-reference page limit exceeded")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _issue_number(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _numbers(values: Iterable[object]) -> list[int]:
    return sorted(number for value in values if (number := _issue_number(value)) is not None)


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_contract(contract: Iterable[dict[str, Any]], repository: str) -> list[str]:
    errors: list[str] = []
    seen: set[int] = set()
    for entry in contract:
        number = _issue_number(entry.get("issue_number"))
        if entry.get("repository") != repository:
            errors.append("repository identity mismatch")
        if number is None:
            errors.append("exact issue number is required")
            continue
        if number in seen:
            errors.append(f"duplicate issue declaration: #{number}")
        seen.add(number)
        if entry.get("role") not in ROLE_VALUES:
            errors.append(f"invalid issue role: #{number}")
        for field in ("expected_pre_merge_state", "expected_post_merge_state"):
            if entry.get(field) not in {"open", "closed"}:
                errors.append(f"invalid expected state: #{number}")
        if not isinstance(entry.get("closure_authorized"), bool) or not isinstance(
            entry.get("reopen_authorized"), bool
        ):
            errors.append(f"explicit closure and reopen authorization required: #{number}")
        if not isinstance(entry.get("authority_reference"), str) or not entry.get(
            "authority_reference"
        ):
            errors.append(f"authority reference required: #{number}")
        if not isinstance(entry.get("rationale"), str) or not entry.get("rationale"):
            errors.append(f"rationale required: #{number}")
        if not isinstance(entry.get("must_remain_open"), bool):
            errors.append(f"must_remain_open declaration required: #{number}")
    return sorted(set(errors))


def closing_references(body: str) -> list[int]:
    """Return normalized identifiers only; callers must not retain a PR body."""
    return sorted({int(match.group(1)) for match in CLOSING_REFERENCE.finditer(body)})


def _finding(code: str, issue_number: int | None, source: str, detail: str) -> dict[str, Any]:
    return {"code": code, "issue_number": issue_number, "source": source, "detail": detail}


def _sorted_findings(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda item: (str(item["code"]), item["issue_number"] or 0, str(item["source"])),
    )


def _readiness(findings: Sequence[dict[str, Any]]) -> str:
    codes = {item["code"] for item in findings}
    if codes & {
        "CLOSURE_EVIDENCE_INCOMPLETE",
        "ISSUE_ROLE_UNDECLARED",
        "CLOSURE_AUTHORITY_MISSING",
        "CLOSURE_SOURCE_UNKNOWN",
    }:
        return "EVIDENCE_INCOMPLETE"
    if codes & {"UNAUTHORIZED_CLOSURE_LINKAGE", "ISSUE_STATE_PRECONDITION_MISMATCH"}:
        return "NOT_READY"
    return "READY_FOR_SEPARATE_MERGE_AUTHORIZATION"


def _availability_for_error(error: ClosureLinkageError) -> str:
    """Classify only observable source failures; residual limits are fixed elsewhere."""
    detail = str(error).casefold()
    if "pagination" in detail or "page limit" in detail or "partial" in detail:
        return "partial"
    if "malformed" in detail or "duplicate" in detail:
        return "malformed"
    return "collection_failed"


def _post_merge_obligations(
    repository: str, pr_number: int, contract: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Bind the residual platform limitation to exact post-merge observations."""
    return [
        {
            "repository": repository,
            "pull_request_number": pr_number,
            "issue_number": int(entry["issue_number"]),
            "expected_post_merge_state": entry["expected_post_merge_state"],
            "immediate_observation_required": True,
        }
        for entry in contract
        if entry["must_remain_open"]
    ]


def _observed_state(number: int, issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_number": number,
        "state": str(issue.get("state") or "unknown"),
        "state_reason": issue.get("state_reason"),
        "closed_at": issue.get("closed_at"),
        "reopened_at": issue.get("reopened_at"),
    }


def _timeline_observation(item: dict[str, Any], pr_number: int) -> dict[str, Any]:
    """Classify only explicit timeline semantics; unknown data remains fail-closed."""
    event = item.get("event")
    source = (item.get("source") or {}).get("issue") or {}
    issue_number = _issue_number(source.get("number"))
    actor = (item.get("actor") or {}).get("login")
    occurred_at = item.get("created_at")
    commit_sha = None
    classification = "unknown_timeline_event"
    explicit_closure_semantic = False
    if not isinstance(event, str):
        event = "unknown"
    elif event == "cross-referenced" and issue_number is not None:
        classification = "informational_cross_reference"
    elif event == "connected" and issue_number is not None:
        if item.get("closes_issue") is True:
            classification = "observed_closing_development_link"
            explicit_closure_semantic = True
        else:
            classification = "observed_development_link"
    elif event == "closed":
        classification = "close_event"
        explicit_closure_semantic = True
    elif event == "reopened":
        classification = "reopen_event"
    elif event == "committed":
        candidate_sha = item.get("sha")
        author_date = (item.get("author") or {}).get("date")
        has_linkage_semantic = "source" in item or "closes_issue" in item
        if (
            isinstance(candidate_sha, str)
            and COMMIT_SHA.fullmatch(candidate_sha)
            and isinstance(author_date, str)
            and not has_linkage_semantic
        ):
            classification = "operational_commit_event"
            commit_sha = candidate_sha
            occurred_at = occurred_at if isinstance(occurred_at, str) else author_date
    return {
        "event": event,
        "classification": classification,
        "issue_number": issue_number,
        "target_pull_request_number": pr_number,
        "actor": actor if isinstance(actor, str) else None,
        "occurred_at": occurred_at if isinstance(occurred_at, str) else None,
        "commit_sha": commit_sha,
        "explicit_closure_semantic": explicit_closure_semantic,
    }


def _sorted_timeline_observations(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        observations,
        key=lambda item: (
            str(item["classification"]),
            item["issue_number"] or 0,
            str(item["event"]),
            str(item["occurred_at"] or ""),
        ),
    )


def _repository_contract_path(path: Path) -> Path:
    """Resolve an existing repository-relative contract without escape capability."""
    raw_path = str(path)
    windows_path = PureWindowsPath(raw_path)
    if (
        path.is_absolute()
        or windows_path.is_absolute()
        or raw_path.startswith(("\\\\", "//", "\\\\?\\", "\\\\.\\"))
        or ".." in windows_path.parts
    ):
        raise ClosureLinkageError("contract path rejected: must be repository-relative")
    try:
        root = ROOT.resolve(strict=True)
        resolved = (root / path).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise ClosureLinkageError("contract path rejected: outside repository") from error
    return resolved


def inspect_pre_merge(
    *,
    repository: str,
    pr_number: int,
    contract: list[dict[str, Any]],
    transport: ReadOnlyGitHubTransport,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Collect deterministic, sanitized pre-merge closure-risk evidence."""
    errors = validate_contract(contract, repository)
    if errors:
        raise ClosureLinkageError("; ".join(errors))
    if repository.count("/") != 1 or _issue_number(pr_number) is None:
        raise ClosureLinkageError("repository and pull-request identity are required")
    owner, name = repository.split("/", 1)
    identity = transport.api(f"repos/{repository}")
    if identity.get("full_name") != repository:
        raise ClosureLinkageError("repository identity mismatch")
    pr = transport.api(f"repos/{repository}/pulls/{pr_number}")
    if _issue_number(pr.get("number")) != pr_number:
        raise ClosureLinkageError("pull-request identity mismatch")

    body_links = closing_references(str(pr.get("body") or ""))
    findings: list[dict[str, Any]] = []
    try:
        graphql_links = _numbers(
            item.get("number") for item in transport.closing_issues(owner, name, pr_number)
        )
        graphql_availability = "complete"
    except ClosureLinkageError as error:
        graphql_links = []
        graphql_availability = _availability_for_error(error)
        findings.append(
            _finding(
                "CLOSURE_EVIDENCE_INCOMPLETE",
                None,
                "graphql_closing_references",
                "closing-reference collection did not complete",
            )
        )
    try:
        timeline = transport.paginated(
            f"repos/{repository}/issues/{pr_number}/timeline?per_page=100"
        )
        timeline_availability = "complete"
    except ClosureLinkageError as error:
        timeline = []
        timeline_availability = _availability_for_error(error)
        findings.append(
            _finding(
                "CLOSURE_EVIDENCE_INCOMPLETE",
                None,
                "timeline",
                "timeline collection did not complete",
            )
        )
    timeline_observations = _sorted_timeline_observations(
        _timeline_observation(item, pr_number) for item in timeline
    )
    unknown_timeline = [
        item for item in timeline_observations if item["classification"] == "unknown_timeline_event"
    ]
    for item in unknown_timeline:
        findings.append(
            _finding(
                "CLOSURE_EVIDENCE_INCOMPLETE",
                item["issue_number"],
                "timeline",
                "timeline event lacks explicit supported classification",
            )
        )
    development_links = _numbers(
        item["issue_number"]
        for item in timeline_observations
        if item["classification"] == "observed_development_link"
    )
    closing_development_links = _numbers(
        item["issue_number"]
        for item in timeline_observations
        if item["classification"] == "observed_closing_development_link"
    )
    timeline_issue_numbers = _numbers(item["issue_number"] for item in timeline_observations)
    # GitHub exposes links but not a supported read-only closure-effect field.
    # This fixed residual limitation cannot be supplied by a caller or transport.
    development_effect_availability = "platform_not_exposed"

    discoverable = sorted(set(body_links) | set(graphql_links) | set(timeline_issue_numbers))
    declared = {int(entry["issue_number"]): entry for entry in contract}
    observed_states: list[dict[str, Any]] = []
    for number in sorted(set(discoverable) | set(declared)):
        entry = declared.get(number)
        if entry is None:
            findings.extend(
                (
                    _finding(
                        "ISSUE_ROLE_UNDECLARED",
                        number,
                        "closing_evidence",
                        "discoverable issue lacks exact declared outcome",
                    ),
                    _finding(
                        "CLOSURE_AUTHORITY_MISSING",
                        number,
                        "contract",
                        "no exact closure authority exists",
                    ),
                )
            )
            continue
        try:
            issue = transport.api(f"repos/{repository}/issues/{number}")
            observed = _observed_state(number, issue)
        except ClosureLinkageError:
            observed = {
                "issue_number": number,
                "state": "unknown",
                "state_reason": None,
                "closed_at": None,
                "reopened_at": None,
            }
            findings.append(
                _finding(
                    "CLOSURE_SOURCE_UNKNOWN",
                    number,
                    "issue_state",
                    "exact pre-merge issue state is unavailable",
                )
            )
        observed_states.append(observed)
        if observed["state"] != entry["expected_pre_merge_state"]:
            findings.append(
                _finding(
                    "ISSUE_STATE_PRECONDITION_MISMATCH",
                    number,
                    "issue_state",
                    "observed state differs from exact pre-merge contract",
                )
            )
        linked_for_closure = number in body_links or number in graphql_links
        if linked_for_closure and (entry["must_remain_open"] or not entry["closure_authorized"]):
            findings.append(
                _finding(
                    "UNAUTHORIZED_CLOSURE_LINKAGE",
                    number,
                    "pr_body_or_graphql",
                    "detectable closing linkage conflicts with declared outcome",
                )
            )
        elif linked_for_closure:
            findings.append(
                _finding(
                    "AUTHORIZED_CLOSURE_LINKAGE",
                    number,
                    "pr_body_or_graphql",
                    "exact declared closure authorization observed",
                )
            )
        elif number in closing_development_links and (
            entry["must_remain_open"] or not entry["closure_authorized"]
        ):
            findings.append(
                _finding(
                    "UNAUTHORIZED_CLOSURE_LINKAGE",
                    number,
                    "timeline",
                    "explicit closing development linkage conflicts with declared open outcome",
                )
            )
        elif number in closing_development_links:
            findings.append(
                _finding(
                    "AUTHORIZED_CLOSURE_LINKAGE",
                    number,
                    "timeline",
                    "explicit closing development linkage has exact declared authorization",
                )
            )
        else:
            findings.append(
                _finding(
                    "NO_CLOSING_LINKAGE_DETECTED",
                    number,
                    "github_api",
                    "no detectable closing linkage",
                )
            )
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "repository": repository,
        "pull_request": {
            "number": pr_number,
            "base": (pr.get("base") or {}).get("ref"),
            "base_sha": (pr.get("base") or {}).get("sha"),
            "head": (pr.get("head") or {}).get("ref"),
            "head_sha": (pr.get("head") or {}).get("sha"),
        },
        "inspected_at": observed_at or utc_now(),
        "issue_outcome_contract": contract,
        "observed_closing_references": {
            "pr_body_issue_numbers": body_links,
            "graphql_issue_numbers": graphql_links,
        },
        "observed_development_links": development_links,
        "observed_timeline_evidence": timeline_observations,
        "observed_issue_states": sorted(observed_states, key=lambda item: item["issue_number"]),
        "evidence_source_availability": {
            "pr_body": "complete",
            "graphql_closing_references": graphql_availability,
            "timeline": timeline_availability,
            "development_link_closure_effect": development_effect_availability,
            "post_merge_issue_states": "not_observed",
        },
        "residual_platform_limitations": [
            {
                "mechanism": "development_link_closure_effect",
                "availability": "platform_not_exposed",
                "rationale": (
                    "GitHub supported read-only APIs expose development links but not their "
                    "closure effect."
                ),
            }
        ],
        "post_merge_verification_obligations": _post_merge_obligations(
            repository, pr_number, contract
        ),
        "closure_risk_findings": _sorted_findings(findings),
        "post_merge_findings": [],
        "primary_readiness_classification": _readiness(findings),
        "prohibited_actions": PROHIBITED_ACTIONS,
        "source_attribution": ["github_rest", "github_graphql"],
        "globally_atomic": False,
    }
    validate_evidence(evidence)
    return evidence


def _source_for_post_merge(evidence: dict[str, Any], number: int) -> str:
    refs = evidence.get("observed_closing_references", {})
    if number in refs.get("pr_body_issue_numbers", []) or number in refs.get(
        "graphql_issue_numbers", []
    ):
        return "pr_body_or_graphql"
    if number in evidence.get("observed_development_links", []):
        return "development_linkage"
    return "unknown"


def collect_post_merge_issue_states(
    evidence: dict[str, Any], transport: ReadOnlyGitHubTransport
) -> dict[str, Any]:
    """Collect only declared issue state through fixed, read-only endpoints."""
    validate_evidence(evidence)
    repository = evidence["repository"]
    pull_request = evidence["pull_request"]
    pr_number = _issue_number(pull_request.get("number"))
    if not isinstance(repository, str) or repository.count("/") != 1 or pr_number is None:
        raise ClosureLinkageError("post-merge collection identity is invalid")
    identity = transport.api(f"repos/{repository}")
    if identity.get("full_name") != repository:
        raise ClosureLinkageError("post-merge collection repository identity mismatch")
    pull_request_observation = transport.api(f"repos/{repository}/pulls/{pr_number}")
    if _issue_number(pull_request_observation.get("number")) != pr_number:
        raise ClosureLinkageError("post-merge collection pull-request identity mismatch")
    observations: list[dict[str, Any]] = []
    availability = "complete"
    for entry in evidence["issue_outcome_contract"]:
        issue_number = _issue_number(entry.get("issue_number"))
        if issue_number is None:
            raise ClosureLinkageError("post-merge collection issue identity is invalid")
        try:
            observations.append(
                _observed_state(
                    issue_number, transport.api(f"repos/{repository}/issues/{issue_number}")
                )
            )
        except ClosureLinkageError:
            availability = "incomplete"
    return {
        "repository": repository,
        "pull_request_number": pr_number,
        "merged_at": pull_request_observation.get("merged_at"),
        "availability": availability,
        "issue_states": observations,
    }


def verify_post_merge(
    evidence: dict[str, Any],
    collection: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare normalized post-merge observations without any recovery action."""
    if (
        collection.get("repository") != evidence["repository"]
        or collection.get("pull_request_number") != evidence["pull_request"]["number"]
    ):
        raise ClosureLinkageError("post-merge collection identity mismatch")
    declared_numbers = {int(entry["issue_number"]) for entry in evidence["issue_outcome_contract"]}
    normalized_states: dict[int, dict[str, Any]] = {}
    for observed in collection.get("issue_states", []):
        issue_number = (
            _issue_number(observed.get("issue_number")) if isinstance(observed, dict) else None
        )
        if issue_number is None or issue_number not in declared_numbers:
            raise ClosureLinkageError("post-merge collection contains undeclared issue")
        normalized_states[issue_number] = observed
    findings: list[dict[str, Any]] = []
    if collection.get("availability") != "complete":
        findings.append(
            _finding(
                "CLOSURE_EVIDENCE_INCOMPLETE",
                None,
                "post_merge_issue_states",
                "post-merge issue-state collection is incomplete",
            )
        )
    merge_time = _timestamp(collection.get("merged_at"))
    for entry in evidence["issue_outcome_contract"]:
        number = int(entry["issue_number"])
        observed = normalized_states.get(number)
        if observed is None:
            findings.append(
                _finding(
                    "CLOSURE_SOURCE_UNKNOWN",
                    number,
                    "issue_state",
                    "post-merge issue observation unavailable",
                )
            )
            continue
        state = str(observed.get("state") or "unknown")
        expected = entry["expected_post_merge_state"]
        source = _source_for_post_merge(evidence, number)
        observed_reason = observed.get("state_reason")
        expected_reason = entry.get("expected_post_merge_state_reason")
        closed_at = _timestamp(observed.get("closed_at"))
        reopened_at = _timestamp(observed.get("reopened_at"))
        raw_closed_at = observed.get("closed_at")
        raw_reopened_at = observed.get("reopened_at")
        malformed_timestamp = (raw_closed_at and closed_at is None) or (
            raw_reopened_at and reopened_at is None
        )
        closes_before_merge = (
            merge_time is not None and closed_at is not None and closed_at < merge_time
        )
        reopens_before_close = (
            closed_at is not None and reopened_at is not None and reopened_at < closed_at
        )
        if malformed_timestamp or closes_before_merge or reopens_before_close:
            findings.append(
                _finding(
                    "POST_MERGE_TIMESTAMP_AMBIGUOUS",
                    number,
                    "issue_state",
                    "post-merge timestamp sequence is malformed or ambiguous",
                )
            )
        if reopened_at is not None and not entry["reopen_authorized"]:
            findings.append(
                _finding(
                    "POST_MERGE_UNAUTHORIZED_REOPEN",
                    number,
                    source,
                    "reopen is observed without exact authorization; no action is taken",
                )
            )
        elif entry.get("expected_reopen") and reopened_at is None:
            findings.append(
                _finding(
                    "POST_MERGE_EXPECTED_REOPEN_MISSING",
                    number,
                    source,
                    "authorized expected reopen is not observed",
                )
            )
        if state == expected and (expected_reason is None or observed_reason == expected_reason):
            findings.append(
                _finding(
                    "POST_MERGE_STATE_MATCHED",
                    number,
                    "issue_state",
                    "observed state and declared reason match exact contract",
                )
            )
        elif state == expected and expected_reason is not None:
            findings.append(
                _finding(
                    "POST_MERGE_STATE_REASON_MISMATCH",
                    number,
                    "issue_state",
                    "observed state reason differs from exact post-merge contract",
                )
            )
        elif state == "closed" and not entry["closure_authorized"]:
            findings.append(
                _finding(
                    "POST_MERGE_UNAUTHORIZED_CLOSURE",
                    number,
                    source,
                    "unauthorized closure detected; no reopening action is available",
                )
            )
        elif expected == "closed":
            findings.append(
                _finding(
                    "POST_MERGE_EXPECTED_CLOSURE_MISSING",
                    number,
                    source,
                    "authorized expected closure did not occur",
                )
            )
        else:
            findings.append(
                _finding(
                    "CLOSURE_SOURCE_UNKNOWN",
                    number,
                    source,
                    "post-merge state differs and no authorized cause is proven",
                )
            )
    return _sorted_findings(findings)


def validate_evidence(evidence: dict[str, Any]) -> None:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(
            evidence
        )
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as error:
        raise ClosureLinkageError("closure-linkage evidence failed schema validation") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--post-merge", action="store_true")
    args = parser.parse_args(argv)
    try:
        contract = json.loads(_repository_contract_path(args.contract).read_text(encoding="utf-8"))
        if not isinstance(contract, list) or not all(isinstance(item, dict) for item in contract):
            raise ClosureLinkageError("issue-outcome contract must be a JSON array")
        evidence = inspect_pre_merge(
            repository=args.repo,
            pr_number=args.pr,
            contract=contract,
            transport=ReadOnlyGitHubTransport(),
        )
        if args.post_merge:
            collection = collect_post_merge_issue_states(evidence, ReadOnlyGitHubTransport())
            evidence["evidence_source_availability"]["post_merge_issue_states"] = collection[
                "availability"
            ]
            evidence["post_merge_findings"] = verify_post_merge(evidence, collection)
            validate_evidence(evidence)
        print(
            json.dumps(
                evidence,
                indent=2,
                sort_keys=True,
            )
        )
    except (OSError, json.JSONDecodeError, ClosureLinkageError) as error:
        print(f"Closure-linkage inspection failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
