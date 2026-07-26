"""Fail closed on machine-verifiable pull-request verification evidence.

This script deliberately validates only objective repository controls. It does
not approve product, UX, privacy, security, legal, or governance decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, NamedTuple

REQUIRED_WORKFLOWS: dict[str, tuple[str, tuple[str, ...]]] = {
    ".github/workflows/ci.yml": (
        "validate",
        ("ruff check .", "mypy src", "pytest", "python scripts/check_docs.py"),
    ),
    ".github/workflows/docs-check.yml": ("docs-check", ("python scripts/check_docs.py",)),
    ".github/workflows/regression.yml": (
        "fixtures",
        ("pytest tests/regression tests/fixtures",),
    ),
    ".github/workflows/security.yml": (
        "security",
        (
            "python scripts/check_no_secrets.py",
            "pip-audit -r requirements.txt -r requirements-dev.txt",
        ),
    ),
}

REQUIRED_BOUNDARIES = (
    "Schemas and migrations",
    "Ingestion and source-connector contracts",
    "Security and privacy",
    "Production data and correction behavior",
    "Deployment and infrastructure",
    "Repository governance",
    "Required GitHub workflows and checks",
    "Tests or checks weakened to obtain passage",
)

REQUIRED_TEMPLATE_SECTIONS = (
    "Governing issue and intended outcome",
    "Implementation scope",
    "Acceptance-criteria evidence",
    "Validation and failure classification",
    "UI and accessibility evidence (when applicable)",
    "Reviewer-facing redesign artifact classification (when applicable)",
    "Documentation, assumptions, and remaining risks",
    "Governed-boundary review",
    "Required GitHub checks",
)

REVIEWER_CONTRACT_ID = re.compile(r"\bRT-RC-\d{3}\b")
REVIEWER_CONTRACT_NOT_APPLICABLE = re.compile(r"(?is)^not\s+applicable\s*-\s*(.+)$")
REVIEWER_CONTRACT_EVASIVE_VALUES = {
    "n/a",
    "na",
    "none",
    "tbd",
    "todo",
    "not applicable",
}
REVIEWER_CONTRACT_PATH_PREFIXES = (
    "src/ccld_complaints/hosted_app/",
    "tests/unit/test_hosted_",
    "docs/developer/reviewer-ui-regression-contracts.md",
)

GOVERNED_SUMMARY_SECTIONS = (
    "Summary",
    "Required checks",
    "Verification behavior",
    "Boundaries",
    "Validation",
)

COMPACT_POLICY_HEADING = "Validation impact and evidence delta"
COMPACT_POLICY_REQUIRED_FIELDS = (
    "kind",
    "schema_version",
    "policy_input",
    "policy_result",
    "delta",
    "validation_newly_performed",
    "live_evidence_recollected",
)
COMPACT_POLICY_RESULT_FIELDS = (
    "decision",
    "repository_state",
    "change_inventory",
    "impact_classes",
    "validation_requirements",
    "evidence_reused",
    "evidence_recollected",
    "evidence_superseded",
    "evidence_invalidated",
    "live_obligations",
    "blockers",
    "authorized_mutations",
    "unauthorized_mutations",
    "governed_boundary_disclosures",
    "reasons",
)

BOUNDARY_PATH_PREFIXES: dict[str, tuple[str, ...]] = {
    "Schemas and migrations": ("migrations/", "schemas/", "DATA_CONTRACT.md"),
    "Ingestion and source-connector contracts": (
        "src/ccld_complaints/connectors/",
        "SOURCE_CONNECTOR_CONTRACT.md",
    ),
    "Security and privacy": (
        "SECURITY_AND_PRIVACY.md",
        "scripts/check_no_secrets.py",
        ".github/workflows/security.yml",
        "src/ccld_complaints/hosted_app/auth",
    ),
    "Production data and correction behavior": (
        "src/ccld_complaints/hosted_app/ccld_backfill.py",
        "src/ccld_complaints/hosted_app/ccld_import_reload.py",
        "src/ccld_complaints/hosted_app/persistence.py",
        "src/ccld_complaints/hosted_app/source_snapshot_lifecycle.py",
    ),
    "Deployment and infrastructure": (
        "Dockerfile",
        "docker-compose",
        "RUNBOOK.md",
        "docs/developer/qnap-",
    ),
    "Repository governance": (
        "AGENTS.md",
        "CONTRIBUTING.md",
        ".github/copilot-instructions.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/development-loop-labels.json",
        "docs/developer/codex-workflow.md",
        "docs/developer/copilot-workflow.md",
        "docs/developer/development-loop-label-taxonomy.md",
        "scripts/check_docs.py",
    ),
    "Required GitHub workflows and checks": (".github/workflows/",),
    "Tests or checks weakened to obtain passage": (
        "tests/",
        "pyproject.toml",
        "requirements-dev.txt",
        "scripts/check_independent_verification.py",
    ),
}

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_PLACEHOLDER = re.compile(r"<[^>]+>")
_UNRESOLVED_INSTRUCTION = re.compile(r"(?i)\bnot\s+run\s*-\s*<\s*reason\s*>")
_MOJIBAKE_EM_DASH = "\u00e2\u20ac\u201d"
_COMPACT_POLICY_FENCE = re.compile(r"(?ms)```json\s*\n(?P<payload>\{.*?\})\s*\n```")


def _load_evidence_policy_module() -> Any:
    """Load only the repository-fixed evaluator; caller policy paths are unsupported."""

    path = Path(__file__).with_name("evaluate_evidence_reuse_policy.py")
    spec = importlib.util.spec_from_file_location("evidence_reuse_policy", path)
    if not spec or not spec.loader:
        raise RuntimeError("cannot load fixed evidence policy evaluator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE_POLICY = _load_evidence_policy_module()
SUPPORTED_POLICY_VERSION = EVIDENCE_POLICY.POLICY_VERSION
SUPPORTED_SCHEMA_VERSION = EVIDENCE_POLICY.SCHEMA_VERSION


class PrEvidenceValidation(NamedTuple):
    """One canonical, normalized PR-evidence validation result."""

    body: str
    body_sha256: str
    changed_files: tuple[str, ...]
    template_mode: str
    violations: tuple[str, ...]


def normalize_pr_body(body: str) -> str:
    """Normalize only line endings before all PR-body parsing.

    The canonical representation converts CRLF and lone CR to LF while
    preserving Unicode, Markdown, substantive whitespace, and whether the
    input ends in a trailing newline. It intentionally does not repair
    mojibake.
    """

    return body.replace("\r\n", "\n").replace("\r", "\n")


def normalized_body_sha256(body: str) -> str:
    """Hash the canonical UTF-8, line-ending-normalized body representation."""

    return hashlib.sha256(normalize_pr_body(body).encode("utf-8")).hexdigest()


def normalize_changed_files(changed_files: Iterable[str]) -> tuple[str, ...]:
    """Return the complete changed scope as slash-normalized unique paths."""

    normalized: dict[str, None] = {}
    for changed_file in changed_files:
        path = changed_file.strip().replace("\\", "/")
        if path:
            normalized.setdefault(path, None)
    return tuple(normalized)


def find_workflow_contract_violations(repo_root: Path = Path(".")) -> list[str]:
    """Return deterministic violations that could weaken a required gate."""
    violations: list[str] = []
    for relative_path, (job_name, commands) in REQUIRED_WORKFLOWS.items():
        path = repo_root / relative_path
        if not path.exists():
            violations.append(f"missing required workflow: {relative_path}")
            continue
        content = path.read_text(encoding="utf-8")
        if not re.search(rf"(?m)^  {re.escape(job_name)}:\s*$", content):
            violations.append(f"{relative_path}: missing required job: {job_name}")
        for command in commands:
            if command not in content:
                violations.append(f"{relative_path}: missing authoritative command: {command}")
        if re.search(r"(?mi)^\s*continue-on-error:\s*true\s*(?:#.*)?$", content):
            violations.append(f"{relative_path}: continue-on-error: true is not permitted")
        if re.search(r"(?mi)^\s*paths(?:-ignore)?:\s*$", content):
            violations.append(f"{relative_path}: path filters can silently skip a required check")
        if re.search(r"(?mi)^\s*if:\s*(?:false|\$\{\{\s*false\s*\}\})\s*$", content):
            violations.append(f"{relative_path}: unconditional false workflow condition")
    return violations


def changed_governed_boundaries(changed_files: Iterable[str]) -> dict[str, list[str]]:
    """Map changed paths to documented governed boundaries.

    The map is intentionally conservative: a path may require more than one
    disclosure, and an unknown path is never represented as an approval.
    """
    changed: dict[str, list[str]] = {}
    for changed_file in normalize_changed_files(changed_files):
        normalized = changed_file
        for boundary, prefixes in BOUNDARY_PATH_PREFIXES.items():
            if any(normalized.startswith(prefix) for prefix in prefixes):
                changed.setdefault(boundary, []).append(normalized)
    return changed


def find_pr_evidence_violations(body: str, changed_files: Iterable[str]) -> list[str]:
    """Validate the PR evidence that is reliable to evaluate mechanically."""
    normalized_body = normalize_pr_body(body)
    normalized_files = normalize_changed_files(changed_files)
    without_comments = _COMMENT.sub("", normalized_body)
    violations: list[str] = []
    if _UNRESOLVED_INSTRUCTION.search(without_comments):
        violations.append(
            "unresolved PR template instruction: replace `Not run - <reason>` "
            "with completed evidence or a truthful reason"
        )
    if _MOJIBAKE_EM_DASH in normalized_body:
        violations.append(
            "invalid PR evidence text: detected mojibake em dash; preserve the "
            "intended Unicode text"
        )
    if _is_governed_summary(normalized_body):
        if _markdown_section(normalized_body, COMPACT_POLICY_HEADING):
            violations.append(
                "compact policy evidence cannot be mixed with legacy governed summary"
            )
        return violations + _find_governed_summary_violations(normalized_body, normalized_files)

    for heading in REQUIRED_TEMPLATE_SECTIONS:
        occurrences = _heading_occurrences(normalized_body, heading)
        if not occurrences:
            violations.append(f"missing PR evidence section: {heading}")
        elif len(occurrences) > 1:
            violations.append(f"duplicate PR evidence section: {heading}")

    governing_section = _markdown_section(normalized_body, "Governing issue and intended outcome")
    if not _field_value(governing_section, "Governing issue") or not re.search(
        r"(?<!\w)#\d+\b", governing_section
    ):
        violations.append("missing governing issue reference")
    if not _field_value(governing_section, "Intended outcome"):
        violations.append("missing intended outcome")

    implementation_section = _markdown_section(normalized_body, "Implementation scope")
    reviewer_contracts = _field_value(implementation_section, "Reviewer UI regression contracts")
    if not reviewer_contracts:
        violations.append("missing PR evidence field: Reviewer UI regression contracts")
    else:
        violations.extend(_reviewer_contract_violations(reviewer_contracts, normalized_files))

    acceptance_section = _markdown_section(normalized_body, "Acceptance-criteria evidence")
    if not _has_completed_table_row(acceptance_section):
        violations.append("missing completed acceptance-criteria evidence row")

    validation_section = _markdown_section(normalized_body, "Validation and failure classification")
    if not _has_completed_table_row(validation_section):
        violations.append("missing completed validation evidence row")

    documentation_section = _markdown_section(
        normalized_body, "Documentation, assumptions, and remaining risks"
    )
    for label in (
        "Documentation impact",
        "Assumptions and limitations",
        "Remaining risks or follow-up",
    ):
        if not _field_value(documentation_section, label):
            violations.append(f"missing PR evidence field: {label}")

    boundary_section = _markdown_section(normalized_body, "Governed-boundary review")
    statuses = _boundary_statuses(boundary_section)
    for boundary in REQUIRED_BOUNDARIES:
        status = statuses.get(boundary)
        if status not in {"No change", "Authorized change", "Concern - review required"}:
            violations.append(f"missing or invalid governed-boundary status: {boundary}")

    for boundary in changed_governed_boundaries(normalized_files):
        status = statuses.get(boundary)
        if status == "No change":
            violations.append(f"{boundary}: changed files require explicit disclosure")
        if (
            boundary == "Required GitHub workflows and checks"
            and status != "Concern - review required"
        ):
            violations.append(
                "Required GitHub workflows and checks: changes require Concern - review required"
            )
    compact_section = _markdown_section(normalized_body, COMPACT_POLICY_HEADING)
    if "```json" in compact_section:
        violations.extend(_compact_policy_violations(compact_section, normalized_files))
    return violations


def compact_policy_section(
    policy_input: Mapping[str, object],
    *,
    delta: str,
    validation_newly_performed: list[str],
    live_evidence_recollected: list[str],
) -> str:
    """Render a deterministic, read-only compact evidence section from fixed policy output."""

    result = EVIDENCE_POLICY.evaluate(dict(policy_input))
    envelope = {
        "kind": "compact_policy_evidence",
        "schema_version": result["schema_version"],
        "policy_input": policy_input,
        "policy_result": result,
        "delta": delta,
        "validation_newly_performed": validation_newly_performed,
        "live_evidence_recollected": live_evidence_recollected,
    }
    return (
        f"## {COMPACT_POLICY_HEADING}\n\n"
        f"- Decision: {result['decision']}\n"
        f"- Delta: {delta}\n"
        f"- Policy version: {result['policy_version']}\n"
        "- Compact evidence envelope:\n\n```json\n"
        + json.dumps(envelope, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n```\n"
    )


def _compact_policy_violations(section: str, changed_files: tuple[str, ...]) -> list[str]:
    """Independently reconstruct declared compact policy evidence from full scope."""

    violations: list[str] = []
    match = _COMPACT_POLICY_FENCE.search(section.strip())
    if match is None:
        return ["missing compact policy JSON envelope"]
    try:
        envelope = json.loads(match.group("payload"))
    except json.JSONDecodeError:
        return ["malformed compact policy JSON envelope"]
    if not isinstance(envelope, dict):
        return ["malformed compact policy JSON envelope"]
    unknown = sorted(set(envelope) - set(COMPACT_POLICY_REQUIRED_FIELDS))
    missing = [field for field in COMPACT_POLICY_REQUIRED_FIELDS if field not in envelope]
    if unknown:
        violations.append("compact policy envelope has unknown field: " + ", ".join(unknown))
    if missing:
        violations.append("compact policy envelope missing field: " + ", ".join(missing))
        return violations
    if envelope.get("kind") != "compact_policy_evidence":
        violations.append("invalid compact policy envelope kind")
    if not isinstance(envelope.get("delta"), str) or not envelope["delta"].strip():
        violations.append("compact policy delta is missing")
    for field in ("validation_newly_performed", "live_evidence_recollected"):
        if not isinstance(envelope.get(field), list):
            violations.append(f"compact policy {field} is missing")
    policy_input = envelope.get("policy_input")
    declared_result = envelope.get("policy_result")
    if not isinstance(policy_input, dict) or not isinstance(declared_result, dict):
        return violations + ["compact policy input or result is malformed"]
    inventory = policy_input.get("changed_file_inventory")
    if not isinstance(inventory, dict):
        return violations + ["compact policy changed-file inventory is missing"]
    expected_paths = list(changed_files)
    if inventory.get("paths") != expected_paths:
        violations.append(
            "compact policy changed-file inventory differs from independently supplied scope"
        )
    if inventory.get("complete") is not True:
        violations.append("compact policy changed-file inventory is incomplete")
    try:
        reconstructed = EVIDENCE_POLICY.evaluate(policy_input)
    except EVIDENCE_POLICY.EvidencePolicyError as error:
        return violations + [f"compact policy reconstruction failed: {error}"]
    if envelope.get("schema_version") != reconstructed["schema_version"]:
        violations.append("compact policy envelope schema version is invalid")
    if declared_result != reconstructed:
        violations.append("compact policy result differs from independently reconstructed result")
    visible_fields = {
        "Decision": reconstructed["decision"],
        "Delta": envelope["delta"],
        "Policy version": reconstructed["policy_version"],
    }
    for label, expected in visible_fields.items():
        if _field_value(section, label) != expected:
            violations.append(f"compact policy visible {label.lower()} differs from envelope")
    missing_result = [
        field for field in COMPACT_POLICY_RESULT_FIELDS if field not in declared_result
    ]
    if missing_result:
        violations.append("compact policy result missing field: " + ", ".join(missing_result))
    requirements = declared_result.get("validation_requirements")
    if not isinstance(requirements, dict) or "failure_classification" not in requirements:
        violations.append("compact policy failure classification is missing")
    if declared_result.get("live_obligations") == [] or not declared_result.get("live_obligations"):
        violations.append("compact policy live obligations are missing")
    if reconstructed.get("evidence_invalidated") and not declared_result.get(
        "evidence_invalidated"
    ):
        violations.append("compact policy invalidated evidence declaration is missing")
    if declared_result.get("authorized_mutations") not in ([],):
        violations.append("compact policy cannot authorize mutations")
    if "automatic_rerun" not in declared_result.get("unauthorized_mutations", []):
        violations.append("compact policy must prohibit automatic rerun")
    return violations


def _is_governed_summary(body: str) -> bool:
    return all(_markdown_section(body, heading) for heading in GOVERNED_SUMMARY_SECTIONS)


def _find_governed_summary_violations(body: str, changed_files: Iterable[str]) -> list[str]:
    """Validate the compact, governed draft-PR evidence format.

    The format intentionally remains narrower than the full template, but it
    still requires an issue reference, verification evidence, and explicit
    statements about the controls that automation cannot change.
    """
    violations: list[str] = []
    if not re.search(r"(?mi)^refs\s+#\d+\b", body):
        violations.append("missing governing issue reference")
    for heading in GOVERNED_SUMMARY_SECTIONS:
        if not _meaningful(_markdown_section(body, heading)):
            violations.append(f"missing governed-summary section: {heading}")

    verification = _markdown_section(body, "Verification behavior")
    if "requires disclosure when governed workflow boundaries change" not in verification:
        violations.append("missing governed workflow-boundary disclosure rule")

    boundaries = _markdown_section(body, "Boundaries")
    for statement in (
        "no branch-protection or ruleset change",
        "no required-check rename or removal",
        "no autonomous approval or merge",
    ):
        if statement not in boundaries:
            violations.append(f"missing governed boundary statement: {statement}")

    if ".github/workflows/" in "\n".join(changed_files) and (
        "requires disclosure when governed workflow boundaries change" not in verification
    ):
        violations.append("required workflow change lacks explicit disclosure rule")
    return violations


def validate_pr_evidence(
    repo_root: Path,
    body: str,
    changed_files: Iterable[str],
) -> PrEvidenceValidation:
    """Validate every PR-body input through one canonical production boundary."""

    normalized_body = normalize_pr_body(body)
    normalized_files = normalize_changed_files(changed_files)
    template_mode = "governed-summary" if _is_governed_summary(normalized_body) else "full-template"
    violations = tuple(
        find_workflow_contract_violations(repo_root)
        + find_pr_evidence_violations(normalized_body, normalized_files)
    )
    return PrEvidenceValidation(
        body=normalized_body,
        body_sha256=normalized_body_sha256(normalized_body),
        changed_files=normalized_files,
        template_mode=template_mode,
        violations=violations,
    )


def verification_summary(body: str, changed_files: Iterable[str]) -> list[str]:
    issue_match = re.search(
        r"(?<!\w)#(\d+)\b",
        _markdown_section(body, "Governing issue and intended outcome"),
    )
    issue = f"#{issue_match.group(1)}" if issue_match else "not identified"
    boundaries = changed_governed_boundaries(changed_files)
    boundary_summary = ", ".join(boundaries) if boundaries else "none detected"
    return [
        "Independent verification summary",
        f"- Governing issue: {issue}",
        f"- Governed boundaries requiring disclosure: {boundary_summary}",
        "- Required checks remain: validate, docs-check, fixtures, security",
        "- Result: machine-verifiable evidence is complete; human approval remains required.",
    ]


def _markdown_section(body: str, heading: str) -> str:
    occurrences = _heading_occurrences(body, heading)
    if not occurrences:
        return ""
    start = occurrences[0].end()
    next_heading = re.search(r"(?m)^##[ \t]+", body[start:])
    end = start + next_heading.start() if next_heading else len(body)
    return body[start:end]


def _heading_occurrences(body: str, heading: str) -> list[re.Match[str]]:
    return list(re.finditer(rf"(?m)^##[ \t]+{re.escape(heading)}[ \t]*$", body))


def _field_value(section: str, label: str) -> str:
    match = re.search(rf"(?m)^\s*-\s*{re.escape(label)}:\s*(.*)$", section)
    if match is None:
        return ""
    value = _COMMENT.sub("", match.group(1))
    return _PLACEHOLDER.sub("", value).strip()


def _reviewer_contract_violations(
    value: str,
    changed_files: Iterable[str],
) -> list[str]:
    normalized = " ".join(value.casefold().split())
    if normalized in REVIEWER_CONTRACT_EVASIVE_VALUES:
        return ["invalid reviewer-contract disposition: provide contracts or a reason"]
    if REVIEWER_CONTRACT_ID.search(value):
        return []
    not_applicable = REVIEWER_CONTRACT_NOT_APPLICABLE.match(value)
    if not_applicable and _meaningful(not_applicable.group(1)):
        if any(
            changed_file.replace("\\", "/").startswith(REVIEWER_CONTRACT_PATH_PREFIXES)
            for changed_file in changed_files
        ):
            return ["reviewer-contract disposition cannot be not applicable for reviewer scope"]
        return []
    return ["invalid reviewer-contract disposition: provide contracts or a reason"]


def _has_completed_table_row(section: str) -> bool:
    for line in section.splitlines():
        if not line.lstrip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or any("criterion" in cell.lower() for cell in cells[:2]):
            continue
        if all(_meaningful(cell) for cell in cells[:2]):
            return True
    return False


def _boundary_statuses(section: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] in REQUIRED_BOUNDARIES:
            statuses[cells[0]] = _COMMENT.sub("", cells[1]).strip()
    return statuses


def _meaningful(value: str) -> bool:
    cleaned = _PLACEHOLDER.sub("", _COMMENT.sub("", value)).strip()
    return bool(cleaned) and cleaned not in {"-", "None"}


def _event_body(event_path: Path) -> str:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, Mapping):
        raise ValueError("event does not contain a pull request")
    body = pull_request.get("body")
    return body if isinstance(body, str) else ""


def _pr_body(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _changed_files(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def find_verification_violations(
    repo_root: Path,
    body: str,
    changed_files: Iterable[str],
) -> list[str]:
    """Return the same workflow and PR-evidence violations used by CI."""
    return list(validate_pr_evidence(repo_root, body, changed_files).violations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--event-path", type=Path)
    parser.add_argument("--pr-body", type=Path)
    parser.add_argument("--changed-files", type=Path)
    args = parser.parse_args(argv)

    input_violations: list[str] = []
    changed_files: list[str] = []
    body = ""
    if args.event_path and args.pr_body:
        parser.error("--event-path and --pr-body are mutually exclusive")
    if args.event_path or args.pr_body or args.changed_files:
        if not args.changed_files or not (args.event_path or args.pr_body):
            parser.error("--changed-files and exactly one PR body input are required together")
        try:
            body = (
                _event_body(args.event_path)
                if args.event_path is not None
                else _pr_body(args.pr_body)
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            source = "pull-request event" if args.event_path is not None else "pull-request body"
            input_violations.append(f"cannot read {source}: {error}")
        try:
            changed_files = _changed_files(args.changed_files)
        except OSError as error:
            input_violations.append(f"cannot read changed-file list: {error}")
        validation = validate_pr_evidence(args.repo_root, body, changed_files)
        violations = input_violations + list(validation.violations)
        body = validation.body
        changed_files = list(validation.changed_files)
    else:
        violations = find_workflow_contract_violations(args.repo_root)

    if violations:
        print("Independent verification failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    if body:
        print("\n".join(verification_summary(body, changed_files)))
    else:
        print("Required workflow contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
