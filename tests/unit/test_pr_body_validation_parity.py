from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "pr_body_validation" / "pr-615-full-template.md"
VALIDATOR_PATH = ROOT / "scripts" / "check_independent_verification.py"
PREPARE_PATH = ROOT / "scripts" / "prepare_pr_body.py"

PR_615_SCOPE = (
    "CONTRIBUTING.md",
    "docs/developer/codex-workflow.md",
    "schemas/delivery-state-snapshot-v1.schema.json",
    "scripts/delivery_state.py",
    "tests/fixtures/delivery_state/no-pr-stale-tracking-v1.json",
    "tests/unit/test_delivery_state.py",
)
INTENDED_OUTCOME = "- Intended outcome: Enforce one canonical PR-body validation path for DA-029."
UNRESOLVED_INSTRUCTION = (
    "unresolved PR template instruction: replace `Not run - <reason>` "
    "with completed evidence or a truthful reason"
)
MOJIBAKE_VIOLATION = (
    "invalid PR evidence text: detected mojibake em dash; preserve the intended Unicode text"
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validator() -> ModuleType:
    return _load_module("independent_verification_parity", VALIDATOR_PATH)


def _prepare() -> ModuleType:
    return _load_module("prepare_pr_body_parity", PREPARE_PATH)


class _LiveJsonTransport:
    def __init__(self, body: str) -> None:
        self.body = body

    def repository(self, repository: str) -> str:
        return repository

    def pull_request(self, _repository: str, _number: int) -> dict[str, object]:
        return {
            "state": "open",
            "body": self.body,
            "base": {"ref": "main", "sha": "base-sha"},
            "head": {"ref": "parity", "sha": "head-sha"},
        }

    def changed_files(self, _repository: str, _number: int) -> tuple[str, ...]:
        return tuple(path.replace("/", "\\") for path in PR_615_SCOPE) + (
            PR_615_SCOPE[0],
        )


def _ci_style_result(
    validator: ModuleType,
    tmp_path: Path,
    body: str,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    body_path = tmp_path / "live-pr-body.md"
    changed_path = tmp_path / "changed-files.txt"
    body_path.write_bytes(body.encode("utf-8"))
    changed_path.write_text(
        "\r\n".join(path.replace("/", "\\") for path in PR_615_SCOPE) + "\r\n",
        encoding="utf-8",
    )
    result = validator.main(
        [
            "--repo-root",
            str(ROOT),
            "--pr-body",
            str(body_path),
            "--changed-files",
            str(changed_path),
        ]
    )
    return result, capsys.readouterr().out


def _live_json_violations(prepare: ModuleType, body: str) -> list[str]:
    pull_request = prepare.fetch_open_pull_request(
        _LiveJsonTransport(body), "nicho1ab/RecordsTracker", "615"
    )
    return prepare.validate_open_pull_request(ROOT, pull_request)


@pytest.mark.parametrize(
    ("body", "expected_violation"),
    (
        (FIXTURE.read_text(encoding="utf-8"), None),
        (FIXTURE.read_text(encoding="utf-8").replace("\n", "\r\n"), None),
        (
            FIXTURE.read_text(encoding="utf-8")
            .replace(INTENDED_OUTCOME, "- Intended outcome:")
            .replace("\n", "\r\n"),
            "missing intended outcome",
        ),
        (
            FIXTURE.read_text(encoding="utf-8").replace(
                "Not run - full suite is deferred until the final stable point.",
                "Not run - <reason>",
            ),
            UNRESOLVED_INSTRUCTION,
        ),
        (
            FIXTURE.read_text(encoding="utf-8").replace("DA-029 —", "DA-029 \u00e2\u20ac\u201d"),
            MOJIBAKE_VIOLATION,
        ),
    ),
)
def test_pr_615_fixture_has_identical_decisions_across_validation_paths(
    body: str,
    expected_violation: str | None,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    validator = _validator()
    prepare = _prepare()

    direct = validator.validate_pr_evidence(ROOT, body, PR_615_SCOPE)
    file_path = tmp_path / "body.md"
    file_path.write_bytes(body.encode("utf-8"))
    file_result = validator.validate_pr_evidence(
        ROOT, file_path.read_text(encoding="utf-8"), PR_615_SCOPE
    )
    ci_exit, ci_output = _ci_style_result(validator, tmp_path, body, capsys)
    live_violations = _live_json_violations(prepare, body)

    assert file_result.body_sha256 == direct.body_sha256
    assert file_result.template_mode == direct.template_mode == "full-template"
    assert file_result.changed_files == direct.changed_files == PR_615_SCOPE
    assert live_violations == list(direct.violations)
    assert (ci_exit == 0) is (not direct.violations)
    for violation in direct.violations:
        assert f"- {violation}" in ci_output
    if expected_violation is None:
        assert direct.violations == ()
    else:
        assert expected_violation in direct.violations


def test_normalization_is_idempotent_preserves_unicode_and_trailing_newlines() -> None:
    validator = _validator()
    body = "\r\nUnicode — café\r"

    normalized = validator.normalize_pr_body(body)

    assert normalized == "\nUnicode — café\n"
    assert validator.normalize_pr_body(normalized) == normalized
    assert validator.normalized_body_sha256(body) == validator.normalized_body_sha256(normalized)


def test_instruction_detection_ignores_comments_and_accepts_truthful_reason() -> None:
    validator = _validator()
    body = FIXTURE.read_text(encoding="utf-8") + "\n<!-- Not run - <reason> -->\n"

    assert validator.find_pr_evidence_violations(body, PR_615_SCOPE) == []
    assert "Not run - full suite is deferred" in body


def test_incidental_summary_prose_does_not_select_compact_template_mode() -> None:
    validator = _validator()
    body = FIXTURE.read_text(encoding="utf-8") + "\nSummary: this is ordinary evidence prose.\n"

    result = validator.validate_pr_evidence(ROOT, body.replace("\n", "\r\n"), PR_615_SCOPE)

    assert result.template_mode == "full-template"
    assert result.violations == ()


def test_changed_file_scope_is_slash_normalized_deduplicated_and_ordered() -> None:
    validator = _validator()

    assert validator.normalize_changed_files(
        (
            " scripts\\delivery_state.py ",
            "scripts/delivery_state.py",
            "Scripts/Delivery_State.py",
            "",
            "   ",
            "CONTRIBUTING.md",
        )
    ) == ("scripts/delivery_state.py", "Scripts/Delivery_State.py", "CONTRIBUTING.md")
