from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_portable_paths.py"


def _audit() -> ModuleType:
    spec = importlib.util.spec_from_file_location("github_portable_path_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _windows(*parts: str) -> str:
    return "\\".join(("C:", "Users", *parts))


class FakeTransport:
    def __init__(self, body: str, *, author: str = "repository-user") -> None:
        self.body = body
        self.author = author
        self.update_calls: list[tuple[str, str]] = []

    def get(self, endpoint: str):
        if endpoint == "repos/example/RecordsTracker":
            return {"full_name": "example/RecordsTracker"}
        if endpoint == "user":
            return {"login": "repository-user"}
        return {
            "body": self.body,
            "updated_at": "2026-07-28T00:00:01Z",
        }

    def paginated(self, endpoint: str):
        if endpoint.endswith("/issues?state=all&per_page=100"):
            return [
                {
                    "number": 550,
                    "body": self.body,
                    "user": {"login": self.author},
                    "updated_at": "2026-07-28T00:00:00Z",
                }
            ]
        return []

    def update_body(self, endpoint: str, body: str):
        self.update_calls.append((endpoint, body))
        self.body = body
        return {"body": body, "updated_at": "2026-07-28T00:00:01Z"}


class CoverageTransport(FakeTransport):
    def paginated(self, endpoint: str):
        if endpoint.endswith("/issues?state=all&per_page=100"):
            common = {
                "body": "",
                "user": {"login": "repository-user"},
                "updated_at": "2026-07-28T00:00:00Z",
            }
            return [
                {"number": 1, **common},
                {"number": 2, "pull_request": {"url": "sanitized"}, **common},
            ]
        if endpoint.endswith("/issues/comments?per_page=100"):
            return [
                {
                    "id": 11,
                    "issue_url": "https://api.github.com/repos/example/RecordsTracker/issues/1",
                    "body": "",
                    "user": {"login": "repository-user"},
                    "updated_at": "2026-07-28T00:00:00Z",
                },
                {
                    "id": 12,
                    "issue_url": "https://api.github.com/repos/example/RecordsTracker/issues/2",
                    "body": "",
                    "user": {"login": "repository-user"},
                    "updated_at": "2026-07-28T00:00:00Z",
                },
            ]
        if endpoint.endswith("/pulls/comments?per_page=100"):
            return [
                {
                    "id": 13,
                    "pull_request_url": (
                        "https://api.github.com/repos/example/RecordsTracker/pulls/2"
                    ),
                    "body": "",
                    "user": {"login": "repository-user"},
                    "updated_at": "2026-07-28T00:00:00Z",
                }
            ]
        return []


def test_collection_covers_all_supported_github_content_classes() -> None:
    audit = _audit()

    _viewer, items = audit.collect_github_content(
        CoverageTransport(""),
        "example/RecordsTracker",
    )

    assert [item.item_type for item in items] == [
        "issue_body",
        "issue_comment",
        "pull_request_body",
        "pull_request_conversation_comment",
        "pull_request_review_comment",
    ]


def test_supported_github_body_is_preflighted_corrected_and_verified() -> None:
    audit = _audit()
    raw_path = _windows(
        "synthetic-user",
        "Desktop",
        "evidence",
        "recordstracker-evidence-manifest.json",
    )
    transport = FakeTransport(f"Evidence manifest: `{raw_path}`")

    inventory, remaining = audit.audit_github_content(
        transport=transport,
        repository="example/RecordsTracker",
        apply=True,
        now=datetime(2026, 7, 28, tzinfo=UTC),
    )

    assert remaining == 0
    assert len(transport.update_calls) == 1
    assert transport.body == (
        "Evidence manifest: `<Evidence Path>/recordstracker-evidence-manifest.json`"
    )
    assert inventory["summary"] == {
        "content_items_audited": 1,
        "matches_classified": 1,
        "corrections_applied": 1,
        "retained_or_uneditable": 0,
        "editable_matches_remaining": 0,
    }
    serialized = json.dumps(inventory)
    assert raw_path not in serialized
    assert "synthetic-user" not in serialized

    schema = json.loads(
        (ROOT / "schemas/portable-path-remediation-inventory-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator(schema).validate(inventory)


def test_line_only_unquoted_path_with_spaces_preserves_final_component() -> None:
    audit = _audit()
    raw_path = _windows(
        "synthetic-user",
        "Desktop",
        "RecordsTracker Issue 446 Runtime Evidence",
    )
    transport = FakeTransport(raw_path)

    inventory, remaining = audit.audit_github_content(
        transport=transport,
        repository="example/RecordsTracker",
        apply=True,
        now=datetime(2026, 7, 28, tzinfo=UTC),
    )

    assert remaining == 0
    assert transport.body == "<Evidence Path>/RecordsTracker Issue 446 Runtime Evidence"
    assert inventory["records"][0]["replacement_type"] == "<Evidence Path>"


def test_third_party_comment_is_classified_without_mutation() -> None:
    audit = _audit()
    raw_path = "/" + "/".join(("home", "other-author", "result.json"))
    transport = FakeTransport(raw_path, author="other-author")

    inventory, remaining = audit.audit_github_content(
        transport=transport,
        repository="example/RecordsTracker",
        apply=True,
        now=datetime(2026, 7, 28, tzinfo=UTC),
    )

    assert remaining == 0
    assert transport.update_calls == []
    record = inventory["records"][0]
    assert record["editability_classification"] == "third_party_authored_not_mutated"
    assert record["verification_result"] == "retained_exception"


def test_mutation_is_not_attempted_when_candidate_preflight_rejects(
    monkeypatch,
) -> None:
    audit = _audit()
    raw_path = _windows("synthetic-user", "Desktop", "result.json")
    transport = FakeTransport(raw_path)
    original = audit.find_portable_path_violations
    calls = 0

    def reject_candidate(text: str, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original(text, **kwargs)
        return original(raw_path, **kwargs)

    monkeypatch.setattr(audit, "find_portable_path_violations", reject_candidate)

    inventory, remaining = audit.audit_github_content(
        transport=transport,
        repository="example/RecordsTracker",
        apply=True,
        now=datetime(2026, 7, 28, tzinfo=UTC),
    )

    assert remaining == 1
    assert transport.update_calls == []
    assert inventory["records"][0]["editability_classification"] == (
        "editable_preflight_rejected"
    )


def test_tracked_inventory_verifies_issue_550_and_632_remediation_without_raw_paths() -> None:
    audit = _audit()
    path = ROOT / "docs/analysis/issue-632-portable-path-remediation.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    records = inventory["records"]

    assert {record["issue_or_pull_request_number"] for record in records} >= {550, 632}
    assert all(record["verification_result"] == "verified_absent" for record in records)
    serialized = json.dumps(inventory, sort_keys=True)
    assert audit.find_portable_path_violations(
        serialized,
        field="remediation inventory",
    ) == ()
