from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "developer" / "reviewer-ui-regression-contracts.md"


def test_initial_reviewer_ui_contract_registry_is_complete_and_bounded() -> None:
    content = REGISTRY.read_text(encoding="utf-8")

    assert "Status vocabulary:" in content
    assert "| Contract ID | Status | Durable outcome and protected invariant |" in content
    rows = [line for line in content.splitlines() if line.startswith("| `RT-RC-")]
    assert [row.split("|")[1].strip() for row in rows] == [
        "`RT-RC-001`",
        "`RT-RC-002`",
        "`RT-RC-003`",
        "`RT-RC-004`",
        "`RT-RC-005`",
        "`RT-RC-006`",
    ]
    for row in rows:
        assert len(row.strip().strip("|").split("|")) == 9
        assert "#" in row
        assert any(status in row for status in ("Documented", "Partially enforced", "Enforced"))
        assert "|" in row

    assert "`RT-RC-006` | Partially enforced" in content
    assert "tests/unit/reviewer_ui_contracts.py" in content
    assert "tests/unit/test_reviewer_ui_contract_routes.py" in content
    assert "assert_fixture_integrity" in content


def test_registry_requires_pr_contract_disposition_and_focused_first_validation() -> None:
    content = REGISTRY.read_text(encoding="utf-8")

    assert "affected, added, updated,\nsuperseded, or not applicable" in content
    assert "focused applicable checks" in content
    assert "final stable" in content
    assert "must not be presented as completed executable coverage" in content
    assert "## Registration and change lifecycle" in content
    assert "Retire or supersede a contract only through Issue\n#504 classification" in content
    assert "## Bounded historical sample" in content
    for issue in ("#568", "#419", "#522", "#605", "#606"):
        assert issue in content
    assert "## Deferred Issue #608 phases" in content
