import pathlib  # isort: skip


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _acceptance_script() -> str:
    script_path = REPO_ROOT / "scripts" / "verify-hosted-reviewer-acceptance.ps1"
    assert script_path.exists(), f"Missing script: {script_path}"
    return script_path.read_text(encoding="utf-8")


def _acceptance_doc() -> str:
    doc_path = REPO_ROOT / "docs" / "developer" / "hosted-reviewer-acceptance.md"
    assert doc_path.exists(), f"Missing acceptance doc: {doc_path}"
    return doc_path.read_text(encoding="utf-8")


def test_verify_script_has_required_flags_and_markers() -> None:
    script = _acceptance_script()

    # flags and parameters
    assert "-BaseUrl" in script or "Parameter(Mandatory" in script
    assert 'ValidateSet("live' in script
    assert "RunWriteChecks" in script
    assert "IncludeCapture" in script

    # checks that the script looks for preview/draft context and the ambiguous label
    assert "packet-preview-empty" in script
    assert "packet-draft-context" in script
    assert "Date range: not provided" in script

    # known positive facility sample is present
    assert "157806098" in script


def test_verify_script_checks_complete_tester_readiness_route_set() -> None:
    script = _acceptance_script()

    for route_name in (
        "home-start",
        "ccld-start",
        "facility-lookup",
        "facility-priority",
        "facility-hub",
        "record-request",
        "record-request-context",
        "reviewer",
        "reviewer-records",
        "reviewer-detail",
        "packet-preview-empty",
        "packet-preview-context",
        "packet-draft-empty",
        "packet-draft-context",
        "feedback",
        "help",
    ):
        assert route_name in script

    for route_path in (
        'Path = "/"',
        'Path = "/ccld/"',
        'Path = "/ccld/facilities"',
        'Path = "/ccld/facilities/review-priority"',
        'Path = "/ccld/facilities/detail?facility_number=$ContextFacilityNumber"',
        'Path = "/ccld/records/request"',
        'Path = "/reviewer"',
        'Path = "/reviewer/records"',
        'Path = "/reviewer/packet/preview"',
        'Path = "/reviewer/packet/draft"',
        'Path = "/feedback"',
        'Path = "/ccld/help"',
    ):
        assert route_path in script

    for marker in (
        "Start a facility complaint review",
        "Lookup or manual entry?",
        "Keyboard flow:",
        "Ready to retrieve complaint records",
        "Complaint overview",
        "Before copying or printing",
        "Review before copying or printing",
        "Do not include private material",
        "How packet preparation fits in",
    ):
        assert marker in script


def test_verify_script_reports_route_names_marker_failures_and_summary() -> None:
    script = _acceptance_script()

    assert "Missing expected marker" in script
    assert "Found forbidden marker" in script
    assert "PASS $($check.Name) -> HTTP" in script
    assert "Tester-readiness acceptance summary" in script
    assert "Routes checked" in script
    assert "-- $($f.Name):" in script


def test_verify_script_defaults_to_non_mutating_get_checks() -> None:
    script = _acceptance_script()
    lowered = script.casefold()

    assert "default route checks are non-mutating get checks" in lowered
    assert "write checks skipped" in lowered
    assert "runwritechecks was explicitly requested" in lowered
    assert "invoke-webrequest" in lowered
    assert "-method post" not in lowered
    assert "invoke-restmethod" not in lowered
    assert "run_controlled_ccld_retrieval" not in lowered
    assert "load_local_validated_ccld_records" not in lowered
    assert "github_feedback_token" not in lowered


def test_verify_script_packages_include_capture_evidence_as_local_zip() -> None:
    script = _acceptance_script()

    assert "IncludeCapture" in script
    assert "capture-hosted-ui-evidence.ps1" in script
    assert "EVIDENCE_PACKET_PATH=" in script
    assert "Evidence folder path" in script
    assert "Compress-Archive" in script
    assert "Evidence ZIP path" in script
    assert "EVIDENCE_PACKET_ZIP_PATH=" in script
    assert "packet draft intentionally hides workflow indicator" in script
    assert "packet-preview-context" in script
    assert "packet-draft-context" in script


def test_acceptance_doc_contains_commands_and_cleanup() -> None:
    doc = _acceptance_doc()

    # ports and commands
    assert "http://127.0.0.1:8003" in doc
    assert "http://127.0.0.1:8010" in doc
    assert "capture-hosted-ui-evidence.ps1" in doc
    assert "verify-hosted-reviewer-acceptance.ps1" in doc

    # cleanup command
    assert "Get-NetTCPConnection" in doc or "foreach ($p in 8000,8003,8010)" in doc

    # known sample facility/date
    assert "157806098" in doc
    assert "2026-01-01" in doc
    assert "2026-01-31" in doc


def test_acceptance_doc_covers_full_route_set_and_boundaries() -> None:
    doc = _acceptance_doc()

    for expected in (
        "tester-readiness acceptance path",
        "The acceptance verifier is non-mutating by default",
        "Route Set Checked",
        "home-start",
        "facility-lookup",
        "facility-priority",
        "facility-hub",
        "record-request-context",
        "reviewer-detail",
        "packet-preview-empty",
        "packet-draft-context",
        "feedback",
        "help",
        "Evidence folder path",
        "Evidence ZIP path",
        "local review artifact only",
        "not a legal report",
        "not a final export",
        "not a certified report",
        "not a source-completeness proof",
        "public CCLD portal remains the source of record",
        "Reviewer-created status/note cues remain separate",
        "visible keyboard-flow guidance",
        "Write checks require explicit",
        "safe local test or staging instance",
    ):
        assert expected in doc


def test_ui_evidence_doc_describes_zip_as_local_review_artifact_only() -> None:
    guide = (REPO_ROOT / "docs" / "developer" / "ui-evidence-review.md").read_text(
        encoding="utf-8"
    )

    assert "tester-readiness verifier" in guide
    assert "sibling ZIP" in guide
    assert "local review artifact only" in guide
    assert "not a product packet" in guide
    assert "not an audit export" in guide
    assert "not a legal report" in guide
    assert "not a final export" in guide
    assert "not a certified report" in guide
    assert "not production monitoring" in guide
    assert "not a source-completeness proof" in guide
