from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlparse

import pytest
from pytest import MonkeyPatch

from ccld_complaints.hosted_app import operator_coverage_dashboard as dashboard
from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.operator_coverage_dashboard import (
    FACILITY_ID_GROUPS,
    OPERATOR_COVERAGE_EXPORT_PATH,
    OPERATOR_COVERAGE_FACILITIES_PATH,
    OPERATOR_COVERAGE_FACILITY_IDS_PATH,
    OPERATOR_COVERAGE_JOBS_PATH,
    OPERATOR_COVERAGE_SUMMARY_PATH,
    CoveragePackageError,
    OperatorCoverageDashboardContext,
    facility_filters_from_query,
    facility_page,
    load_coverage_package,
    route_operator_coverage_response,
)
from ccld_complaints.source_to_screen_audit import (
    COVERAGE_AGGREGATE_CSV_FIELDNAMES,
    generate_coverage_package,
    load_coverage_fixture_scenario,
)
from ccld_complaints.source_to_screen_coverage import (
    COVERAGE_ARTIFACT_MEDIA_TYPES,
    COVERAGE_PRODUCER_SCHEMA_ID,
    COVERAGE_SOURCE_LAYOUT_CLASSIFICATIONS,
)

FIXTURE_ROOT = Path("tests/fixtures/hosted_operator_coverage_dashboard")
TEST_SCOPE = HostedAccessScope("test_project", "scope.fixture.operator")
OTHER_SCOPE = HostedAccessScope("test_project", "scope.fixture.other")
SCENARIOS = {
    "complete-balanced",
    "empty-verified",
    "partial-unavailable-stage",
    "failed-reconciliation",
    "version-mismatch",
    "hash-validation-failure",
    "interrupted-job-previous-accepted-active",
    "raw-733-unresolved",
    "pagination-adjacent-pages",
    "prohibited-content-rejected",
}


def test_contract_fixture_matrix_is_complete_and_adapter_states_are_truthful() -> None:
    assert {path.name for path in FIXTURE_ROOT.iterdir() if path.is_dir()} == SCENARIOS

    expected = {
        "complete-balanced": ("available", 4, 2),
        "empty-verified": ("available", 0, 0),
        "partial-unavailable-stage": ("partial", 0, 1),
        "interrupted-job-previous-accepted-active": ("available", 2, 1),
        "raw-733-unresolved": ("available", 1, 1),
        "pagination-adjacent-pages": ("available", 6, 1),
    }
    for scenario, outcome in expected.items():
        package = load_coverage_package(
            FIXTURE_ROOT / scenario, allow_legacy_fixture=True
        )
        assert (package.state, len(package.facility_rows), len(package.job_rows)) == outcome
        assert package.manifest["contract_version"] == "1.0.0"
        assert package.report["report_id"] == package.manifest["report_id"]

    failures = {
        "failed-reconciliation": "reconciliation_failed",
        "version-mismatch": "version_mismatch",
        "hash-validation-failure": "hash_failed",
        "prohibited-content-rejected": "unavailable",
    }
    for scenario, state in failures.items():
        with pytest.raises(CoveragePackageError) as captured:
            load_coverage_package(
                FIXTURE_ROOT / scenario, allow_legacy_fixture=True
            )
        assert captured.value.state == state


def test_real_issue_453_package_loads_through_stable_contract_boundary(
    tmp_path: Path,
) -> None:
    assert dashboard.CONSUMER_VERSION == "1.1.0"
    fixture = load_coverage_fixture_scenario(
        Path("tests/fixtures/source_to_screen_coverage/scenarios.json"),
        "complete-balanced",
    )
    generated = generate_coverage_package(
        fixture,
        output_dir=tmp_path,
        repo_root=Path.cwd(),
        generated_at=datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )

    package = load_coverage_package(tmp_path)

    assert package.report_id == generated.report_id
    assert package.manifest["producer_schema_id"] == COVERAGE_PRODUCER_SCHEMA_ID
    assert {
        item["name"]: item["media_type"]
        for item in package.manifest["artifacts"]
    } == COVERAGE_ARTIFACT_MEDIA_TYPES
    assert tuple(package.aggregate_csv.splitlines()[0].decode("utf-8").split(",")) == (
        COVERAGE_AGGREGATE_CSV_FIELDNAMES
    )
    assert package.facility_rows
    assert {
        row["source_layout_classification"] for row in package.facility_rows
    } <= set(COVERAGE_SOURCE_LAYOUT_CLASSIFICATIONS)
    assert package.job_rows[0]["checkpoint_identity"]

    context = OperatorCoverageDashboardContext(
        actor=_actor(),
        scope=TEST_SCOPE,
        package_dir=tmp_path,
        fixture_mode=True,
        fixture_scenario="producer-complete-balanced",
    )
    status, content_type, body = route_operator_coverage_response(
        OPERATOR_COVERAGE_SUMMARY_PATH,
        context,
    )
    markup = body.decode("utf-8")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert generated.report_id in markup
    assert "Release assessment: Passed" in markup
    assert "Reconciliation: Passed" in markup


def test_producer_first_import_order_does_not_create_a_hosted_app_cycle() -> None:
    command = (
        "import sys;sys.path.insert(0, 'src');"
        "from ccld_complaints.source_to_screen_audit import generate_coverage_package;"
        "from ccld_complaints.hosted_app.operator_coverage_dashboard import "
        "load_coverage_package;"
        "assert callable(generate_coverage_package) and callable(load_coverage_package)"
    )
    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_legacy_dashboard_scenarios_require_explicit_fixture_mode() -> None:
    with pytest.raises(CoveragePackageError) as captured:
        load_coverage_package(FIXTURE_ROOT / "complete-balanced")
    assert captured.value.state == "unavailable"


def test_adapter_validates_deterministic_report_and_facility_entry_identities(
    tmp_path: Path,
) -> None:
    report_copy = tmp_path / "report-identity"
    shutil.copytree(FIXTURE_ROOT / "complete-balanced", report_copy)
    manifest_path = report_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["report_id"] = "coverage-report-v1-" + ("f" * 64)
    manifest_path.write_text(_pretty_json(manifest), encoding="utf-8", newline="\n")

    with pytest.raises(CoveragePackageError, match="deterministic identity"):
        load_coverage_package(report_copy, allow_legacy_fixture=True)

    facility_copy = tmp_path / "facility-identity"
    shutil.copytree(FIXTURE_ROOT / "complete-balanced", facility_copy)
    facility_path = facility_copy / "operator-facility-index.jsonl"
    rows = [json.loads(line) for line in facility_path.read_text().splitlines()]
    rows[0]["facility_entry_id"] = "facility-v1-" + ("f" * 64)
    serialized = "\n".join(_canonical_json(row) for row in rows) + "\n"
    facility_path.write_text(serialized, encoding="utf-8", newline="\n")
    _refresh_manifest_artifact(facility_copy, "operator-facility-index.jsonl")

    with pytest.raises(CoveragePackageError, match="Facility entry deterministic"):
        load_coverage_package(facility_copy, allow_legacy_fixture=True)


def test_adapter_rejects_unknown_closed_enum_without_reclassifying(
    tmp_path: Path,
) -> None:
    package_copy = tmp_path / "unknown-enum"
    shutil.copytree(FIXTURE_ROOT / "complete-balanced", package_copy)
    report_path = package_copy / "coverage-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["operations"]["processing_outcome_counts"] = {"invented_success": 4}
    report_path.write_text(_pretty_json(report), encoding="utf-8", newline="\n")
    _refresh_manifest_artifact(package_copy, "coverage-report.json")

    with pytest.raises(CoveragePackageError, match="invalid closed enum"):
        load_coverage_package(package_copy, allow_legacy_fixture=True)


def test_adapter_rejects_unexpected_artifact_media_type(tmp_path: Path) -> None:
    package_copy = tmp_path / "media-type"
    shutil.copytree(FIXTURE_ROOT / "complete-balanced", package_copy)
    manifest_path = package_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["name"] == "coverage-report.json"
    )
    artifact["media_type"] = "text/plain"
    manifest_path.write_text(_pretty_json(manifest), encoding="utf-8", newline="\n")

    with pytest.raises(CoveragePackageError, match="media type"):
        load_coverage_package(package_copy, allow_legacy_fixture=True)


def test_complete_summary_separates_coverage_from_operations_and_is_safe() -> None:
    status, content_type, body = _route(
        OPERATOR_COVERAGE_SUMMARY_PATH,
        scenario="complete-balanced",
    )
    markup = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Fixture coverage data" in markup
    assert "Coverage through reviewer surfaces" in markup
    assert "Retrieval, import, artifacts, checkpoints, and jobs" in markup
    assert "does not describe whether a refresh job ran successfully" in markup
    assert "successful operation does not prove correct rendering" in markup
    assert "Producer-supplied source-to-screen stage counts" in markup
    assert "Authorization permission: audit_read" in markup
    assert '>Source coverage</a>' in markup
    assert 'aria-current="page" href="/operator/source-coverage"' in markup
    assert 'method="post"' not in markup.casefold()
    assert "source body" not in markup.casefold()
    assert "facility name" not in markup.casefold()
    assert "https://" not in markup.casefold()


def test_empty_partial_unavailable_and_contract_failure_pages_fail_truthfully() -> None:
    states = {
        "empty-verified": (200, "Verified empty coverage report"),
        "partial-unavailable-stage": (200, "Partial coverage"),
        "failed-reconciliation": (422, "Coverage report reconciliation failed"),
        "hash-validation-failure": (422, "Coverage report hash validation failed"),
        "version-mismatch": (409, "Coverage report version is not supported"),
    }
    for scenario, (expected_status, text) in states.items():
        status, _content_type, body = _route(
            OPERATOR_COVERAGE_SUMMARY_PATH,
            scenario=scenario,
        )
        markup = body.decode("utf-8")
        assert status == expected_status
        assert text in markup
        if expected_status != 200:
            assert "No package counts, Facility IDs, job rows, hashes" in markup

    status, _content_type, body = route_operator_coverage_response(
        OPERATOR_COVERAGE_SUMMARY_PATH,
        _context(None),
    )
    assert status == 503
    assert "Coverage report unavailable" in body.decode("utf-8")


def test_interrupted_job_keeps_previous_accepted_report_explicit() -> None:
    for path in (OPERATOR_COVERAGE_SUMMARY_PATH, OPERATOR_COVERAGE_JOBS_PATH):
        status, _content_type, body = _route(
            path,
            scenario="interrupted-job-previous-accepted-active",
        )
        markup = body.decode("utf-8")
        assert status == 200
        assert "Previous accepted report remains active" in markup
        assert "Current processing is not labeled successful or current" in markup
        assert "Interrupted" in markup
        if path == OPERATOR_COVERAGE_JOBS_PATH:
            assert "Checkpoint interrupted" in markup


def test_facility_filters_sort_and_filtered_empty_state_are_allowlisted() -> None:
    status, _content_type, body = _route(
        f"{OPERATOR_COVERAGE_FACILITIES_PATH}?processing_outcome=failed"
        "&sort=last_refresh_attempt_at&direction=desc&limit=25",
        scenario="complete-balanced",
    )
    markup = body.decode("utf-8")
    assert status == 200
    assert "Showing 1–1 of 1 facilities" in markup
    assert "100000004" in markup
    assert "100000001" not in markup
    assert "Processing outcome = failed" in markup

    status, _content_type, body = _route(
        f"{OPERATOR_COVERAGE_FACILITIES_PATH}?q=999999999",
        scenario="complete-balanced",
    )
    markup = body.decode("utf-8")
    assert status == 200
    assert "Showing 0–0 of 0 facilities" in markup
    assert "No facilities match the active filters" in markup
    assert "Clear filters" in markup

    for query in (
        "processing_outcome=invented",
        "sort=facility_name",
        "direction=sideways",
        "limit=101",
        "q=1&q=2",
    ):
        status, _content_type, _body = _route(
            f"{OPERATOR_COVERAGE_FACILITIES_PATH}?{query}",
            scenario="complete-balanced",
        )
        assert status == 400


def test_adjacent_keyset_pages_have_no_duplicates_or_omissions() -> None:
    package = load_coverage_package(
        FIXTURE_ROOT / "pagination-adjacent-pages", allow_legacy_fixture=True
    )
    filters = facility_filters_from_query("limit=2", package)
    pages = []
    while True:
        page = facility_page(package, filters)
        pages.append(page)
        if page.next_cursor is None:
            break
        filters = replace(filters, cursor=page.next_cursor)

    facility_entry_ids = [
        str(row["facility_entry_id"])
        for page in pages
        for row in page.rows
    ]
    assert [len(page.rows) for page in pages] == [2, 2, 2]
    assert len(facility_entry_ids) == len(set(facility_entry_ids)) == 6
    assert set(facility_entry_ids) == {
        str(row["facility_entry_id"]) for row in package.facility_rows
    }
    assert pages[0].start == 1
    assert pages[-1].end == 6

    second_filters = replace(
        facility_filters_from_query("limit=2", package),
        cursor=cast(str, pages[0].next_cursor),
    )
    second = facility_page(package, second_filters)
    previous = facility_page(
        package,
        replace(second_filters, cursor=cast(str, second.previous_cursor)),
    )
    assert previous.rows == pages[0].rows

    with pytest.raises(ValueError, match="does not match"):
        facility_page(
            package,
            replace(second_filters, processing_outcome="successful"),
        )


def test_downloads_preserve_aggregate_and_explicit_facility_id_boundaries() -> None:
    package = load_coverage_package(
        FIXTURE_ROOT / "complete-balanced", allow_legacy_fixture=True
    )
    status, content_type, body = _route(
        OPERATOR_COVERAGE_EXPORT_PATH,
        scenario="complete-balanced",
    )
    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert body == package.aggregate_csv
    assert body.startswith(
        b"report_id,dimension,category,numerator_count,denominator_count,"
    )
    assert b"facility_id" not in body
    assert b"100000001" not in body
    assert b"sha256" not in body

    for group in FACILITY_ID_GROUPS:
        status, content_type, body = _route(
            f"{OPERATOR_COVERAGE_FACILITY_IDS_PATH}?group={group}",
            scenario="complete-balanced",
        )
        assert status == 200
        assert content_type == "text/csv; charset=utf-8"
        assert body.splitlines()[0] == b"report_id,group,facility_id"
        assert b"hash" not in body.lower()
        assert b"error" not in body.lower()

    changed = _route(
        f"{OPERATOR_COVERAGE_FACILITY_IDS_PATH}?group=changed",
        scenario="complete-balanced",
    )[2].decode("utf-8")
    assert changed.count("\n") == 2
    assert changed.endswith(",changed,100000001\n")

    empty = _route(
        f"{OPERATOR_COVERAGE_FACILITY_IDS_PATH}?group=failed",
        scenario="empty-verified",
    )[2]
    assert empty == b"report_id,group,facility_id\n"

    for query in ("", "group=unknown", "group=failed&group=changed", "group=failed&x=1"):
        status, _content_type, _body = _route(
            f"{OPERATOR_COVERAGE_FACILITY_IDS_PATH}?{query}",
            scenario="complete-balanced",
        )
        assert status == 400


def test_authorization_happens_before_fixture_or_package_read(
    monkeypatch: MonkeyPatch,
) -> None:
    def fail_if_read(
        _package_dir: Path | None, *, allow_legacy_fixture: bool = False
    ) -> dashboard.CoveragePackage:
        del allow_legacy_fixture
        raise AssertionError("package must not be read before authorization")

    monkeypatch.setattr(dashboard, "load_coverage_package", fail_if_read)
    denied = [
        (None, 401),
        (_actor(account_status="disabled"), 403),
        (_actor(account_status="revoked"), 403),
        (_actor(roles=("tester_reviewer",), actor_category="tester"), 403),
        (_actor(roles=("read_only_tester",), actor_category="tester"), 403),
        (_actor(roles=("feedback_tester",), actor_category="tester"), 403),
        (_actor(scopes=(OTHER_SCOPE,)), 403),
    ]
    for actor, expected_status in denied:
        context = OperatorCoverageDashboardContext(
            actor=actor,
            scope=TEST_SCOPE,
            package_dir=FIXTURE_ROOT / "complete-balanced",
            fixture_mode=True,
        )
        status, _content_type, body = route_operator_coverage_response(
            OPERATOR_COVERAGE_SUMMARY_PATH,
            context,
        )
        assert status == expected_status
        assert b"No coverage package data was read or serialized" in body


@pytest.mark.parametrize("role", ["developer_operator", "admin"])
def test_admin_and_developer_operator_with_audit_read_and_scope_are_allowed(
    role: str,
) -> None:
    status, _content_type, body = _route(
        OPERATOR_COVERAGE_SUMMARY_PATH,
        scenario="complete-balanced",
        actor=_actor(roles=(role,)),
    )
    assert status == 200
    assert b"Authorization permission: audit_read" in body


def test_operator_routes_are_get_only_and_unknown_action_routes_do_not_exist() -> None:
    context = _context(FIXTURE_ROOT / "complete-balanced")
    for path in (
        OPERATOR_COVERAGE_SUMMARY_PATH,
        OPERATOR_COVERAGE_FACILITIES_PATH,
        OPERATOR_COVERAGE_JOBS_PATH,
        OPERATOR_COVERAGE_EXPORT_PATH,
        f"{OPERATOR_COVERAGE_FACILITY_IDS_PATH}?group=changed",
    ):
        status, _content_type, _body = route_operator_coverage_response(
            path,
            context,
            method="POST",
        )
        assert status == 405

    for suffix in ("retry", "apply", "cancel", "resume", "backfill", "actions"):
        status, _content_type, _body = route_operator_coverage_response(
            f"{OPERATOR_COVERAGE_SUMMARY_PATH}/{suffix}",
            context,
        )
        assert status == 404


def test_all_gets_leave_fixture_package_bytes_unchanged() -> None:
    scenario = "pagination-adjacent-pages"
    package_dir = FIXTURE_ROOT / scenario
    before = _tree_hashes(package_dir)
    paths = [
        OPERATOR_COVERAGE_SUMMARY_PATH,
        f"{OPERATOR_COVERAGE_FACILITIES_PATH}?limit=2&sort=facility_id",
        OPERATOR_COVERAGE_JOBS_PATH,
        OPERATOR_COVERAGE_EXPORT_PATH,
        f"{OPERATOR_COVERAGE_FACILITY_IDS_PATH}?group=changed",
    ]
    for path in paths:
        assert _route(path, scenario=scenario)[0] == 200
    assert _tree_hashes(package_dir) == before


def test_issue_490_source_selection_cadence_and_raw_733_boundary() -> None:
    package = load_coverage_package(
        FIXTURE_ROOT / "raw-733-unresolved", allow_legacy_fixture=True
    )
    snapshots = package.manifest["source_snapshots"]
    assert [item["selection_state"] for item in snapshots] == [
        "retained_existing",
        "inactive_candidate",
    ]
    assert all(item["cadence_status"] == "not_approved" for item in snapshots)
    assert package.facility_rows[0]["source_layout_classification"] == (
        "supported_unresolved_code"
    )
    fixture_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (FIXTURE_ROOT / "raw-733-unresolved").iterdir()
    )
    assert "STRTP" not in fixture_text

    status, _content_type, body = _route(
        OPERATOR_COVERAGE_SUMMARY_PATH,
        scenario="raw-733-unresolved",
    )
    markup = body.decode("utf-8")
    assert status == 200
    assert "Every statewide candidate remains inactive" in markup
    assert "No statewide completeness baseline or refresh cadence is approved" in markup
    assert "733" in markup
    assert "no approved facility-type mapping" in markup
    assert ".section-heading-row .ds-badge" in markup
    assert "white-space: normal" in markup


def test_production_style_context_never_silently_substitutes_fixture(
    monkeypatch: MonkeyPatch,
) -> None:
    for key in (
        dashboard.FIXTURE_MODE_ENV,
        dashboard.FIXTURE_PACKAGE_DIR_ENV,
        dashboard.FIXTURE_SCENARIO_ENV,
    ):
        monkeypatch.delenv(key, raising=False)

    status, _content_type, body = route_response(OPERATOR_COVERAGE_SUMMARY_PATH)
    assert status == 403
    assert b"Operator source coverage requires the Cloudflare Access provider" in body
    assert b"Fixture coverage data" not in body


def test_shared_navigation_hides_operator_link_from_reviewer_pages() -> None:
    for path in ("/reviewer", "/ccld"):
        status, _content_type, body = route_response(
            path, page_data_mode="fixture-demo"
        )
        assert status in {200, 401}
        assert b"/operator/source-coverage" not in body


def test_implementation_has_no_offset_or_direct_producer_import() -> None:
    source = Path(dashboard.__file__).read_text(encoding="utf-8")
    assert " OFFSET " not in source.upper()
    assert "source_to_screen_audit" not in source
    assert "source_to_screen_coverage" in source
    assert "sqlalchemy" not in source


def _route(
    path: str,
    *,
    scenario: str,
    actor: AuthenticatedActor | None = None,
) -> tuple[int, str, bytes]:
    package_dir = FIXTURE_ROOT / scenario
    context = _context(package_dir, scenario=scenario, actor=actor)
    return route_operator_coverage_response(path, context)


def _context(
    package_dir: Path | None,
    *,
    scenario: str | None = None,
    actor: AuthenticatedActor | None = None,
) -> OperatorCoverageDashboardContext:
    return OperatorCoverageDashboardContext(
        actor=_actor() if actor is None else actor,
        scope=TEST_SCOPE,
        package_dir=package_dir,
        fixture_mode=True,
        fixture_scenario=scenario,
    )


def _actor(
    *,
    roles: tuple[str, ...] = ("developer_operator",),
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
    actor_category: str = "operator",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="fixture-operator-subject",
        provider_issuer="fixture-managed-identity",
        display_name="Fixture operator",
        email=None,
        actor_category=cast(HostedActorCategory, actor_category),
        account_status=cast(HostedAccountStatus, account_status),
        roles=tuple(cast(HostedTesterRole, role) for role in roles),
        scopes=scopes,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _pretty_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def _refresh_manifest_artifact(package_dir: Path, artifact_name: str) -> None:
    artifact_path = package_dir / artifact_name
    artifact_bytes = artifact_path.read_bytes()
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = next(
        item for item in manifest["artifacts"] if item["name"] == artifact_name
    )
    artifact["byte_count"] = len(artifact_bytes)
    artifact["sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    manifest_path.write_text(_pretty_json(manifest), encoding="utf-8", newline="\n")


def _tree_hashes(package_dir: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package_dir.iterdir())
        if path.is_file()
    }


def _cursor_query(cursor: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(cursor).query)
