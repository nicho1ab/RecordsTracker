"""Preflight tracked/publication text and audit supported GitHub content."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ccld_complaints.portable_paths import (  # noqa: E402
    PORTABLE_PATH_CONTRACT_VERSION,
    PortablePathViolation,
    find_portable_path_violations,
)

INVENTORY_SCHEMA_VERSION = "recordstracker.portable-path-remediation-inventory.v1"


class GitHubAuditError(RuntimeError):
    """GitHub content could not be audited or safely remediated."""


class GitHubContentItem(NamedTuple):
    item_type: str
    number: int
    comment_id: int | None
    endpoint: str
    body: str
    author_login: str
    updated_at: str

    @property
    def field(self) -> str:
        identifier = (
            f"comment {self.comment_id}" if self.comment_id is not None else f"#{self.number}"
        )
        return f"{self.item_type} {identifier}"


class GitHubTransport:
    """Injectable GitHub CLI transport that never emits credentials or raw bodies."""

    def __init__(self, runner: Any = subprocess.run) -> None:
        self._runner = runner

    def _api(self, *arguments: str) -> Any:
        try:
            result = self._runner(
                ("gh", "api", *arguments),
                check=True,
                capture_output=True,
                encoding="utf-8",
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise GitHubAuditError("GitHub/API request failed") from error
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise GitHubAuditError("GitHub/API response was not valid JSON") from error

    def get(self, endpoint: str) -> Mapping[str, Any]:
        value = self._api(endpoint)
        if not isinstance(value, Mapping):
            raise GitHubAuditError("GitHub/API object response was malformed")
        return value

    def paginated(self, endpoint: str) -> list[Mapping[str, Any]]:
        pages = self._api("--paginate", "--slurp", endpoint)
        if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
            raise GitHubAuditError("GitHub/API paginated response was malformed")
        items = [item for page in pages for item in page]
        if not all(isinstance(item, Mapping) for item in items):
            raise GitHubAuditError("GitHub/API paginated item was malformed")
        return items

    def update_body(self, endpoint: str, body: str) -> Mapping[str, Any]:
        payload = json.dumps({"body": body}, ensure_ascii=False).encode("utf-8")
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as handle:
            handle.write(payload)
            payload_path = Path(handle.name)
        try:
            value = self._api("--method", "PATCH", endpoint, "--input", str(payload_path))
        finally:
            payload_path.unlink(missing_ok=True)
        if not isinstance(value, Mapping):
            raise GitHubAuditError("GitHub/API mutation response was malformed")
        return value


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise GitHubAuditError(f"GitHub/API item is missing {label}")
    return value


def _required_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise GitHubAuditError(f"GitHub/API item is missing {label}")
    return value


def _author_login(item: Mapping[str, Any]) -> str:
    user = item.get("user")
    if not isinstance(user, Mapping):
        return "unknown"
    login = user.get("login")
    return login if isinstance(login, str) and login else "unknown"


def _parent_number(url: object) -> int:
    if not isinstance(url, str):
        raise GitHubAuditError("GitHub/API comment is missing its parent URL")
    value = url.rstrip("/").rsplit("/", 1)[-1]
    if not value.isdigit():
        raise GitHubAuditError("GitHub/API comment parent URL was malformed")
    return int(value)


def collect_github_content(
    transport: GitHubTransport, repository: str
) -> tuple[str, tuple[GitHubContentItem, ...]]:
    """Collect all supported issue, PR, conversation, and review-comment bodies."""

    identity = transport.get(f"repos/{repository}")
    if identity.get("full_name") != repository:
        raise GitHubAuditError("repository identity mismatch")
    viewer = _required_string(transport.get("user").get("login"), "viewer login")
    issues = transport.paginated(f"repos/{repository}/issues?state=all&per_page=100")
    issue_types: dict[int, str] = {}
    items: list[GitHubContentItem] = []
    for issue in issues:
        number = _required_int(issue.get("number"), "issue number")
        item_type = (
            "pull_request_body"
            if isinstance(issue.get("pull_request"), Mapping)
            else "issue_body"
        )
        issue_types[number] = item_type
        body = issue.get("body")
        items.append(
            GitHubContentItem(
                item_type=item_type,
                number=number,
                comment_id=None,
                endpoint=(
                    f"repos/{repository}/pulls/{number}"
                    if item_type == "pull_request_body"
                    else f"repos/{repository}/issues/{number}"
                ),
                body=body if isinstance(body, str) else "",
                author_login=_author_login(issue),
                updated_at=_required_string(issue.get("updated_at"), "content timestamp"),
            )
        )
    for comment in transport.paginated(f"repos/{repository}/issues/comments?per_page=100"):
        number = _parent_number(comment.get("issue_url"))
        parent = issue_types.get(number, "issue_body")
        body = comment.get("body")
        items.append(
            GitHubContentItem(
                item_type=(
                    "pull_request_conversation_comment"
                    if parent == "pull_request_body"
                    else "issue_comment"
                ),
                number=number,
                comment_id=_required_int(comment.get("id"), "comment identifier"),
                endpoint=f"repos/{repository}/issues/comments/{comment['id']}",
                body=body if isinstance(body, str) else "",
                author_login=_author_login(comment),
                updated_at=_required_string(comment.get("updated_at"), "content timestamp"),
            )
        )
    for comment in transport.paginated(f"repos/{repository}/pulls/comments?per_page=100"):
        number = _parent_number(comment.get("pull_request_url"))
        body = comment.get("body")
        items.append(
            GitHubContentItem(
                item_type="pull_request_review_comment",
                number=number,
                comment_id=_required_int(comment.get("id"), "review comment identifier"),
                endpoint=f"repos/{repository}/pulls/comments/{comment['id']}",
                body=body if isinstance(body, str) else "",
                author_login=_author_login(comment),
                updated_at=_required_string(comment.get("updated_at"), "content timestamp"),
            )
        )
    return viewer, tuple(
        sorted(items, key=lambda item: (item.item_type, item.number, item.comment_id or 0))
    )


def _path_basename(value: str) -> str:
    normalized = re.sub(r"[\\/]+", "/", value).rstrip("/")
    return normalized.rsplit("/", 1)[-1].strip()


def _replacement(value: str, recommendation: str) -> tuple[str, str]:
    normalized = re.sub(r"[\\/]+", "/", value)
    lowered = normalized.casefold()
    if recommendation == "<Repo Path>":
        marker = "/repos/"
        marker_index = lowered.find(marker)
        if marker_index >= 0:
            after_repos = normalized[marker_index + len(marker) :]
            suffix_index = after_repos.find("/")
            suffix = after_repos[suffix_index:] if suffix_index >= 0 else ""
            return recommendation + suffix, recommendation
    basename = _path_basename(normalized)
    if basename.casefold() in {
        "desktop",
        "documents",
        "downloads",
        "home",
        "output",
        "temp",
        "tmp",
    }:
        return recommendation, recommendation
    if "." in basename and basename not in {".", ".."}:
        return f"{recommendation}/{basename}", recommendation
    if basename:
        return f"{recommendation}/{basename}", recommendation
    return recommendation, recommendation


def portable_replacement(
    body: str, violations: Sequence[PortablePathViolation]
) -> tuple[str, tuple[str, ...]]:
    """Replace only detected spans, preserving every unrelated character."""

    candidate = body
    replacement_types: list[str] = []
    for violation in sorted(violations, key=lambda item: item.start, reverse=True):
        value = candidate[violation.start : violation.end]
        replacement, replacement_type = _replacement(
            value, violation.recommended_replacement
        )
        candidate = candidate[: violation.start] + replacement + candidate[violation.end :]
        replacement_types.append(replacement_type)
    return candidate, tuple(reversed(replacement_types))


def _inventory_record(
    item: GitHubContentItem,
    violation: PortablePathViolation,
    *,
    author_classification: str,
    editability: str,
    correction_applied: bool,
    replacement_type: str | None,
    verification_result: str,
    limitation: str | None,
    final_freshness: str | None = None,
) -> dict[str, object]:
    return {
        "item_type": item.item_type,
        "issue_or_pull_request_number": item.number,
        "comment_identifier": item.comment_id,
        "author_classification": author_classification,
        "prohibited_pattern_identifier": violation.pattern_id,
        "location": {"line": violation.line, "column": violation.column},
        "editability_classification": editability,
        "correction_applied": correction_applied,
        "replacement_type": replacement_type,
        "verification_result": verification_result,
        "limitation_or_exception": limitation,
        "source_content_freshness": {
            "updated_at": item.updated_at,
            "body_sha256": _sha256(item.body),
            "verified_updated_at": final_freshness,
        },
    }


def audit_github_content(
    *,
    transport: GitHubTransport,
    repository: str,
    apply: bool,
    now: datetime | None = None,
) -> tuple[dict[str, object], int]:
    """Audit and optionally correct supported, viewer-authored GitHub content."""

    viewer, items = collect_github_content(transport, repository)
    records: list[dict[str, object]] = []
    remaining_editable = 0
    for item in items:
        violations = find_portable_path_violations(item.body, field=item.field)
        if not violations:
            continue
        author_classification = (
            "authenticated_repository_user"
            if item.author_login.casefold() == viewer.casefold()
            else "third_party_or_other_author"
        )
        if author_classification != "authenticated_repository_user":
            records.extend(
                _inventory_record(
                    item,
                    violation,
                    author_classification=author_classification,
                    editability="third_party_authored_not_mutated",
                    correction_applied=False,
                    replacement_type=None,
                    verification_result="retained_exception",
                    limitation="Content was not authored by the authenticated repository user.",
                )
                for violation in violations
            )
            continue
        if not apply:
            remaining_editable += len(violations)
            records.extend(
                _inventory_record(
                    item,
                    violation,
                    author_classification=author_classification,
                    editability="editable",
                    correction_applied=False,
                    replacement_type=None,
                    verification_result="prohibited_path_present",
                    limitation=None,
                )
                for violation in violations
            )
            continue

        current = transport.get(item.endpoint)
        current_body = current.get("body")
        if not isinstance(current_body, str) or _sha256(current_body) != _sha256(item.body):
            remaining_editable += len(violations)
            records.extend(
                _inventory_record(
                    item,
                    violation,
                    author_classification=author_classification,
                    editability="editable_concurrent_drift",
                    correction_applied=False,
                    replacement_type=None,
                    verification_result="not_mutated",
                    limitation="Content changed after collection; no mutation was attempted.",
                )
                for violation in violations
            )
            continue

        candidate, replacement_types = portable_replacement(item.body, violations)
        candidate_violations = find_portable_path_violations(candidate, field=item.field)
        if candidate_violations:
            remaining_editable += len(violations)
            records.extend(
                _inventory_record(
                    item,
                    violation,
                    author_classification=author_classification,
                    editability="editable_preflight_rejected",
                    correction_applied=False,
                    replacement_type=None,
                    verification_result="not_mutated",
                    limitation="Portable-path publication preflight rejected the candidate.",
                )
                for violation in violations
            )
            continue

        transport.update_body(item.endpoint, candidate)
        persisted = transport.get(item.endpoint)
        persisted_body = persisted.get("body")
        persisted_at = persisted.get("updated_at")
        verified = (
            isinstance(persisted_body, str)
            and persisted_body == candidate
            and not find_portable_path_violations(persisted_body, field=item.field)
        )
        if not verified:
            remaining_editable += len(violations)
        records.extend(
            _inventory_record(
                item,
                violation,
                author_classification=author_classification,
                editability="editable",
                correction_applied=True,
                replacement_type=replacement_types[index],
                verification_result="verified_absent" if verified else "persistence_mismatch",
                limitation=None if verified else "The persisted body did not equal the candidate.",
                final_freshness=persisted_at if isinstance(persisted_at, str) else None,
            )
            for index, violation in enumerate(violations)
        )

    audit_time = now or datetime.now(UTC)
    inventory: dict[str, object] = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "portable_path_contract_version": PORTABLE_PATH_CONTRACT_VERSION,
        "audit_timestamp": audit_time.isoformat(),
        "repository": repository,
        "audit_scope": [
            "open_and_closed_issue_bodies",
            "issue_comments",
            "open_and_closed_pull_request_bodies",
            "pull_request_conversation_comments",
            "pull_request_review_comments",
        ],
        "records": sorted(
            records,
            key=lambda record: (
                str(record["item_type"]),
                int(record["issue_or_pull_request_number"]),
                int(record["comment_identifier"] or 0),
                int(cast(Mapping[str, object], record["location"])["line"]),
                int(cast(Mapping[str, object], record["location"])["column"]),
            ),
        ),
        "summary": {
            "content_items_audited": len(items),
            "matches_classified": len(records),
            "corrections_applied": sum(
                record["correction_applied"] is True for record in records
            ),
            "retained_or_uneditable": sum(
                record["verification_result"] == "retained_exception" for record in records
            ),
            "editable_matches_remaining": remaining_editable,
        },
    }
    return inventory, remaining_editable


def preview_github_replacement_lines(
    transport: GitHubTransport, repository: str
) -> tuple[str, ...]:
    """Return sanitized candidate lines for review without mutating GitHub."""

    viewer, items = collect_github_content(transport, repository)
    previews: list[str] = []
    for item in items:
        if item.author_login.casefold() != viewer.casefold():
            continue
        violations = find_portable_path_violations(item.body, field=item.field)
        if not violations:
            continue
        redacted = item.body
        for violation in sorted(violations, key=lambda value: value.start, reverse=True):
            redacted = (
                redacted[: violation.start]
                + "<REDACTED_PERSONAL_PATH>"
                + redacted[violation.end :]
            )
        candidate, _replacement_types = portable_replacement(item.body, violations)
        if find_portable_path_violations(candidate, field=item.field):
            previews.append(f"{item.field}: candidate preflight failed")
            continue
        candidate_lines = candidate.splitlines()
        redacted_lines = redacted.splitlines()
        for line in sorted({violation.line for violation in violations}):
            rendered = candidate_lines[line - 1] if line <= len(candidate_lines) else ""
            original = redacted_lines[line - 1] if line <= len(redacted_lines) else ""
            previews.append(
                f"{item.field}, line {line}: current {original} | candidate {rendered}"
            )
    return tuple(previews)


def scan_tracked_files(repo_root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ("git", "-C", str(repo_root), "ls-files", "-z"),
        check=True,
        capture_output=True,
    )
    diagnostics: list[str] = []
    for relative_path in result.stdout.decode("utf-8").split("\0"):
        if not relative_path:
            continue
        path = repo_root / relative_path
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        diagnostics.extend(
            violation.diagnostic()
            for violation in find_portable_path_violations(
                content,
                field=Path(relative_path).as_posix(),
                source_path=relative_path,
                allow_approved_fixture=True,
            )
        )
    return tuple(diagnostics)


def _write_inventory(path: Path, inventory: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _print_diagnostics(diagnostics: Iterable[str]) -> int:
    values = tuple(diagnostics)
    if not values:
        print("Portable-path contract passed.")
        return 0
    print("Portable-path contract failed:")
    for diagnostic in values:
        print(f"- {diagnostic}")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    tracked = subparsers.add_parser("tracked")
    tracked.add_argument("--repo-root", type=Path, default=Path("."))
    publication = subparsers.add_parser("publication")
    publication.add_argument("--field", required=True)
    publication.add_argument("--input", type=Path, required=True)
    github = subparsers.add_parser("github")
    github.add_argument("--repository", required=True)
    github.add_argument("--apply", action="store_true")
    github.add_argument("--preview-lines", action="store_true")
    github.add_argument("--inventory-output", type=Path)
    args = parser.parse_args(argv)

    if args.command == "tracked":
        return _print_diagnostics(scan_tracked_files(args.repo_root))
    if args.command == "publication":
        content = args.input.read_text(encoding="utf-8")
        return _print_diagnostics(
            violation.diagnostic()
            for violation in find_portable_path_violations(content, field=args.field)
        )
    transport = GitHubTransport()
    if args.preview_lines:
        for preview in preview_github_replacement_lines(transport, args.repository):
            print(preview)
    inventory, remaining = audit_github_content(
        transport=transport,
        repository=args.repository,
        apply=args.apply,
    )
    if args.inventory_output is not None:
        _write_inventory(args.inventory_output, inventory)
    summary = cast(Mapping[str, object], inventory["summary"])
    print(
        "GitHub portable-path audit completed: "
        f"{summary['content_items_audited']} items, "
        f"{summary['matches_classified']} matches, "
        f"{summary['corrections_applied']} corrections, "
        f"{summary['retained_or_uneditable']} retained or uneditable, "
        f"{summary['editable_matches_remaining']} editable matches remaining."
    )
    return 1 if remaining else 0


if __name__ == "__main__":
    raise SystemExit(main())
