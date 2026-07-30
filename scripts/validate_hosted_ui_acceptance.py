"""Fail-closed validation for hosted UI evidence and human owner acceptance."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "hosted-ui-acceptance-v1.schema.json"
SCHEMA_VERSION = "recordstracker.hosted-ui-acceptance.v1"
REQUIRED_VIEWPORTS = {"DESKTOP", "NARROW", "MOBILE", "ZOOM_200"}
REQUIRED_STATES = {
    "DEFAULT",
    "HOVER",
    "FOCUS",
    "ACTIVE",
    "DISABLED",
    "EMPTY",
    "LOADING",
    "UNAVAILABLE",
    "STRESS",
    "PRINT",
}
REQUIRED_DESIGN_REQUIREMENTS = {
    "RT-DS-004",
    "RT-STATE-001",
    "RT-RWD-001",
    "RT-A11Y-001",
    "RT-STRESS-001",
    "RT-PRINT-001",
}
GOVERNED_DENSITY_LIMITS = {
    "desktop-page-length": (12, "viewport-heights"),
    "narrow-page-length": (16, "viewport-heights"),
    "mobile-page-length": (24, "viewport-heights"),
    "zoom-200-page-length": (24, "viewport-heights"),
    "inline-contributing-records": (25, "records"),
}
GOVERNED_PRINT_PAGE_LIMIT = 4
VISUAL_EVIDENCE_TYPES = {"SCREENSHOT", "INTERACTION", "PRINT"}
ALLOWED_OPTIONAL_TELEMETRY_RESOURCES = {
    "static.cloudflareinsights.com beacon.min.js",
}
PRIVATE_CONTENT = re.compile(
    r"(?i)(?:github_pat_|ghp_|authorization\s*:\s*\S+|cookie\s*:\s*\S+|"
    r"[a-z]:[\\/]|https?://|\bqnap\b)"
)


@dataclass(frozen=True)
class AcceptanceResult:
    """Stable validator result for one acceptance record."""

    gates: dict[str, str]
    overall: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "gates": self.gates,
            "overall": self.overall,
            "errors": list(self.errors),
        }


def _pointer(error: Any) -> str:
    return "/".join(str(part) for part in error.absolute_path) or "root"


def _schema_errors(record: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    return sorted(
        (f"schema:{_pointer(error)}: {error.message}" for error in validator.iter_errors(record)),
        key=str,
    )


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["id"]) for row in rows]


def _missing_or_duplicate_ids(
    rows: list[dict[str, Any]], required: set[str], location: str
) -> list[str]:
    observed = _ids(rows)
    errors = []
    missing = sorted(required - set(observed))
    duplicates = sorted({identifier for identifier in observed if observed.count(identifier) > 1})
    if missing:
        errors.append(f"{location}: missing required entries: {', '.join(missing)}")
    if duplicates:
        errors.append(f"{location}: duplicate entries: {', '.join(duplicates)}")
    return errors


def _structural_errors(record: dict[str, Any]) -> list[str]:
    structural = record["structural"]
    counts = record["source_packet"]["artifact_counts"]
    errors = []
    if not structural["integrity_verified"]:
        errors.append("structural: packet integrity was not verified")
    if structural["missing_artifacts"]:
        errors.append("structural: required artifacts are missing")
    if len(set(counts.values())) != 1:
        errors.append(
            "structural: artifact counts do not reconcile "
            f"(filesystem={counts['filesystem']}, zip={counts['zip']}, "
            f"manifest={counts['manifest']}, reported={counts['reported']})"
        )
    return errors


def _functional_errors(record: dict[str, Any]) -> list[str]:
    functional = record["functional"]
    errors = []
    for field in ("assertion_failures", "route_failures"):
        if functional[field]:
            errors.append(f"functional: {field} must be zero")
    inventories = (
        ("console event", "observed_console_events", "console_event_classifications"),
        ("network failure", "observed_network_failures", "network_failure_classifications"),
    )
    for label, observed_field, classification_field in inventories:
        rows = functional[classification_field]
        classified_occurrences = sum(row["occurrences"] for row in rows)
        if classified_occurrences != functional[observed_field]:
            errors.append(
                f"functional: {label} classification occurrences "
                f"{classified_occurrences} do not match observed {functional[observed_field]}"
            )
        if any(row["classification"] == "UNCLASSIFIED" for row in rows):
            errors.append(f"functional: every {label} must be explicitly classified")
        for row in rows:
            if (
                row["classification"] == "EXPECTED_OPTIONAL_TELEMETRY"
                and (
                    row["origin_scope"] != "ALLOWLISTED_OPTIONAL_TELEMETRY"
                    or row["resource"] not in ALLOWED_OPTIONAL_TELEMETRY_RESOURCES
                )
            ):
                errors.append(
                    f"functional/{classification_field}/{row['id']}: optional telemetry "
                    "must use the exact allowlisted origin and resource classification"
                )
            if row["origin_scope"] == "UNKNOWN":
                errors.append(
                    f"functional/{classification_field}/{row['id']}: origin scope is unknown"
                )
    return errors


def _state_errors(record: dict[str, Any]) -> list[str]:
    rows = record["visual"]["state_matrix"]
    errors = _missing_or_duplicate_ids(rows, REQUIRED_STATES, "visual/state_matrix")
    for row in rows:
        identifier = row["id"]
        classification = row["classification"]
        if classification in {"REGRESSION", "MISSING"}:
            errors.append(f"visual/state_matrix/{identifier}: {classification.lower()}")
        if classification == "PASS" and not row["evidence"]:
            errors.append(f"visual/state_matrix/{identifier}: PASS requires evidence")
        if classification == "NOT_APPLICABLE" and not row["rationale"].strip():
            errors.append(
                f"visual/state_matrix/{identifier}: NOT_APPLICABLE requires a rationale"
            )
    return errors


def _design_errors(record: dict[str, Any]) -> list[str]:
    rows = record["visual"]["design_requirements"]
    errors = _missing_or_duplicate_ids(
        rows, REQUIRED_DESIGN_REQUIREMENTS, "visual/design_requirements"
    )
    for row in rows:
        identifier = row["id"]
        classification = row["classification"]
        if classification == "REGRESSION":
            errors.append(f"visual/design_requirements/{identifier}: regression")
        if classification == "PASS" and not row["evidence"]:
            errors.append(f"visual/design_requirements/{identifier}: PASS requires evidence")
        if classification == "VARIANCE":
            approval = row["variance_approval"]
            if not approval:
                errors.append(
                    f"visual/design_requirements/{identifier}: variance requires human approval"
                )
        elif row["variance_approval"] is not None:
            errors.append(
                f"visual/design_requirements/{identifier}: approval is only valid for VARIANCE"
            )
        if classification == "NOT_APPLICABLE" and not row["rationale"].strip():
            errors.append(
                f"visual/design_requirements/{identifier}: NOT_APPLICABLE requires a rationale"
            )
    return errors


def _visual_errors(record: dict[str, Any]) -> list[str]:
    visual = record["visual"]
    errors = _missing_or_duplicate_ids(
        visual["viewports"], REQUIRED_VIEWPORTS, "visual/viewports"
    )
    errors.extend(_state_errors(record))
    errors.extend(_design_errors(record))

    for assertion in visual["visual_assertions"]:
        if not set(assertion["evidence_types"]) & VISUAL_EVIDENCE_TYPES:
            errors.append(
                f"visual/visual_assertions/{assertion['id']}: DOM or text alone "
                "cannot prove a visual requirement"
            )
    errors.extend(
        _missing_or_duplicate_ids(
            visual["density_checks"],
            set(GOVERNED_DENSITY_LIMITS),
            "visual/density_checks",
        )
    )
    for check in visual["density_checks"]:
        governed_limit = GOVERNED_DENSITY_LIMITS.get(check["id"])
        if governed_limit and (
            check["maximum"] != governed_limit[0] or check["unit"] != governed_limit[1]
        ):
            errors.append(
                f"visual/density_checks/{check['id']}: maximum and unit must remain "
                f"{governed_limit[0]} {governed_limit[1]}"
            )
        if check["measured"] > check["maximum"]:
            errors.append(
                f"visual/density_checks/{check['id']}: measured {check['measured']} "
                f"exceeds maximum {check['maximum']} {check['unit']}"
            )
    for check in visual["print_checks"]:
        if check["maximum_pages"] != GOVERNED_PRINT_PAGE_LIMIT:
            errors.append(
                f"visual/print_checks/{check['id']}: maximum_pages must remain "
                f"{GOVERNED_PRINT_PAGE_LIMIT}"
            )
        if check["page_count"] > check["maximum_pages"]:
            errors.append(
                f"visual/print_checks/{check['id']}: {check['page_count']} pages "
                f"exceeds maximum {check['maximum_pages']}"
            )
        if not check["interactive_controls_hidden"]:
            errors.append(
                f"visual/print_checks/{check['id']}: interactive-only controls remain visible"
            )

    review = visual["independent_review"]
    if review["decision"] != "PASS":
        errors.append("visual/independent_review: a human PASS decision is required")
    required_review_evidence = {
        viewport["screenshot"] for viewport in visual["viewports"]
    } | {check["evidence"] for check in visual["print_checks"]}
    missing_review = sorted(required_review_evidence - set(review["reviewed_evidence"]))
    if missing_review:
        errors.append(
            "visual/independent_review: unreviewed screenshot or print evidence: "
            + ", ".join(missing_review)
        )
    return errors


def _owner_errors(record: dict[str, Any]) -> list[str]:
    owner = record["owner_acceptance"]
    review = record["visual"]["independent_review"]
    errors = []
    if owner["decision"] != "PASS":
        errors.append("owner_acceptance: an explicit human PASS decision is required")
    if owner["reviewed_visual_record"] != review["artifact"]:
        errors.append("owner_acceptance: decision does not reference the independent review")
    if owner["artifact"] == review["artifact"]:
        errors.append("owner_acceptance: owner decision must be a separate artifact")
    return errors


def _privacy_errors(record: dict[str, Any]) -> list[str]:
    if PRIVATE_CONTENT.search(json.dumps(record, sort_keys=True)):
        return ["record: contains a credential, URL, private-host marker, or absolute path"]
    return []


def validate_acceptance(
    record: dict[str, Any], schema: dict[str, Any] | None = None
) -> AcceptanceResult:
    """Validate one loaded acceptance record without network or mutation."""

    active_schema = schema or json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = _schema_errors(record, active_schema)
    if errors:
        gates = {
            "STRUCTURAL": "FAIL",
            "FUNCTIONAL": "FAIL",
            "VISUAL": "FAIL",
            "OWNER_ACCEPTANCE": "FAIL",
        }
        return AcceptanceResult(gates, "NOT_ACCEPTED", tuple(errors))

    errors_by_gate = {
        "STRUCTURAL": _structural_errors(record),
        "FUNCTIONAL": _functional_errors(record),
        "VISUAL": _visual_errors(record),
        "OWNER_ACCEPTANCE": _owner_errors(record),
    }
    errors = [error for gate_errors in errors_by_gate.values() for error in gate_errors]
    errors.extend(_privacy_errors(record))
    if errors and not errors_by_gate["STRUCTURAL"]:
        if any(error.startswith("record:") for error in errors):
            errors_by_gate["STRUCTURAL"].append("structural: record privacy check failed")

    gates = {
        gate: "PASS" if not gate_errors else "FAIL"
        for gate, gate_errors in errors_by_gate.items()
    }
    for gate, computed in gates.items():
        claimed = record["gate_claims"][gate]
        if claimed != computed:
            errors.append(f"claims/{gate}: claimed {claimed}, computed {computed}")

    overall = "PASS" if all(status == "PASS" for status in gates.values()) else "NOT_ACCEPTED"
    if record["overall_claim"] != overall:
        errors.append(
            f"claims/overall: claimed {record['overall_claim']}, computed {overall}"
        )
    return AcceptanceResult(gates, overall, tuple(sorted(set(errors))))


def _load_record(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("acceptance record must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="Acceptance record JSON")
    args = parser.parse_args()
    result = validate_acceptance(_load_record(args.record))
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
