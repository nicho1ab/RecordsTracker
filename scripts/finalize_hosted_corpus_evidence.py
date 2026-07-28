"""Build a verified local evidence package without altering historical evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ccld_complaints.hosted_app.corpus_verification import (  # noqa: E402
    validate_corpus_verification_result,
)

ALLOWED_DISPOSITIONS = frozenset({"created", "updated", "copied unchanged", "reused unchanged"})
_PLACEHOLDER_MARKERS = ("<", ">", "placeholder", "example")
_INTERNAL_VISUALIZATION_MARKER = ".codex/visualizations"


class ArtifactPathError(ValueError):
    """A supplied evidence artifact cannot be safely packaged."""


def validate_artifact_file(path: Path, *, require_zip: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    normalized = resolved.as_posix().casefold()
    if any(marker in str(path).casefold() for marker in _PLACEHOLDER_MARKERS):
        raise ArtifactPathError("Artifact path is a placeholder.")
    if _INTERNAL_VISUALIZATION_MARKER in normalized:
        raise ArtifactPathError("Internal visualization paths are not user-accessible artifacts.")
    if not resolved.is_file():
        raise ArtifactPathError("Artifact path must identify an existing file.")
    if resolved.stat().st_size == 0:
        raise ArtifactPathError("Artifact file must not be empty.")
    if require_zip:
        if not zipfile.is_zipfile(resolved):
            raise ArtifactPathError("Artifact package must be a valid ZIP file.")
        with zipfile.ZipFile(resolved) as archive:
            if archive.testzip() is not None:
                raise ArtifactPathError("Artifact package ZIP integrity check failed.")
    return resolved


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_final_package(path: Path, *, audit_filename: str) -> Path:
    package = validate_artifact_file(path, require_zip=True)
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    required = {f"current/{audit_filename}", "manifest.json"}
    if not required.issubset(names):
        raise ArtifactPathError("Final package is missing current execution evidence.")
    return package


def artifact_disposition(
    delivered: Path,
    *,
    source: Path | None = None,
    materially_changed: bool,
) -> dict[str, Any]:
    if source is None:
        disposition = "updated" if delivered.exists() else "created"
    elif delivered.resolve() == source.resolve():
        disposition = "reused unchanged"
    elif materially_changed:
        disposition = "updated"
    else:
        disposition = "copied unchanged"
    if disposition not in ALLOWED_DISPOSITIONS:
        raise AssertionError("Unsupported artifact disposition.")
    return {
        "disposition": disposition,
        "source_path": str(source) if source else None,
        "delivered_path": str(delivered),
        "content_materially_changed": materially_changed,
    }


def create_evidence_package(
    *,
    audit_json: Path,
    historical_package: Path,
    output_directory: Path,
    prior_evidence: tuple[Path, ...] = (),
    finalized_at: datetime | None = None,
) -> tuple[Path, dict[str, Any]]:
    audit = validate_artifact_file(audit_json)
    historical = validate_artifact_file(historical_package, require_zip=True)
    audit_payload = json.loads(audit.read_text(encoding="utf-8"))
    validate_corpus_verification_result(audit_payload)
    evidence = tuple(validate_artifact_file(item) for item in prior_evidence)
    timestamp = (finalized_at or datetime.now(UTC)).astimezone(UTC).strftime(
        "%Y%m%d-%H%M%SZ"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    delivered = output_directory / f"issue-419-corpus-verification-{timestamp}.zip"
    if delivered.exists():
        raise ArtifactPathError(
            "Final package path already exists; choose a new finalization timestamp."
        )
    members = [audit, *evidence]
    manifest = {
        "contract_id": "recordstracker.hosted-corpus-evidence-package.v1",
        "finalized_at": timestamp,
        "historical_package": {"filename": historical.name, "sha256": sha256_file(historical)},
        "current_execution_evidence": [
            {"filename": item.name, "sha256": sha256_file(item), "size": item.stat().st_size}
            for item in members
        ],
    }
    disposition = artifact_disposition(delivered, materially_changed=True)
    with zipfile.ZipFile(delivered, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in members:
            archive.write(item, arcname=f"current/{item.name}")
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    validate_final_package(delivered, audit_filename=audit.name)
    disposition.update(
        {
            "created_or_modified_at": datetime.fromtimestamp(
                delivered.stat().st_mtime, UTC
            ).isoformat().replace("+00:00", "Z"),
            "size": delivered.stat().st_size,
            "sha256": sha256_file(delivered),
            "action": "created distinct package with current execution evidence",
        }
    )
    return delivered, disposition


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize hosted corpus verification evidence.")
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--historical-package", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--prior-evidence", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    package, disposition = create_evidence_package(
        audit_json=args.audit_json,
        historical_package=args.historical_package,
        output_directory=args.output_directory,
        prior_evidence=tuple(args.prior_evidence),
    )
    print("PASS: evidence package finalized")
    print(f"Package: {package}")
    print(json.dumps(disposition, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
