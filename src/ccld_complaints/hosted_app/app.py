from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

APP_NAME = "CCLD Hosted Tester MVP Scaffold"
SCAFFOLD_NOTICE = "Scaffold only: not a functioning reviewer workflow yet."


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


def route_response(path: str) -> tuple[int, str, bytes]:
    parsed_path = urlparse(path).path
    if parsed_path == "/":
        return 200, "text/html; charset=utf-8", render_app_shell().encode("utf-8")
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