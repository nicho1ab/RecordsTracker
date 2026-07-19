from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from playwright.sync_api import Browser, sync_playwright
from sqlalchemy import create_engine, event, func, select

LOCAL_NOW = datetime(2026, 7, 19, 20, 0, 0, tzinfo=UTC)
OPERATOR_EMAIL = "operator@example.invalid"
TESTER_EMAIL = "ordinary-tester@example.invalid"
TEAM_DOMAIN = "operator-acceptance.cloudflareaccess.invalid"
AUDIENCE = "operator-acceptance-audience"
KEY_ID = "operator-acceptance-ephemeral-key"
GROUPS = (
    "changed",
    "unchanged",
    "warning",
    "failed",
    "missing_artifact",
    "retry_eligible",
)
PROHIBITED_OUTPUT_MARKERS = (
    "a. miriam jamison",
    "32-cr-20220407124448",
    "facility clients are being mistreated",
    "https://www.ccld",
    "tests/fixtures/ccld/raw",
    "provider_subject",
    "provider_issuer",
    "cf-access-jwt-assertion",
    "authorization: bearer",
    "set-cookie",
    "traceback (most recent call last)",
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    sys.path.insert(0, str(repo_root / "src"))
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    packet = output_root / f"{timestamp}-hosted-operator-coverage-acceptance"
    for name in ("screenshots", "html", "downloads", "diagnostics"):
        (packet / name).mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    runtime_metadata: Mapping[str, Any] | None = None
    if args.mode == "LocalProductionAuth":
        runtime_metadata, operator_headers, tester_headers = _local_runtime_setup(
            repo_root, packet
        )
        base_url = f"http://127.0.0.1:{args.port}"
        _require_unused_loopback_port(args.port)
        with _local_server(
            args.port,
            packet / "runtime-current",
            operator_headers=operator_headers,
            tester_headers=tester_headers,
        ) as auth:
            results.extend(
                _capture_route_set(
                    packet,
                    base_url,
                    operator_headers=auth["operator_headers"],
                    tester_headers=auth["tester_headers"],
                    local_mode=True,
                )
            )
        with _local_server(
            args.port,
            packet / "missing-runtime-package",
            operator_headers=operator_headers,
            tester_headers=tester_headers,
        ) as auth:
            results.append(
                _capture_page(
                    packet,
                    base_url,
                    {
                        "label": "17-unavailable-package",
                        "path": "/operator/source-coverage",
                        "width": 720,
                        "height": 900,
                        "expected_status": 503,
                        "contains": ("Coverage report unavailable",),
                    },
                    auth["operator_headers"],
                )
            )
    else:
        base_url = _validated_base_url(args.base_url)
        provider = os.environ.get(
            "CCLD_OPERATOR_COVERAGE_ACCEPTANCE_HEADER_PROVIDER_COMMAND", ""
        ).strip()
        if not provider:
            raise RuntimeError(
                "Hosted acceptance is blocked: an already-authorized header provider "
                "is required, and browser cookie/profile fallback is forbidden."
            )
        operator_headers = _provider_headers(provider, "operator")
        tester_headers = _provider_headers(provider, "tester")
        results.extend(
            _capture_route_set(
                packet,
                base_url,
                operator_headers=operator_headers,
                tester_headers=tester_headers,
                local_mode=False,
            )
        )

    _write_result_csvs(packet, results)
    failed = sum(
        1
        for result in results
        for assertion in result["assertions"]
        if not assertion["passed"]
    )
    manifest = {
        "evidence_kind": "issues-453-477-hosted-runtime-read-only-acceptance",
        "mode": args.mode,
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "branch": args.branch,
        "commit_sha": args.commit_sha,
        "transport": "loopback" if args.mode == "LocalProductionAuth" else "hosted-configured",
        "get_only_capture": True,
        "manual_review_required": False,
        "authentication_material_persisted": False,
        "browser_cookie_or_profile_accessed": False,
        "captures": len(results),
        "assertions_failed": failed,
        "runtime_reconciliation": runtime_metadata,
        "routes": sorted({str(result["path"]) for result in results}),
        "facility_id_groups": list(GROUPS),
        "mutation_features": [
            "retry deferred",
            "apply deferred",
            "cancel deferred",
            "resume deferred",
            "backfill execution deferred",
            "database writes absent from runtime adapter",
        ],
    }
    payload_files = tuple(path for path in packet.rglob("*") if path.is_file())
    manifest["payload_file_count"] = len(payload_files)
    manifest["payload_byte_count"] = sum(path.stat().st_size for path in payload_files)
    (packet / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    zip_path = packet.with_suffix(".zip")
    _write_zip(packet, zip_path)
    zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    file_count = sum(path.is_file() for path in packet.rglob("*"))
    with zipfile.ZipFile(zip_path) as archive:
        entry_count = len(archive.infolist())
    print(f"EVIDENCE_PACKET_PATH={packet}")
    print(f"EVIDENCE_ZIP_PATH={zip_path}")
    print(f"EVIDENCE_ZIP_SHA256={zip_sha}")
    print(f"EVIDENCE_FILE_COUNT={file_count}")
    print(f"EVIDENCE_ZIP_ENTRY_COUNT={entry_count}")
    print(f"EVIDENCE_ASSERTIONS={'PASS' if failed == 0 else 'FAIL'}")
    return 0 if failed == 0 else 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("LocalProductionAuth", "Hosted"), required=True
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--base-url", default="")
    return parser


def _local_runtime_setup(
    repo_root: Path, packet: Path
) -> tuple[Mapping[str, Any], Mapping[str, str], Mapping[str, str]]:
    from ccld_complaints import source_to_screen_audit as audit
    from ccld_complaints.hosted_app.seeded_import import (
        hosted_import_batches,
        hosted_seeded_import_metadata,
        hosted_source_derived_records,
        import_seeded_corpus_artifact,
        load_seeded_corpus_artifact,
    )
    from ccld_complaints.source_to_screen_coverage import (
        load_validated_coverage_package,
    )

    statements: list[str] = []
    with tempfile.TemporaryDirectory(prefix="operator-coverage-acceptance-") as temp:
        engine = create_engine(f"sqlite:///{Path(temp) / 'runtime.sqlite'}")
        with engine.connect() as connection:
            hosted_seeded_import_metadata.create_all(connection)
            import_seeded_corpus_artifact(
                connection,
                load_seeded_corpus_artifact(
                    repo_root
                    / "tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json"
                ),
            )
            for offset in range(1, 6):
                number = str(157806098 + offset)
                connection.execute(
                    hosted_source_derived_records.insert().values(
                        source_record_key=f"facility:ccld:facility:{number}",
                        entity_type="facility",
                        stable_source_id=f"ccld:facility:{number}",
                        import_batch_id="seeded-ccld-fixture-2026-06-13",
                        source_document_id=f"ccld:document:{number}:acceptance",
                        facility_id=f"ccld:facility:{number}",
                        source_url=f"https://example.invalid/{number}",
                        raw_sha256=f"{offset}" * 64,
                        raw_path=None,
                        connector_name="acceptance_fixture",
                        connector_version="1.0.0",
                        retrieved_at="2026-07-19T19:00:00+00:00",
                        original_values={
                            "facility_id": f"ccld:facility:{number}",
                            "external_facility_number": number,
                        },
                        source_traceability={},
                    )
                )
            connection.commit()

            def capture_statement(
                _connection: Any,
                _cursor: Any,
                statement: str,
                _parameters: Any,
                _context: Any,
                _executemany: bool,
            ) -> None:
                statements.append(statement)

            event.listen(engine, "before_cursor_execute", capture_statement)
            structural = audit.run_audit(
                mode="runtime",
                output_dir=packet / "runtime-audit",
                repo_root=repo_root,
                runtime_connection=connection,
                generated_at=LOCAL_NOW,
            )
            package = audit.publish_runtime_coverage_package(
                connection,
                structural,
                output_dir=packet / "runtime-current",
                repo_root=repo_root,
                generated_at=LOCAL_NOW,
            )
            event.remove(engine, "before_cursor_execute", capture_statement)
            database_facilities = int(
                connection.scalar(
                    select(func.count())
                    .select_from(hosted_source_derived_records)
                    .where(hosted_source_derived_records.c.entity_type == "facility")
                )
                or 0
            )
            database_batches = int(
                connection.scalar(select(func.count()).select_from(hosted_import_batches))
                or 0
            )
        engine.dispose()

    validated = load_validated_coverage_package(packet / "runtime-current")
    select_only = all(
        statement.lstrip().upper().startswith(("SELECT", "WITH", "PRAGMA"))
        for statement in statements
    )
    reconciliation = {
        "report_id": package.report_id,
        "package_state": validated.state,
        "database_facility_total": database_facilities,
        "package_facility_index_total": len(validated.facility_rows),
        "report_existing_facility_total": validated.report["operations"][
            "existing_facility_total"
        ],
        "database_import_batch_total": database_batches,
        "runtime_sql_select_only": select_only,
        "runtime_database_writes": False,
        "reconciled": database_facilities
        == len(validated.facility_rows)
        == validated.report["operations"]["existing_facility_total"],
    }
    (packet / "diagnostics/runtime-reconciliation.json").write_text(
        json.dumps(reconciliation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if not select_only or not reconciliation["reconciled"]:
        raise RuntimeError("Local runtime package did not reconcile through SELECT-only reads.")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    operator_token = _token(private_key, OPERATOR_EMAIL)
    tester_token = _token(private_key, TESTER_EMAIL)
    _LOCAL_AUTH["private_key"] = private_key
    return (
        reconciliation,
        {"Cf-Access-Jwt-Assertion": operator_token},
        {"Cf-Access-Jwt-Assertion": tester_token},
    )


_LOCAL_AUTH: dict[str, Any] = {}


def _token(private_key: rsa.RSAPrivateKey, email: str) -> str:
    header = {"alg": "RS256", "kid": KEY_ID, "typ": "JWT"}
    claims = {
        "iss": f"https://{TEAM_DOMAIN}",
        "aud": AUDIENCE,
        "exp": int((LOCAL_NOW + timedelta(minutes=10)).timestamp()),
        "nbf": int((LOCAL_NOW - timedelta(minutes=1)).timestamp()),
        "email": email,
    }
    signing = f"{_b64_json(header)}.{_b64_json(claims)}".encode("ascii")
    signature = private_key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing.decode('ascii')}.{_b64(signature)}"


def _b64_json(value: Mapping[str, object]) -> str:
    return _b64(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_uint(value: int) -> str:
    return _b64(value.to_bytes((value.bit_length() + 7) // 8, "big"))


@contextmanager
def _local_server(
    port: int,
    package_dir: Path,
    *,
    operator_headers: Mapping[str, str],
    tester_headers: Mapping[str, str],
) -> Iterator[Mapping[str, Mapping[str, str]]]:
    from ccld_complaints.hosted_app import app
    from ccld_complaints.hosted_app.auth import load_hosted_auth_runtime_config

    private_key = cast(rsa.RSAPrivateKey, _LOCAL_AUTH["private_key"])
    numbers = private_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": KEY_ID,
                "alg": "RS256",
                "use": "sig",
                "n": _b64_uint(numbers.n),
                "e": _b64_uint(numbers.e),
            }
        ]
    }
    config = load_hosted_auth_runtime_config(
        {
            "CCLD_HOSTED_TESTER_AUTH_MODE": "production",
            "CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS": "cloudflare-access",
            "CCLD_CLOUDFLARE_ACCESS_TEAM_DOMAIN": TEAM_DOMAIN,
            "CCLD_CLOUDFLARE_ACCESS_AUD": AUDIENCE,
            "CCLD_CLOUDFLARE_ACCESS_ALLOWED_EMAIL_DOMAINS": "example.invalid",
            "CCLD_CLOUDFLARE_ACCESS_ALLOWED_EMAILS": OPERATOR_EMAIL,
            "CCLD_CLOUDFLARE_ACCESS_JWKS_CACHE_SECONDS": "0",
        }
    )
    os.environ["CCLD_OPERATOR_COVERAGE_ALLOWED_EMAILS"] = OPERATOR_EMAIL
    os.environ["CCLD_OPERATOR_COVERAGE_PACKAGE_DIR"] = str(package_dir)

    class Handler(app.HostedScaffoldHandler):
        def do_GET(self) -> None:
            status, content_type, body = app.route_response(
                self.path,
                method="GET",
                request_headers={key: value for key, value in self.headers.items()},
                auth_runtime_config=config,
                cloudflare_jwks_fetcher=lambda _url: jwks,
                cloudflare_auth_now=LOCAL_NOW,
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            disposition = app._content_disposition_header(  # noqa: SLF001
                self.path, status, content_type
            )
            if disposition is not None:
                self.send_header("Content-Disposition", disposition)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {
            "operator_headers": dict(operator_headers),
            "tester_headers": dict(tester_headers),
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _capture_route_set(
    packet: Path,
    base_url: str,
    *,
    operator_headers: Mapping[str, str],
    tester_headers: Mapping[str, str],
    local_mode: bool,
) -> list[dict[str, Any]]:
    captures = (
        {
            "label": "01-summary-desktop",
            "path": "/operator/source-coverage",
            "width": 1440,
            "height": 1100,
            "expected_status": 200,
            "contains": ("Coverage through reviewer surfaces",),
        },
        {
            "label": "02-summary-narrow",
            "path": "/operator/source-coverage",
            "width": 720,
            "height": 900,
            "expected_status": 200,
        },
        {
            "label": "03-summary-mobile",
            "path": "/operator/source-coverage",
            "width": 390,
            "height": 844,
            "expected_status": 200,
        },
        {
            "label": "04-summary-200-percent-reflow",
            "path": "/operator/source-coverage",
            "width": 360,
            "height": 450,
            "device_scale_factor": 2,
            "expected_status": 200,
        },
        {
            "label": "05-facilities",
            "path": "/operator/source-coverage/facilities",
            "width": 720,
            "height": 900,
            "expected_status": 200,
            "contains": ("Facility coverage details",),
        },
        {
            "label": "06-adjacent-first",
            "path": "/operator/source-coverage/facilities?limit=2",
            "width": 720,
            "height": 900,
            "expected_status": 200,
            "adjacent": True,
        },
        {
            "label": "08-jobs",
            "path": "/operator/source-coverage/jobs",
            "width": 720,
            "height": 900,
            "expected_status": 200,
            "contains": ("Refresh job metadata",),
        },
        {
            "label": "09-keyboard-focus",
            "path": "/operator/source-coverage/facilities",
            "width": 720,
            "height": 900,
            "expected_status": 200,
            "focus": True,
        },
        {
            "label": "10-print-summary",
            "path": "/operator/source-coverage",
            "width": 1440,
            "height": 1100,
            "expected_status": 200,
            "print": True,
        },
    )
    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        try:
            for capture in captures:
                result = _capture_page(
                    packet, base_url, capture, operator_headers, browser=browser
                )
                results.append(result)
                if capture.get("adjacent") and result.get("next_path"):
                    results.append(
                        _capture_page(
                            packet,
                            base_url,
                            {
                                "label": "07-adjacent-second",
                                "path": result["next_path"],
                                "width": 720,
                                "height": 900,
                                "expected_status": 200,
                            },
                            operator_headers,
                            browser=browser,
                        )
                    )
            results.append(
                _capture_page(
                    packet,
                    base_url,
                    {
                        "label": "11-authorization-denial",
                        "path": "/operator/source-coverage",
                        "width": 720,
                        "height": 900,
                        "expected_status": 401,
                        "contains": ("Cloudflare Access sign-in required",),
                    },
                    {},
                    browser=browser,
                )
            )
            results.append(
                _capture_page(
                    packet,
                    base_url,
                    {
                        "label": "12-reviewer-tier-denial",
                        "path": "/operator/source-coverage",
                        "width": 720,
                        "height": 900,
                        "expected_status": 403,
                        "contains": ("not authorized for operator source coverage",),
                    },
                    tester_headers,
                    browser=browser,
                )
            )
            downloads = (
                (
                    "13-aggregate-csv",
                    "/operator/source-coverage/export.csv",
                    "aggregate-coverage.csv",
                ),
                *(
                    (
                        f"14-facility-ids-{group}",
                        f"/operator/source-coverage/facility-ids.csv?group={group}",
                        f"facility-ids-{group}.csv",
                    )
                    for group in GROUPS
                ),
            )
            context = browser.new_context(extra_http_headers=dict(operator_headers))
            try:
                for label, path, filename in downloads:
                    response = context.request.get(base_url + path)
                    body = response.body()
                    (packet / "downloads" / filename).write_bytes(body)
                    assertions = [
                        _assertion("expected HTTP status", response.status == 200),
                        _assertion(
                            "CSV content type",
                            "text/csv" in response.headers.get("content-type", ""),
                        ),
                        _assertion("LF serialization", b"\r" not in body),
                        _assertion("prohibited content absent", _safe_output(body.decode("utf-8"))),
                    ]
                    results.append(
                        {
                            "label": label,
                            "path": path,
                            "kind": "download",
                            "status": response.status,
                            "assertions": assertions,
                        }
                    )
            finally:
                context.close()
        finally:
            browser.close()
    if local_mode:
        assert any(result["label"] == "07-adjacent-second" for result in results)
    return results


def _capture_page(
    packet: Path,
    base_url: str,
    capture: Mapping[str, Any],
    headers: Mapping[str, str],
    *,
    browser: Browser | None = None,
) -> dict[str, Any]:
    own_browser = browser is None
    playwright_manager = sync_playwright() if own_browser else None
    playwright = playwright_manager.start() if playwright_manager is not None else None
    active_browser = (
        playwright.chromium.launch(channel="msedge", headless=True)
        if playwright is not None
        else cast(Browser, browser)
    )
    context = active_browser.new_context(
        viewport={"width": int(capture["width"]), "height": int(capture["height"])},
        device_scale_factor=int(capture.get("device_scale_factor", 1)),
        extra_http_headers=dict(headers),
    )
    try:
        page = context.new_page()
        response = page.goto(
            base_url + str(capture["path"]), wait_until="networkidle", timeout=30000
        )
        status = response.status if response is not None else 0
        focused: Mapping[str, Any] | None = None
        if capture.get("focus"):
            for _ in range(30):
                page.keyboard.press("Tab")
                focused = page.evaluate(
                    """() => {
                      const e = document.activeElement;
                      const r = e?.getBoundingClientRect();
                      const s = e ? getComputedStyle(e) : null;
                      return e ? {tag: e.tagName, width: r.width, outline: s.outlineStyle} : null;
                    }"""
                )
                if focused and focused["width"] > 0 and focused["outline"] != "none":
                    break
        if capture.get("print"):
            page.emulate_media(media="print")
            page.pdf(
                path=str(packet / "screenshots" / f"{capture['label']}.pdf"),
                print_background=True,
            )
        metrics = page.evaluate(
            """() => ({
              scrollWidth: document.documentElement.scrollWidth,
              clientWidth: document.documentElement.clientWidth,
              h1Count: document.querySelectorAll('h1').length,
              headings: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
                .map(e => Number(e.tagName.slice(1))),
              operatorLinks: document.querySelectorAll(
                'nav.civic-nav a[href^="/operator/source-coverage"]'
              ).length,
              mutationControls: [...document.querySelectorAll('button,a')]
                .map(e => (e.textContent || '').trim().toLowerCase())
                .filter(v => ['retry','apply','cancel','resume','backfill'].includes(v))
            })"""
        )
        markup = page.content()
        if not _safe_output(markup):
            raise RuntimeError("Prohibited content reached an acceptance response.")
        (packet / "html" / f"{capture['label']}.html").write_text(
            markup, encoding="utf-8", newline="\n"
        )
        page.screenshot(
            path=str(packet / "screenshots" / f"{capture['label']}.png"),
            full_page=True,
        )
        headings = metrics["headings"]
        heading_order = all(
            current <= previous + 1
            for previous, current in zip(headings, headings[1:], strict=False)
        )
        body_text = page.locator("body").inner_text()
        assertions = [
            _assertion(
                "expected HTTP status", status == int(capture["expected_status"])
            ),
            _assertion("no horizontal overflow", metrics["scrollWidth"] <= metrics["clientWidth"]),
            _assertion("single h1", metrics["h1Count"] == 1),
            _assertion("semantic heading order", heading_order),
            _assertion("no mutation controls", not metrics["mutationControls"]),
            _assertion("prohibited content absent", _safe_output(markup)),
        ]
        for marker in cast(Sequence[str], capture.get("contains", ())):
            assertions.append(_assertion(f"contains {marker}", marker in body_text))
        if capture.get("focus"):
            assertions.append(
                _assertion(
                    "keyboard focus reaches visible control",
                    bool(focused)
                    and int(cast(Mapping[str, Any], focused)["width"]) > 0
                    and cast(Mapping[str, Any], focused)["outline"] != "none",
                )
            )
        next_path = None
        next_link = page.locator('a[aria-label="Next facilities"]')
        if next_link.count() >= 1:
            next_path = next_link.first.get_attribute("href")
        return {
            "label": capture["label"],
            "path": capture["path"],
            "kind": "page",
            "status": status,
            "viewport": f"{capture['width']}x{capture['height']}",
            "device_scale_factor": capture.get("device_scale_factor", 1),
            "operator_navigation_links": metrics["operatorLinks"],
            "next_path": next_path,
            "assertions": assertions,
        }
    finally:
        context.close()
        if own_browser:
            active_browser.close()
            assert playwright is not None
            playwright.stop()


def _provider_headers(command: str, role: str) -> Mapping[str, str]:
    completed = subprocess.run(
        [*shlex.split(command, posix=os.name != "nt"), role],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Hosted header provider failed for {role}; its output was suppressed."
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Hosted header provider returned invalid JSON for {role}; output suppressed."
        ) from error
    if not isinstance(payload, Mapping) or set(payload) != {"Cf-Access-Jwt-Assertion"}:
        raise RuntimeError(
            "Hosted header provider must return only the Cloudflare Access assertion header."
        )
    assertion = payload["Cf-Access-Jwt-Assertion"]
    if not isinstance(assertion, str) or not assertion.strip():
        raise RuntimeError("Hosted header provider returned an empty assertion.")
    return {"Cf-Access-Jwt-Assertion": assertion.strip()}


def _assertion(name: str, passed: bool) -> Mapping[str, Any]:
    return {"name": name, "passed": bool(passed)}


def _safe_output(value: str) -> bool:
    lowered = value.casefold()
    return not any(marker in lowered for marker in PROHIBITED_OUTPUT_MARKERS)


def _write_result_csvs(packet: Path, results: Sequence[Mapping[str, Any]]) -> None:
    with (packet / "route-status.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("label", "path", "kind", "status", "viewport"))
        for result in results:
            writer.writerow(
                (
                    result["label"],
                    result["path"],
                    result["kind"],
                    result["status"],
                    result.get("viewport", "download"),
                )
            )
    with (packet / "route-assertions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("label", "path", "assertion", "status"))
        for result in results:
            for assertion in cast(Sequence[Mapping[str, Any]], result["assertions"]):
                writer.writerow(
                    (
                        result["label"],
                        result["path"],
                        assertion["name"],
                        "PASS" if assertion["passed"] else "FAIL",
                    )
                )


def _write_zip(packet: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(packet.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(packet).as_posix())


def _validated_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("Hosted BaseUrl must be an absolute HTTP(S) origin.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("Hosted BaseUrl must not contain credentials, query, or fragment.")
    return value.rstrip("/")


def _require_unused_loopback_port(port: int) -> None:
    import socket

    with socket.socket() as candidate:
        try:
            candidate.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(
                f"Port {port} is already in use; an existing server will not be reused."
            ) from error


if __name__ == "__main__":
    raise SystemExit(main())
