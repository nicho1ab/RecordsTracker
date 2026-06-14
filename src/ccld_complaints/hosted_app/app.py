from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

APP_NAME = "CCLD Hosted Tester MVP Scaffold"
SCAFFOLD_NOTICE = "Scaffold only: not a functioning reviewer workflow yet."
SAMPLE_DATA_NOTICE = "Local sample source-derived data only; no live public-source data is loaded."


@dataclass(frozen=True)
class SampleSourceRecord:
  record_id: str
  facility_name: str
  facility_number: str
  complaint_id: str
  complaint_control_number: str
  finding: str
  source_url: str
  raw_sha256: str
  connector_name: str
  retrieved_at: str
  report_index: str
  extraction_warning: str


SAMPLE_SOURCE_RECORDS = [
  SampleSourceRecord(
    record_id="sample-complaint-001",
    facility_name="Sample Facility Alpha",
    facility_number="000000001",
    complaint_id="sample-complaint-001",
    complaint_control_number="SAMPLE-CC-001",
    finding="Unknown",
    source_url="https://example.invalid/sample-ccld-source-document-001",
    raw_sha256="0" * 64,
    connector_name="sample-ccld-fixture",
    retrieved_at="2026-01-01T00:00:00+00:00",
    report_index="sample-1",
    extraction_warning="Sample-only value; not extracted from live public-source data.",
  ),
  SampleSourceRecord(
    record_id="sample-complaint-002",
    facility_name="Sample Facility Beta",
    facility_number="000000002",
    complaint_id="sample-complaint-002",
    complaint_control_number="SAMPLE-CC-002",
    finding="Unknown",
    source_url="https://example.invalid/sample-ccld-source-document-002",
    raw_sha256="1" * 64,
    connector_name="sample-ccld-fixture",
    retrieved_at="2026-01-02T00:00:00+00:00",
    report_index="sample-2",
    extraction_warning="Sample-only value; not extracted from live public-source data.",
  ),
]


def format_host(host: object) -> str:
    if isinstance(host, bytes):
        return host.decode("ascii")
    return str(host)


def health_response() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "hosted-tester-mvp-scaffold",
        "scaffold_only": True,
        "review_workflows_implemented": False,
        "authentication_implemented": False,
        "source_data_loaded": False,
    }


def get_sample_source_record(record_id: str) -> SampleSourceRecord | None:
    for record in SAMPLE_SOURCE_RECORDS:
        if record.record_id == record_id:
            return record
    return None


def render_scope_notice() -> str:
    return """<section aria-labelledby="scope-heading">
      <h2 id="scope-heading">Local view-shell scope</h2>
      <p>Fixture/sample data only. No live public-source data is loaded.</p>
      <p>No reviewer workflow is active, no authentication is implemented, and
      no reviewer-created state is persisted.</p>
      <p>Source-derived sample records and future reviewer-created state remain
      separate. This shell does not create queues, annotations, corrections,
      exports, feedback, audit history, reset/reload behavior, or imports.</p>
    </section>"""


def render_app_shell() -> str:
    page_title = html.escape(APP_NAME)
    notice = html.escape(SCAFFOLD_NOTICE)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title}</title>
</head>
<body>
  <header>
    <p>{notice}</p>
    <h1>{page_title}</h1>
  </header>
  <nav aria-label="Placeholder hosted scaffold navigation">
    <ul>
      <li><a href="#status">Scaffold status</a></li>
      <li><a href="/source-records">Sample source-derived records</a></li>
      <li><a href="#boundaries">Not implemented yet</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
    <section id="status" aria-labelledby="status-heading">
      <h2 id="status-heading">Local scaffold status</h2>
      <p>This local app shell is runnable on a Windows development workstation.</p>
      <p>No records are loaded, no users are authenticated, and no reviewer
      workflow behavior is active.</p>
      <p>The source-record shell uses fixture/sample data only.</p>
    </section>
    <section id="boundaries" aria-labelledby="boundaries-heading">
      <h2 id="boundaries-heading">Intentionally not implemented</h2>
      <ul>
        <li>Authentication and authorization.</li>
        <li>Production schema, migrations, or domain tables.</li>
        <li>Import/sync, queues, annotations, corrections, exports, feedback,
        audit trail, or reset/reload.</li>
        <li>Hosted live crawling, hosted connector execution, QNAP, Azure, AWS,
        public URLs, or deployment.</li>
      </ul>
    </section>
  </main>
</body>
</html>
"""


def render_source_record_list() -> str:
    rows = "\n".join(
        f"""        <tr>
          <td><a href="/source-records/{html.escape(record.record_id)}">
            {html.escape(record.complaint_control_number)}
          </a></td>
          <td>{html.escape(record.facility_name)}</td>
          <td>{html.escape(record.facility_number)}</td>
          <td>{html.escape(record.finding)}</td>
          <td>{html.escape(record.raw_sha256)}</td>
        </tr>"""
        for record in SAMPLE_SOURCE_RECORDS
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sample source-derived records - {html.escape(APP_NAME)}</title>
</head>
<body>
  <header>
    <p>{html.escape(SCAFFOLD_NOTICE)}</p>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>Sample source-derived records</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Scaffold home</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
    {render_scope_notice()}
    <section aria-labelledby="records-heading">
      <h2 id="records-heading">Fixture/sample source record list</h2>
      <p>These rows are sample-only placeholders for a future read-only hosted
      source-derived view. They are not imported records and are not official
      public-source facts.</p>
      <table>
        <caption>Local sample source-derived complaint records</caption>
        <thead>
          <tr>
            <th scope="col">Complaint control number</th>
            <th scope="col">Facility name</th>
            <th scope="col">Facility number</th>
            <th scope="col">Finding</th>
            <th scope="col">Raw SHA-256</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def render_source_record_detail(record: SampleSourceRecord) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(record.complaint_control_number)} - {html.escape(APP_NAME)}</title>
</head>
<body>
  <header>
    <p>{html.escape(SCAFFOLD_NOTICE)}</p>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>{html.escape(record.complaint_control_number)}</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Scaffold home</a></li>
      <li><a href="/source-records">Sample source-derived records</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
    {render_scope_notice()}
    <section aria-labelledby="detail-heading">
      <h2 id="detail-heading">Read-only sample source-derived detail</h2>
      <dl>
        <dt>Facility name</dt>
        <dd>{html.escape(record.facility_name)}</dd>
        <dt>Facility number</dt>
        <dd>{html.escape(record.facility_number)}</dd>
        <dt>Complaint ID</dt>
        <dd>{html.escape(record.complaint_id)}</dd>
        <dt>Finding</dt>
        <dd>{html.escape(record.finding)}</dd>
        <dt>Sample source URL</dt>
        <dd>{html.escape(record.source_url)}</dd>
        <dt>Raw SHA-256</dt>
        <dd>{html.escape(record.raw_sha256)}</dd>
        <dt>Connector name</dt>
        <dd>{html.escape(record.connector_name)}</dd>
        <dt>Retrieved at</dt>
        <dd>{html.escape(record.retrieved_at)}</dd>
        <dt>Report index</dt>
        <dd>{html.escape(record.report_index)}</dd>
        <dt>Extraction warning</dt>
        <dd>{html.escape(record.extraction_warning)}</dd>
      </dl>
    </section>
  </main>
</body>
</html>
"""


def route_response(path: str) -> tuple[int, str, bytes]:
    parsed_path = urlparse(path).path
    if parsed_path == "/":
        return 200, "text/html; charset=utf-8", render_app_shell().encode("utf-8")
    if parsed_path == "/source-records":
        return 200, "text/html; charset=utf-8", render_source_record_list().encode("utf-8")
    if parsed_path.startswith("/source-records/"):
        record_id = parsed_path.removeprefix("/source-records/")
        record = get_sample_source_record(record_id)
        if record is not None:
            body = render_source_record_detail(record).encode("utf-8")
            return 200, "text/html; charset=utf-8", body
    if parsed_path in {"/health", "/api/health"}:
        body = json.dumps(health_response(), sort_keys=True).encode("utf-8")
        return 200, "application/json; charset=utf-8", body
    body = b"Not found"
    return 404, "text/plain; charset=utf-8", body


class HostedScaffoldHandler(BaseHTTPRequestHandler):
    server_version = "CCLDHostedScaffold/0.1"

    def do_GET(self) -> None:
        status, content_type, body = route_response(self.path)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), HostedScaffoldHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local hosted tester MVP scaffold.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    with create_server(args.host, args.port) as server:
        host, port = server.server_address[:2]
        print(f"{APP_NAME} running locally at http://{format_host(host)}:{port}/")
        print(SCAFFOLD_NOTICE)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopping local hosted tester MVP scaffold.")
    return 0