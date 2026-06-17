import pathlib


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_verify_script_has_required_flags_and_markers():
    script_path = REPO_ROOT / "scripts" / "verify-hosted-reviewer-acceptance.ps1"
    assert script_path.exists(), f"Missing script: {script_path}"
    script = script_path.read_text(encoding="utf-8")

    # flags and parameters
    assert "-BaseUrl" in script or "Parameter(Mandatory" in script
    assert "ValidateSet(\"live\", \"fixture\", \"scaffold\")" in script or "ValidateSet(\"live\",\"fixture\",\"scaffold\")" in script
    assert "RunWriteChecks" in script
    assert "IncludeCapture" in script

    # checks that the script looks for preview/draft context and the ambiguous label
    assert "PacketPreviewEmpty" in script
    assert "PacketDraftContext" in script
    assert "Date range: not provided" in script

    # known positive facility sample is present
    assert "157806098" in script


def test_acceptance_doc_contains_commands_and_cleanup():
    doc_path = REPO_ROOT / "docs" / "developer" / "hosted-reviewer-acceptance.md"
    assert doc_path.exists(), f"Missing acceptance doc: {doc_path}"
    doc = doc_path.read_text(encoding="utf-8")

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
