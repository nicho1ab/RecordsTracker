from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "finalize_hosted_corpus_evidence", Path("scripts/finalize_hosted_corpus_evidence.py")
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
ArtifactPathError = _MODULE.ArtifactPathError
artifact_disposition = _MODULE.artifact_disposition
create_evidence_package = _MODULE.create_evidence_package
validate_artifact_file = _MODULE.validate_artifact_file
validate_final_package = _MODULE.validate_final_package


def test_package_preserves_historical_zip_and_creates_distinct_new_package(tmp_path: Path) -> None:
    audit = _audit_json(tmp_path)
    historical = tmp_path / "historical.zip"
    with zipfile.ZipFile(historical, "w") as archive:
        archive.writestr("old-evidence.txt", "unchanged")
    original = historical.read_bytes()
    package, disposition = create_evidence_package(
        audit_json=audit, historical_package=historical, output_directory=tmp_path / "out"
    )
    assert historical.read_bytes() == original
    assert package.is_file() and package != historical
    assert disposition["disposition"] == "created"
    with zipfile.ZipFile(package) as archive:
        assert "current/audit.json" in archive.namelist()
        assert "manifest.json" in archive.namelist()


@pytest.mark.parametrize("candidate", ("<Output Path>", ".codex/visualizations/a.zip"))
def test_artifact_path_rejects_placeholder_and_internal_visualization(candidate: str) -> None:
    with pytest.raises(ArtifactPathError):
        validate_artifact_file(Path(candidate))


def test_artifact_path_rejects_missing_empty_and_malformed_zip(tmp_path: Path) -> None:
    with pytest.raises(ArtifactPathError):
        validate_artifact_file(tmp_path / "missing.json")
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ArtifactPathError):
        validate_artifact_file(empty)
    malformed = tmp_path / "bad.zip"
    malformed.write_text("not a zip", encoding="utf-8")
    with pytest.raises(ArtifactPathError):
        validate_artifact_file(malformed, require_zip=True)


def test_final_package_rejects_zip_without_current_execution_evidence(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(incomplete, "w") as archive:
        archive.writestr("manifest.json", "{}")
    with pytest.raises(ArtifactPathError):
        validate_final_package(incomplete, audit_filename="audit.json")


def test_all_artifact_dispositions_are_supported(tmp_path: Path) -> None:
    delivered = tmp_path / "delivered.zip"
    source = tmp_path / "source.zip"
    assert artifact_disposition(delivered, materially_changed=True)["disposition"] == "created"
    delivered.write_bytes(b"x")
    assert artifact_disposition(delivered, materially_changed=True)["disposition"] == "updated"
    assert (
        artifact_disposition(delivered, source=source, materially_changed=False)[
            "disposition"
        ]
        == "copied unchanged"
    )
    assert (
        artifact_disposition(delivered, source=delivered, materially_changed=False)[
            "disposition"
        ]
        == "reused unchanged"
    )


def _audit_json(tmp_path: Path) -> Path:
    path = tmp_path / "audit.json"
    path.write_text(
        json.dumps(
            {
                "contract_id": "recordstracker.hosted-corpus-verification.v1",
                "contract_version": "1.0.0",
                "executed_at": "2026-07-28T00:00:00Z",
                "application_sha": "a" * 40,
                "data_mode": {},
                "retrieval_mode": {},
                "counts": {
                    "persisted_facility_count": 2,
                    "read_model_facility_count": 2,
                    "persisted_complaint_count": 2,
                    "unique_complaint_count": 2,
                    "read_model_displayed_complaint_count": 2,
                },
                "counting_rules": {},
                "identity_rules": {},
                "duplicates": {},
                "source_linkage": {},
                "synthetic_and_fallback": {},
                "representatives": {},
                "provenance": {},
                "reviewer_state_separation": {},
                "blocking_failures": [],
                "warnings": [],
                "limitations": [],
                "artifact_disposition": {
                    "disposition": "created",
                    "content_materially_changed": True,
                },
            }
        ), encoding="utf-8"
    )
    return path
