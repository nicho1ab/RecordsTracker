"""Validate the canonical offline delivery-automation governance registry."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / ".github" / "delivery-automation-registry.json"
SCHEMA_PATH = ROOT / "schemas" / "delivery-automation-registry-v1.schema.json"
IDENTIFIER = re.compile(r"^DA-(\d{3})$")
ISSUE_REFERENCE = re.compile(r"^#[1-9]\d*$")
PRIVATE_CONTENT = re.compile(
    r"(?i)(?:github_pat_|ghp_|authorization\s*:\s*\S+|cookie\s*:\s*\S+|"
    r"[a-z]:[\\/]|https?://|\b(?:qnap|cloudflare)\b)"
)


def _pointer(error: Any) -> str:
    return "/".join(str(part) for part in error.absolute_path) or "root"


def _record_number(record: dict[str, Any]) -> int | None:
    value = record.get("id")
    if not isinstance(value, str):
        return None
    match = IDENTIFIER.fullmatch(value)
    return int(match.group(1)) if match else None


def _repository_path(reference: str) -> str:
    return reference.split("#", maxsplit=1)[0]


def _bounded_repository_path(root: Path, reference: str) -> Path | None:
    path = _repository_path(reference)
    if not path or Path(path).is_absolute():
        return None
    resolved_root = root.resolve()
    candidate = (resolved_root / path).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return candidate


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path.name}")
    return payload


def _schema_errors(registry: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return sorted(
        (f"schema:{_pointer(error)}: {error.message}" for error in validator.iter_errors(registry)),
        key=str,
    )


def _validate_reference(reference: dict[str, Any], root: Path, location: str) -> list[str]:
    kind = reference.get("kind")
    value = reference.get("reference")
    if not isinstance(value, str):
        return []
    if kind in {"issue", "pull_request"}:
        if not ISSUE_REFERENCE.fullmatch(value):
            return [f"{location}: invalid {kind} reference"]
        return []
    if kind == "repository_path":
        path = _bounded_repository_path(root, value)
        if path is None or not path.is_file():
            return [f"{location}: invalid repository path reference"]
    return []


def _validate_paths(values: Any, root: Path, location: str) -> list[str]:
    if not isinstance(values, list):
        return []
    errors = []
    for value in values:
        if not isinstance(value, str):
            continue
        path = _bounded_repository_path(root, value)
        if path is None or not path.is_file():
            errors.append(f"{location}: invalid repository path")
    return errors


def _gap_numbers(gaps: Any) -> set[int]:
    numbers: set[int] = set()
    if not isinstance(gaps, list):
        return numbers
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        start = gap.get("start_id")
        end = gap.get("end_id")
        if isinstance(start, int) and isinstance(end, int) and start <= end:
            numbers.update(range(start, end + 1))
    return numbers


def _validate_temporary_exception(record: dict[str, Any], today: date) -> list[str]:
    exception = record.get("temporary_exception")
    if not isinstance(exception, dict) or exception.get("status") != "active":
        return []
    identifier = record.get("id", "record")
    errors = []
    if not exception.get("owner"):
        errors.append(f"{identifier}: active temporary exception requires an owner")
    if not exception.get("expiration_date") and not exception.get("mandatory_review_trigger"):
        errors.append(
            f"{identifier}: active temporary exception requires an expiration date "
            "or review trigger"
        )
    expiration = exception.get("expiration_date")
    if isinstance(expiration, str):
        try:
            if date.fromisoformat(expiration) < today:
                errors.append(f"{identifier}: active temporary exception is expired")
        except ValueError:
            pass
    if exception.get("relaxes_required_check") or exception.get("relaxes_authorization_boundary"):
        errors.append(
            f"{identifier}: temporary exception cannot relax a required check "
            "or authorization boundary"
        )
    return errors


def _validate_cross_record_constraints(
    registry: dict[str, Any], root: Path, today: date
) -> list[str]:
    records = registry.get("records")
    if not isinstance(records, list):
        return []

    errors: list[str] = []
    identifiers: list[int] = []
    known_ids: set[str] = set()
    normalized_patterns: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        location = f"records[{index}]"
        identifier = record.get("id", location)
        number = _record_number(record)
        if number is not None:
            identifiers.append(number)
            known_ids.add(str(identifier))
            if number <= 28:
                errors.append(
                    f"{identifier}: DA-001 through DA-028 must remain unavailable historical gaps"
                )
        pattern = record.get("failure_pattern")
        if isinstance(pattern, str):
            normalized = " ".join(pattern.casefold().split())
            if normalized in normalized_patterns:
                errors.append(f"{identifier}: duplicate semantic failure pattern")
            normalized_patterns.add(normalized)
        for reference_index, reference in enumerate(record.get("evidence_references", [])):
            if isinstance(reference, dict):
                errors.extend(
                    _validate_reference(
                        reference, root, f"{identifier}: evidence_references[{reference_index}]"
                    )
                )
        errors.extend(
            _validate_paths(
                record.get("regression_coverage"), root, f"{identifier}: regression_coverage"
            )
        )
        errors.extend(
            _validate_paths(
                record.get("documentation_impact"), root, f"{identifier}: documentation_impact"
            )
        )
        owner = record.get("owner_issue")
        evidence_issues = {
            item.get("reference")
            for item in record.get("evidence_references", [])
            if isinstance(item, dict) and item.get("kind") == "issue"
        }
        related_issues = set(record.get("related_issues", []))
        if isinstance(owner, str) and owner not in evidence_issues | related_issues:
            errors.append(
                f"{identifier}: owner issue must be represented in evidence or related issues"
            )
        if record.get("prevention_state") == "prevention_complete":
            if not record.get("regression_coverage"):
                errors.append(
                    f"{identifier}: prevention-complete record requires regression coverage"
                )
            if not record.get("documentation_impact"):
                errors.append(
                    f"{identifier}: prevention-complete record requires documentation impact"
                )
        if identifier == "DA-031" and (
            record.get("lifecycle_status") == "prevented"
            or record.get("prevention_state") == "prevention_complete"
        ):
            errors.append(
                "DA-031: prevention cannot be complete without concrete prevention evidence"
            )
        expected_pr = {"DA-029": "#618", "DA-030": "#619"}.get(identifier)
        if expected_pr and record.get("merged_prevention_prs") != [expected_pr]:
            errors.append(f"{identifier}: expected merged prevention PR {expected_pr}")
        errors.extend(_validate_temporary_exception(record, today))

        retirement = record.get("retirement")
        if isinstance(retirement, dict):
            retired = retirement.get("status") == "retired"
            if record.get("lifecycle_status") == "retired":
                if not retired or not retirement.get("rationale"):
                    errors.append(f"{identifier}: retired record requires a retirement rationale")
            elif retired:
                errors.append(f"{identifier}: active and retired state is contradictory")
        classifications = set(record.get("governance_change_classifications", []))
        if "obsolete_control_removal" in classifications:
            supersession = record.get("supersession", {})
            has_replacement = isinstance(supersession, dict) and bool(
                supersession.get("superseded_by")
            )
            has_rationale = isinstance(retirement, dict) and bool(retirement.get("rationale"))
            if not has_replacement and not has_rationale:
                errors.append(
                    f"{identifier}: obsolete-control removal requires a replacement or rationale"
                )

    if identifiers != sorted(identifiers):
        errors.append("records: DA identifiers must be numerically ascending")
    if len(identifiers) != len(set(identifiers)):
        errors.append("records: duplicate DA identifier")
    highest = registry.get("highest_assigned_id")
    if identifiers and highest != max(identifiers):
        errors.append("highest_assigned_id: must equal the highest record identifier")
    declared_gaps = _gap_numbers(registry.get("historical_gaps"))
    if not set(range(1, 29)).issubset(declared_gaps):
        errors.append("historical_gaps: DA-001 through DA-028 must be explicitly unavailable")
    if identifiers:
        missing = set(range(1, max(identifiers) + 1)) - set(identifiers)
        undeclared = sorted(missing - declared_gaps)
        if undeclared:
            rendered = ", ".join(f"DA-{value:03d}" for value in undeclared)
            errors.append(f"records: undeclared identifier gaps: {rendered}")

    for record in records:
        if not isinstance(record, dict):
            continue
        identifier = str(record.get("id", "record"))
        supersession = record.get("supersession")
        if not isinstance(supersession, dict):
            continue
        for relation in ("supersedes", "superseded_by"):
            for reference in supersession.get(relation, []):
                if reference == identifier:
                    errors.append(f"{identifier}: direct self-supersession is not allowed")
                elif reference not in known_ids:
                    errors.append(
                        f"{identifier}: supersession references unknown record {reference}"
                    )
    return errors


def _validate_privacy(registry: dict[str, Any]) -> list[str]:
    rendered = json.dumps(registry, sort_keys=True)
    if PRIVATE_CONTENT.search(rendered):
        return ["registry: contains a credential, absolute path, URL, or private-host marker"]
    return []


def validate_registry(
    registry: dict[str, Any], schema: dict[str, Any], *, root: Path, today: date | None = None
) -> list[str]:
    """Return stable, offline validation diagnostics for one loaded registry."""

    current_day = today or date.today()
    errors = _schema_errors(registry, schema)
    errors.extend(_validate_cross_record_constraints(registry, root, current_day))
    errors.extend(_validate_privacy(registry))
    return sorted(set(errors))


def validate_canonical_registry() -> list[str]:
    """Validate only the repository-bounded canonical registry and schema."""

    return validate_registry(
        _load_json(REGISTRY_PATH),
        _load_json(SCHEMA_PATH),
        root=ROOT,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = validate_canonical_registry()
    if errors:
        print("\n".join(errors))
        return 1
    print("Delivery-automation registry validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
